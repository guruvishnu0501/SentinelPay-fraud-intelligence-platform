from pathlib import Path
import io, html, json, csv
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Polygon
from engine import FraudEngine
from db import db_manager

ROOT = Path(__file__).parent
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

engine = FraudEngine(ROOT)

merchant_options = sorted(engine.df.merchant_name.dropna().astype(str).unique())
category_options = sorted(engine.df.merchant_category.dropna().astype(str).unique())
channel_options = sorted(engine.df.channel.dropna().astype(str).unique())
country_options = sorted(engine.df.ip_country.dropna().astype(str).unique())
city_options = sorted(engine.df.transaction_city.dropna().astype(str).unique())

REQUIRED_COLS = ['card_id', 'trans_date_trans_time', 'amount_inr', 'merchant_name', 'merchant_category', 'channel', 'ip_country', 'transaction_city', 'customer_lat', 'customer_lon', 'merchant_lat', 'merchant_lon', 'device_id']

def create_risk_bar_drawing(probability):
    p = max(0.0, min(1.0, float(probability or 0.0)))
    d = Drawing(520, 24)
    # Background segments: Green (0-40%), Amber (40-70%), Red (70-100%)
    d.add(Rect(0, 8, 208, 14, fillColor=colors.HexColor('#10b981'), strokeColor=None, rx=4, ry=4))
    d.add(Rect(208, 8, 156, 14, fillColor=colors.HexColor('#f59e0b'), strokeColor=None))
    d.add(Rect(364, 8, 156, 14, fillColor=colors.HexColor('#ef4444'), strokeColor=None, rx=4, ry=4))
    
    # Triangle marker pointing down at x_pos
    x_pos = max(6, min(514, p * 520))
    d.add(Polygon([x_pos - 6, 0, x_pos + 6, 0, x_pos, 7], fillColor=colors.HexColor('#0f172a'), strokeColor=None))
    return d

