from pathlib import Path
import io, html, json, csv
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from engine import FraudEngine
from db import db_manager

ROOT = Path(__file__).parent
app = Flask(__name__)
engine = FraudEngine(ROOT)

merchant_options = sorted(engine.df.merchant_name.dropna().astype(str).unique())
category_options = sorted(engine.df.merchant_category.dropna().astype(str).unique())
channel_options = sorted(engine.df.channel.dropna().astype(str).unique())
country_options = sorted(engine.df.ip_country.dropna().astype(str).unique())
city_options = sorted(engine.df.transaction_city.dropna().astype(str).unique())

REQUIRED_COLS = ['card_id', 'trans_date_trans_time', 'amount_inr', 'merchant_name', 'merchant_category', 'channel', 'ip_country', 'transaction_city', 'customer_lat', 'customer_lon', 'merchant_lat', 'merchant_lon', 'device_id']

def pdf_report(result, raw_tx=None):
    path = ROOT / 'artifacts' / 'sentinelpay_transaction_report.pdf'
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('RepTitle', parent=styles['Title'], fontSize=20, leading=24, textColor=colors.HexColor('#0f172a'), alignment=0)
    sub_style = ParagraphStyle('RepSub', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#64748b'))
    h2_style = ParagraphStyle('RepH2', parent=styles['Heading2'], fontSize=14, leading=18, textColor=colors.HexColor('#1e293b'), spaceBefore=12, spaceAfter=6)
    normal_style = ParagraphStyle('RepNorm', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor('#334155'))
    
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    card_id = raw_tx.get('card_id', 'N/A') if raw_tx else 'N/A'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    story = [
        Paragraph('SENTINELPAY — TRANSACTION RISK ASSESSMENT REPORT', title_style),
        Paragraph(f"Generated: {now_str} &nbsp;|&nbsp; Card ID: <b>{html.escape(str(card_id))}</b>", sub_style),
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceBefore=4, spaceAfter=12),
        
        Paragraph('RISK DECISION', h2_style),
        Paragraph(f"<b>Decision:</b> {html.escape(str(result.get('decision', 'N/A')))}", normal_style),
        Paragraph(f"<b>Risk Level:</b> {result.get('risk_level', 'N/A')} RISK", normal_style),
        Paragraph(f"<b>Operational Risk Score:</b> {result.get('operational_risk_score', 0):.2f} / 100", normal_style),
        Paragraph(f"<b>Recommended Action:</b> <b>{html.escape(str(result.get('recommended_action', 'N/A')))}</b>", normal_style),
        Spacer(1, 10),
        
        Paragraph('TRANSACTION DETAILS', h2_style)
    ]
    
    tx_details = raw_tx or {}
    tx_rows = [
        ['Amount (₹)', f"₹{tx_details.get('amount_inr', 'N/A')}", 'Merchant', str(tx_details.get('merchant_name', 'N/A'))],
        ['Category', str(tx_details.get('merchant_category', 'N/A')), 'Channel', str(tx_details.get('channel', 'N/A'))],
        ['City', str(tx_details.get('transaction_city', 'N/A')), 'IP Country', str(tx_details.get('ip_country', 'N/A'))],
        ['Device ID', str(tx_details.get('device_id', 'N/A')), 'Date / Time', str(tx_details.get('trans_date_trans_time', 'N/A'))]
    ]
    t_tx = Table(tx_rows, colWidths=[110, 150, 110, 150])
    t_tx.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1e293b')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 5)
    ]))
    story.append(t_tx)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph('RISK ANALYSIS', h2_style))
    prob = result.get('ml_fraud_probability')
    prob_str = f"{prob * 100:.2f}%" if prob is not None else "N/A"
    story.append(Paragraph(f"<b>ML Fraud Probability:</b> {prob_str}", normal_style))
    story.append(Paragraph(f"<b>Business Evidence Score:</b> {result.get('business_evidence_score', 0)} / 100", normal_style))
    story.append(Paragraph(f"<b>Evidence Families Triggered:</b> {result.get('evidence_family_count', 0)}", normal_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph('DECISION EXPLANATION', h2_style))
    reasons = result.get('reasons', [])
    if reasons:
        exp_text = "Multiple risk signals were detected during authorization: " + "; ".join(reasons) + "."
    else:
        exp_text = "No material anomaly evidence was detected. Transaction aligns with expected customer behavior."
    story.append(Paragraph(html.escape(exp_text), normal_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph('TRIGGERED RISK FACTORS', h2_style))
    for r in reasons:
        story.append(Paragraph('• ' + html.escape(str(r)), normal_style))
    if not reasons:
        story.append(Paragraph('• Standard authorization parameters satisfied.', normal_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph('BEHAVIORAL & CONTEXTUAL SIGNALS', h2_style))
    b_ctx = result.get('behavioral_context', {})
    rows = [['Signal', 'Observed Value']] + [[k.replace('_', ' ').title(), str(v if v is not None else 'Unavailable — Cold Start')] for k, v in b_ctx.items()]
    t_b = Table(rows, colWidths=[250, 270])
    t_b.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('PADDING', (0, 0), (-1, -1), 4)
    ]))
    story.append(t_b)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#cbd5e1'), spaceBefore=4, spaceAfter=8))
    story.append(Paragraph('<b>SentinelPay AI Fraud Screening Prototype</b><br/><i>This report is generated by the SentinelPay prototype using the configured transaction-risk model and evidence engine. It is intended for demonstration and evaluation purposes.</i>', ParagraphStyle('Disc', parent=styles['Italic'], fontSize=8, leading=11, textColor=colors.HexColor('#64748b'))))
    
    doc.build(story)
    return path

