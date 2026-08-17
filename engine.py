from pathlib import Path
import joblib, numpy as np, pandas as pd
from features import current_behavior_features, normalize_raw_transaction
from risk_engine import evidence, final_decision
from model_spec import INPUT_COLS, NUM_COLS

class FraudEngine:
    def __init__(self, root=None):
        root = Path(root or Path(__file__).parent)
        art = root / 'artifacts'
        data = root / 'Dataset.csv'
        self.pre = joblib.load(art / 'preprocessor.joblib')
        self.model = joblib.load(art / 'model.joblib')
        self.calibrator = joblib.load(art / 'calibrator.joblib')
        self.contract = joblib.load(art / 'contract.joblib')
        hist_file = art / 'history_df.joblib'
        if hist_file.exists():
            self.df = joblib.load(hist_file)
        elif data.exists():
            self.df = pd.read_csv(data, parse_dates=['trans_date_trans_time']).sort_values('trans_date_trans_time', kind='mergesort').reset_index(drop=True)
        else:
            self.df = pd.DataFrame(columns=INPUT_COLS + ['transaction_state', 'transaction_zip', 'city_population'])

        ref_file = art / 'reference_data.joblib'
        if ref_file.exists():
            ref = joblib.load(ref_file)
            self.city_reference = ref['city_reference']
            self.amount_inr_values = np.array(ref['amount_inr_values'])
        else:
            self.city_reference = self.df.groupby('transaction_city', as_index=True).agg(
                transaction_state=('transaction_state', 'first'),
                transaction_zip=('transaction_zip', 'first'),
                city_population=('city_population', 'first')
            ).to_dict('index') if 'transaction_city' in self.df.columns and len(self.df) else {}
            self.amount_inr_values = self.df['amount_inr'].values if 'amount_inr' in self.df.columns else np.array([])

        self.q95, self.q99 = self.contract['quantiles']
        self.threshold = float(self.contract['threshold'])

    def probability(self, f):
        row = pd.DataFrame([f])
        X = self.pre.transform(row)
        raw = float(self.model.predict_proba(X)[0, 1])
        eps = 1e-6
        z = np.log(np.clip(raw, eps, 1 - eps) / (1 - np.clip(raw, eps, 1 - eps))).reshape(1, -1)
        calibrated = float(self.calibrator.predict_proba(z)[0, 1])
        return calibrated, raw

    def _analyze_with_history(self, raw_tx, hist, debug=False):
        missing = [c for c in INPUT_COLS if c not in raw_tx or raw_tx[c] in [None, '']]
        if missing:
            raise ValueError('Missing required fields: ' + ', '.join(missing))
            
        tx = normalize_raw_transaction(raw_tx, self.city_reference)
        f = current_behavior_features(tx, hist, self.q95, self.q99)
        p, raw_p = self.probability(f)
        ev_score, fams, reasons = evidence(f)
        dec, level, action, op = final_decision(p, ev_score, fams, self.threshold)
        
        if p >= self.threshold:
            reasons.insert(0, f"ML fraud probability ({p*100:.1f}%) exceeds validation threshold ({self.threshold*100:.1f}%).")
        if not reasons:
            reasons = ['No material anomaly evidence was triggered.']
            
        ctx = {
            'history_state': 'AVAILABLE' if len(hist) else 'COLD START',
            'amount_percentile': round(float((self.amount_inr_values <= tx['amount_inr']).mean() * 100), 2) if len(self.amount_inr_values) else 50.0,
            'amount_ratio_to_card_avg': None if pd.isna(f.get('amount_ratio_to_card_avg')) else round(float(f['amount_ratio_to_card_avg']), 2),
            'amount_zscore_to_card': None if pd.isna(f.get('amount_zscore_to_card')) else round(float(f['amount_zscore_to_card']), 2),
            'transactions_last_1h': int(f.get('txns_last_1h', 0) or 0),
            'transactions_last_24h': int(f.get('txns_last_24h', 0) or 0),
            'new_city': int(f.get('new_city', 0) or 0),
            'new_device': int(f.get('new_device', 0) or 0),
            'merchant_distance_km': round(float(f.get('merchant_distance_km', 0)), 2),
            'previous_location_distance_km': None if pd.isna(f.get('previous_location_distance_km')) else round(float(f['previous_location_distance_km']), 2),
            'implied_travel_speed_kmh': None if pd.isna(f.get('implied_travel_speed_kmh')) else round(float(f['implied_travel_speed_kmh']), 2),
            'hours_since_previous': None if pd.isna(f.get('hours_since_previous')) else round(float(f['hours_since_previous']), 2)
        }
        
        res = {
            'decision': dec,
            'risk_level': level,
            'recommended_action': action,
            'ml_fraud_probability': p,
            'operational_risk_score': round(op, 2),
            'business_evidence_score': int(ev_score),
            'evidence_families': list(fams.keys()),
            'evidence_family_count': len(fams),
            'reasons': reasons,
            'behavioral_context': ctx
        }
        
        if debug:
            num_fam = len(fams)
            anomaly_intensity = min(100.0, num_fam * 20.0)
            res['debug_info'] = {
                'raw_inputs': raw_tx,
                'derived_features': f,
                'ml': {
                    'raw_probability': round(raw_p, 6),
                    'calibrated_probability': round(p, 6),
                    'binary_threshold': self.threshold
                },
                'evidence': {
                    'score': ev_score,
                    'families': list(fams.keys()),
                    'reasons': reasons
                },
                'operational': {
                    'ml_contribution': round(0.38 * (p * 100.0), 2),
                    'evidence_contribution': round(0.45 * ev_score, 2),
                    'anomaly_contribution': round(0.17 * anomaly_intensity, 2),
                    'final_score': round(op, 2),
                    'risk_level': level,
                    'action': action
                }
            }
            
        return res

    def analyze(self, raw_tx, reference_df=None, debug=False):
        tx = normalize_raw_transaction(raw_tx, self.city_reference)
        base = self.df if reference_df is None else reference_df
        hist = pd.DataFrame(columns=self.df.columns)
        if not base.empty:
            hist = base[(base.card_id.astype(str) == str(tx['card_id'])) & (pd.to_datetime(base.trans_date_trans_time) < tx['trans_date_trans_time'])].copy()
        return self._analyze_with_history(tx, hist, debug=debug)

    def batch(self, rows):
        work = pd.DataFrame(rows).copy()
        work['_original_order'] = range(len(work))
        work['_ts_sort'] = pd.to_datetime(work.get('trans_date_trans_time'), errors='coerce')
        work = work.sort_values(['_ts_sort', '_original_order'], kind='mergesort')
        
        state = {str(card): g.copy() for card, g in self.df.groupby('card_id', sort=False)}
        out = []
        
        for item in work.to_dict('records'):
            original_order = item.pop('_original_order')
            item.pop('_ts_sort', None)
            try:
                err = item.pop('_malformed_error', None)
                if err and isinstance(err, str) and err.strip():
                    raise ValueError(err)
                    
                tx = normalize_raw_transaction(item, self.city_reference)
                key = str(tx['card_id'])
                hist = state.get(key, pd.DataFrame(columns=self.df.columns))
                if not hist.empty:
                    hist = hist[pd.to_datetime(hist.trans_date_trans_time) < tx['trans_date_trans_time']].copy()
                result = self._analyze_with_history(tx, hist, debug=False)
                out.append({
                    **item,
                    'decision': result['decision'],
                    'risk_level': result['risk_level'],
                    'recommended_action': result['recommended_action'],
                    'ml_fraud_probability': round(result['ml_fraud_probability'], 6),
                    'operational_risk_score': result['operational_risk_score'],
                    'business_evidence_score': result['business_evidence_score'],
                    'evidence_families': '|'.join(result['evidence_families']),
                    'evidence_family_count': result['evidence_family_count'],
                    'history_state': result['behavioral_context']['history_state'],
                    'transactions_last_1h': result['behavioral_context']['transactions_last_1h'],
                    'transactions_last_24h': result['behavioral_context']['transactions_last_24h'],
                    'new_city': result['behavioral_context']['new_city'],
                    'new_device': result['behavioral_context']['new_device'],
                    'reasons': ' | '.join(result['reasons']),
                    '_original_order': original_order
                })
                tx_row = pd.DataFrame([tx])
                if hist.empty:
                    state[key] = tx_row
                else:
                    state[key] = pd.concat([hist, tx_row], ignore_index=True)
            except Exception as e:
                out.append({
                    **item,
                    'decision': 'INPUT ERROR',
                    'risk_level': 'N/A',
                    'recommended_action': 'Correct the input row and retry.',
                    'ml_fraud_probability': None,
                    'operational_risk_score': None,
                    'business_evidence_score': None,
                    'evidence_families': '',
                    'evidence_family_count': 0,
                    'history_state': 'N/A',
                    'transactions_last_1h': None,
                    'transactions_last_24h': None,
                    'new_city': None,
                    'new_device': None,
                    'reasons': str(e),
                    '_original_order': original_order
                })
        return pd.DataFrame(out).sort_values('_original_order', kind='mergesort').drop(columns=['_original_order'], errors='ignore').reset_index(drop=True)