def pdf_report(result, raw_tx=None):
    tx = raw_tx or {}
    tx_id = str(tx.get('transaction_id') or result.get('transaction_id') or f"TXN-{str(tx.get('card_id', '999001'))}")
    report_id = tx_id if tx_id.startswith('REP-') else f"REP-{tx_id}"
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    risk_level = str(result.get('risk_level') or tx.get('risk_level') or 'LOW').upper()
    prob = float(result.get('ml_fraud_probability') if result.get('ml_fraud_probability') is not None else tx.get('ml_fraud_probability', 0.0))
    prob_pct_str = f"{prob * 100:.2f}%"
    threshold_str = f"{engine.threshold:.2f}"
    
    dec_full = str(result.get('decision') or tx.get('decision') or '').upper()
    if risk_level == 'HIGH' or 'FRAUD' in dec_full or 'BLOCK' in dec_full:
        short_dec = 'FRAUD'
    elif risk_level == 'MEDIUM' or 'SUSPICIOUS' in dec_full or 'STEP' in dec_full:
        short_dec = 'SUSPICIOUS'
    else:
        short_dec = 'GENUINE'
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    styles = getSampleStyleSheet()
    brand_style = ParagraphStyle('Brand', parent=styles['Normal'], fontSize=16, leading=20, textColor=colors.HexColor('#1e293b'), fontName='Helvetica-Bold')
    header_meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.HexColor('#475569'), alignment=2)
    badge_style = ParagraphStyle('Badge', parent=styles['Normal'], fontSize=10, leading=12, textColor=colors.HexColor('#ef4444' if risk_level=='HIGH' else ('#f59e0b' if risk_level=='MEDIUM' else '#10b981')), alignment=1, fontName='Helvetica-Bold')
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#1e293b'), spaceBefore=14, spaceAfter=8, fontName='Helvetica-Bold')
    
    card_label_style = ParagraphStyle('CardLabel', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#64748b'), alignment=1, fontName='Helvetica-Bold')
    card_val_style = ParagraphStyle('CardVal', parent=styles['Normal'], fontSize=14, leading=18, textColor=colors.HexColor('#0f172a'), alignment=1, fontName='Helvetica-Bold')
    
    table_lbl_style = ParagraphStyle('TblLbl', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#64748b'), fontName='Helvetica-Bold')
    table_val_style = ParagraphStyle('TblVal', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor('#0f172a'), fontName='Helvetica')

    # Top Header Table
    header_left = Paragraph('<b>SENTINELPAY AI</b><br/><font color="#64748b">FRAUD INVESTIGATION REPORT</font>', brand_style)
    header_right_text = f"<b>Report ID:</b> {html.escape(report_id)}<br/><b>Generated:</b> {now_str}<br/><b>Engine:</b> XGBoost Classifier (Production)"
    header_right = Paragraph(header_right_text, header_meta_style)
    
    badge_table = Table([[Paragraph(f"{risk_level} RISK", badge_style)]], colWidths=[90])
    badge_bg = colors.HexColor('#fef2f2' if risk_level=='HIGH' else ('#fffbe6' if risk_level=='MEDIUM' else '#ecfdf5'))
    badge_border = colors.HexColor('#fca5a5' if risk_level=='HIGH' else ('#fde68a' if risk_level=='MEDIUM' else '#a7f3d0'))
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), badge_bg),
        ('BOX', (0,0), (-1,-1), 1, badge_border),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    
    top_table = Table([[header_left, header_right, badge_table]], colWidths=[240, 190, 90])
    top_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (2,0), (2,0), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 0),
    ]))
    
    story = [
        top_table,
        Spacer(1, 14),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceBefore=0, spaceAfter=14),
        
        Paragraph('1. Executive Decision Summary', h2_style),
    ]
    
    if risk_level == 'HIGH':
        act_text, act_color = 'BLOCK', '#ef4444'
    elif risk_level == 'MEDIUM':
        act_text, act_color = 'STEP-UP', '#f59e0b'
    else:
        act_text, act_color = 'ALLOW', '#10b981'
    card_action_style = ParagraphStyle('CardAction', parent=styles['Normal'], fontSize=12, leading=16, textColor=colors.HexColor(act_color), alignment=1, fontName='Helvetica-Bold')

    # 4 Cards Table
    c1 = [Paragraph('MODEL DECISION', card_label_style), Paragraph(short_dec, card_val_style)]
    c2 = [Paragraph('FRAUD PROBABILITY', card_label_style), Paragraph(prob_pct_str, card_val_style)]
    c3 = [Paragraph('RISK TIER', card_label_style), Paragraph(risk_level, card_val_style)]
    c4 = [Paragraph('RECOMMENDED ACTION', card_label_style), Paragraph(act_text, card_action_style)]
    
    cards_table = Table([[c1, c2, c3, c4]], colWidths=[125, 125, 125, 125])
    cards_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(cards_table)
    story.append(Spacer(1, 10))
    story.append(create_risk_bar_drawing(prob))
    story.append(Spacer(1, 16))
    
    # Section 2: Transaction Attributes Summary
    story.append(Paragraph('2. Transaction Attributes Summary', h2_style))
    
    amount_val = float(tx.get('amount_inr', result.get('amount_inr', 0.0)) or 0.0)
    amt_str = f"₹{amount_val:,.2f}"
    priority_str = "Critical" if risk_level == "HIGH" else ("Elevated" if risk_level == "MEDIUM" else "Standard")
    location_str = f"{tx.get('transaction_city', 'Hyderabad')}, {tx.get('ip_country', 'India')}"
    
    tx_attr_rows = [
        [
            Paragraph('Transaction ID', table_lbl_style), Paragraph(html.escape(tx_id), table_val_style),
            Paragraph('Transaction Amount', table_lbl_style), Paragraph(amt_str, table_val_style)
        ],
        [
            Paragraph('Merchant Name', table_lbl_style), Paragraph(html.escape(str(tx.get('merchant_name', 'N/A'))), table_val_style),
            Paragraph('Category', table_lbl_style), Paragraph(html.escape(str(tx.get('merchant_category', 'N/A'))), table_val_style)
        ],
        [
            Paragraph('Customer Account ID', table_lbl_style), Paragraph(html.escape(str(tx.get('card_id', 'N/A'))), table_val_style),
            Paragraph('Transaction Timestamp', table_lbl_style), Paragraph(html.escape(str(tx.get('trans_date_trans_time', now_str))), table_val_style)
        ],
        [
            Paragraph('Transaction Location', table_lbl_style), Paragraph(html.escape(location_str), table_val_style),
            Paragraph('Investigation Priority', table_lbl_style), Paragraph(priority_str, table_val_style)
        ]
    ]
    
    attr_table = Table(tx_attr_rows, colWidths=[130, 130, 130, 130])
    attr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f8fafc')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(attr_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.get('/')