@app.get('/')
def dashboard():
    return render_template('dashboard.html')

@app.get('/screen')
def screen():
    return render_template('index.html', cities=city_options, merchants=merchant_options, categories=category_options, channels=channel_options, countries=country_options)

@app.get('/batch')
def batch():
    return render_template('batch.html')

@app.get('/fraud-intelligence')
def fraud_intelligence():
    return render_template('fraud_intelligence.html')

@app.get('/model')
def model_tech():
    return render_template('model.html')

@app.get('/api/options')
def options():
    return jsonify({
        'cities': city_options,
        'merchants': merchant_options,
        'categories': category_options,
        'channels': channel_options,
        'countries': country_options,
        'threshold': engine.threshold
    })

@app.get('/api/model-info')
def model_info():
    meta_path = ROOT / 'artifacts' / 'metadata.json'
    if meta_path.exists():
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        return jsonify({
            'ok': True,
            'model_name': meta.get('final_untouched_future_test', {}).get('model', 'xgboost').upper(),
            'model_version': '2.0-hybrid',
            'threshold': engine.threshold,
            'dataset_rows': meta.get('dataset', {}).get('rows', 100000),
            'metrics': meta.get('final_untouched_future_test', {}),
            'selection_results': meta.get('model_selection', {}).get('validation_results', {})
        })
    return jsonify({'ok': False, 'error': 'Metadata unavailable'}), 404

@app.get('/api/template.csv')
def template():
    sample = pd.DataFrame([{
        'card_id': 999001,
        'trans_date_trans_time': '2026-08-17 18:30:00',
        'amount_inr': 1850,
        'merchant_name': 'Amazon India',
        'merchant_category': 'ecommerce',
        'channel': 'ECOMMERCE',
        'ip_country': 'India',
        'transaction_city': 'Hyderabad',
        'customer_lat': 17.385,
        'customer_lon': 78.4867,
        'merchant_lat': 17.388,
        'merchant_lon': 78.489,
        'device_id': 'DEV-DEMO-001'
    }], columns=REQUIRED_COLS)
    return send_file(io.BytesIO(sample.to_csv(index=False).encode('utf-8')), as_attachment=True, download_name='sentinelpay_input_template.csv', mimetype='text/csv')