def dashboard():
    return render_template('dashboard.html')

@app.get('/screen')
def screen():
    return render_template('index.html', cities=city_options, merchants=merchant_options, categories=category_options, channels=channel_options, countries=country_options)

@app.get('/batch')
def batch():
    return render_template('batch.html')

@app.get('/investigation')
def investigation():
    return render_template('investigation.html')

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

@app.get('/api/transaction/<tx_id>')
def get_transaction_api(tx_id):
    tx = db_manager.get_transaction(tx_id)
    if tx:
        return jsonify({'ok': True, 'result': tx})
    return jsonify({'ok': False, 'error': f'Transaction {tx_id} not found'}), 404

@app.get('/api/transactions')
def get_transactions_api():
    limit = request.args.get('limit', 1000, type=int)
    txs = db_manager.get_recent_transactions(limit)
    return jsonify({'ok': True, 'transactions': txs})

@app.post('/api/clear-session')
def clear_session_api():
    db_manager.clear_transactions()
    return jsonify({'ok': True})

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
        if not data.get('transaction_id'):
            data['transaction_id'] = f"TXN-{int(datetime.now().timestamp()*1000)}"
            
        debug_flag = request.args.get('debug', 'false').lower() == 'true' or request.headers.get('X-Debug-Mode', '').lower() == 'true'
        res = engine.analyze(data, debug=debug_flag)
        
        res['transaction_id'] = data['transaction_id']
        res['card_id'] = data.get('card_id')
        res['amount_inr'] = data.get('amount_inr')
        res['merchant_name'] = data.get('merchant_name')
        res['merchant_category'] = data.get('merchant_category')
        res['trans_date_trans_time'] = str(data.get('trans_date_trans_time'))
        res['ip_country'] = data.get('ip_country')
        res['transaction_city'] = data.get('transaction_city')
        res['channel'] = data.get('channel')
        res['device_id'] = data.get('device_id')
        res['raw_transaction'] = data
        
        db_manager.save_transaction(res)
        return jsonify({'ok': True, 'result': res})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400

@app.post('/api/report')
def report():
    try:
        data = request.get_json(force=True) if request.is_json else {}
        tx_id = request.args.get('id') or data.get('transaction_id') or data.get('id')
        
        res = None
        raw_tx = None
        
        if tx_id:
            db_tx = db_manager.get_transaction(tx_id)
            if db_tx:
                res = db_tx
                raw_tx = db_tx
                
        if not res:
            if 'decision' in data:
                res = data
                raw_tx = data.get('raw_transaction', data)
            elif data:
                res = engine.analyze(data)
                raw_tx = data
            else:
                return jsonify({'ok': False, 'error': 'No transaction data provided'}), 400
                
        pdf_buf = pdf_report(res, raw_tx)
        out_tx_id = str(res.get('transaction_id') or raw_tx.get('transaction_id') or 'TXN').replace('/', '_')
        return send_file(pdf_buf, as_attachment=True, download_name=f"sentinelpay_report_{out_tx_id}.pdf", mimetype='application/pdf')
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
                    
            if not r.get('transaction_id') and r.get('card_id'):
                r['transaction_id'] = f"TXN-BATCH-{int(datetime.now().timestamp()*1000)}-{r.get('card_id')}"
        
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