@app.post('/api/analyze')
def analyze():
    try:
        data = request.get_json(force=True)
        debug_flag = request.args.get('debug', 'false').lower() == 'true' or request.headers.get('X-Debug-Mode', '').lower() == 'true'
        res = engine.analyze(data, debug=debug_flag)
        db_manager.save_transaction(res)
        return jsonify({'ok': True, 'result': res})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.post('/api/report')
def report():
    try:
        data = request.get_json(force=True)
        if 'decision' not in data:
            res = engine.analyze(data)
            raw_tx = data
        else:
            res = data
            raw_tx = data.get('raw_transaction', {})
        pdf = pdf_report(res, raw_tx)
        return send_file(pdf, as_attachment=True, download_name='sentinelpay_transaction_report.pdf', mimetype='application/pdf')
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.post('/api/batch')
def batch_analyze():
    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'ok': False, 'error': 'Only CSV files are supported'}), 400
    try:
        content_bytes = file.read()
        if not content_bytes or len(content_bytes.strip()) == 0:
            return jsonify({'ok': False, 'error': 'Uploaded CSV file is empty'}), 400
            
        content_str = content_bytes.decode('utf-8-sig', errors='replace')
        lines = [line for line in content_str.splitlines() if line.strip()]
        if not lines:
            return jsonify({'ok': False, 'error': 'Uploaded CSV file is empty'}), 400
            
        reader = csv.reader(lines)
        raw_header = next(reader, None)
        if not raw_header:
            return jsonify({'ok': False, 'error': 'CSV header missing'}), 400
            
        headers = [str(h or '').strip() for h in raw_header]
        missing_headers = [col for col in REQUIRED_COLS if col not in headers]
        if missing_headers:
            return jsonify({
                'ok': False,
                'error': f"CSV header validation failed. Missing required columns: {', '.join(missing_headers)}"
            }), 400
            
        input_rows = []
        expected_cols_count = len(headers)
        row_idx = 1
        
        for raw_row in reader:
            if not raw_row or not any(str(c).strip() for c in raw_row):
                continue
                
            row_idx += 1
            row_dict = {}
            if len(raw_row) != expected_cols_count:
                row_dict['_malformed_error'] = f"Row {row_idx}: INPUT ERROR — expected {expected_cols_count} columns but received {len(raw_row)}."
                for i, h in enumerate(headers):
                    row_dict[h] = str(raw_row[i]).strip() if i < len(raw_row) else ''
            else:
                for i, h in enumerate(headers):
                    row_dict[h] = str(raw_row[i]).strip()
            input_rows.append(row_dict)
            
        if not input_rows:
            return jsonify({'ok': False, 'error': 'CSV contains no valid data rows'}), 400
            
        res_df = engine.batch(input_rows)
        
        summary = {
            'total_rows': len(res_df),
            'genuine_count': int((res_df['decision'] == 'GENUINE TRANSACTION').sum()),
            'suspicious_count': int((res_df['decision'] == 'SUSPICIOUS TRANSACTION').sum()),
            'fraud_count': int((res_df['decision'] == 'FRAUDULENT TRANSACTION').sum()),
            'error_count': int((res_df['decision'] == 'INPUT ERROR').sum()),
            'avg_risk_score': None if res_df['operational_risk_score'].dropna().empty else round(float(res_df['operational_risk_score'].dropna().mean()), 2)
        }
        
        csv_buffer = io.StringIO()
        res_df.to_csv(csv_buffer, index=False)
        csv_text = csv_buffer.getvalue()
        
        rows_list = res_df.to_dict('records')
        for r in rows_list:
            for k, v in r.items():
                if pd.isna(v):
                    r[k] = None
        
        db_manager.save_batch_transactions(rows_list)
        
        return jsonify({
            'ok': True,
            'summary': summary,
            'rows': rows_list,
            'csv': csv_text
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': f"Failed to process CSV file: {str(e)}"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
