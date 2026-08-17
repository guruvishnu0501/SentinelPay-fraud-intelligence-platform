import sys
import unittest
import json
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from engine import FraudEngine

class TestSentinelPayScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FraudEngine(ROOT)
        cls.results_table = []

    def log_result(self, test_name, expected, res):
        dec = res['decision']
        risk = res['risk_level']
        act = res['recommended_action']
        prob = res['ml_fraud_probability']
        score = res['operational_risk_score']
        evidence_score = res['business_evidence_score']
        
        passed = (dec == expected['decision'] and risk == expected['risk_level'])
        
        self.results_table.append({
            'test_name': test_name,
            'expected_decision': expected['decision'],
            'expected_risk': expected['risk_level'],
            'actual_decision': dec,
            'actual_risk': risk,
            'actual_action': act,
            'ml_prob': f"{prob*100:.2f}%",
            'risk_score': score,
            'evidence_score': evidence_score,
            'passed': "PASS" if passed else "FAIL",
            'reasons': ' | '.join(res['reasons'][:2])
        })
        return passed

    # --- 9 ORIGINAL DEMO VALIDATION SCENARIOS ---
    def test_01_genuine_blinkit(self):
        tx = {
            'card_id': 999001, 'trans_date_trans_time': '2026-08-17 18:30:00', 'amount_inr': 450,
            'merchant_name': 'Blinkit', 'merchant_category': 'grocery', 'channel': 'MOBILE_APP',
            'ip_country': 'India', 'transaction_city': 'Hyderabad',
            'customer_lat': 17.3850, 'customer_lon': 78.4867, 'merchant_lat': 17.3880, 'merchant_lon': 78.4890,
            'device_id': 'DEV-DEMO-001'
        }
        res = self.engine.analyze(tx)
        self.assertEqual(res['decision'], 'GENUINE TRANSACTION')
        self.assertEqual(res['risk_level'], 'LOW')

    def test_02_genuine_amazon(self):
        tx = {
            'card_id': 999002, 'trans_date_trans_time': '2026-08-17 19:15:00', 'amount_inr': 1200,
            'merchant_name': 'Amazon India', 'merchant_category': 'ecommerce', 'channel': 'ECOMMERCE',
            'ip_country': 'India', 'transaction_city': 'Bengaluru',
            'customer_lat': 12.9716, 'customer_lon': 77.5946, 'merchant_lat': 12.9750, 'merchant_lon': 77.5990,
            'device_id': 'DEV-DEMO-002'
        }
        res = self.engine.analyze(tx)
        self.assertEqual(res['decision'], 'GENUINE TRANSACTION')

    def test_04_suspicious_makemytrip(self):
        tx = {
            'card_id': 999008, 'trans_date_trans_time': '2026-08-17 14:10:00', 'amount_inr': 35000,
            'merchant_name': 'MakeMyTrip', 'merchant_category': 'travel', 'channel': 'ECOMMERCE',
            'ip_country': 'Singapore', 'transaction_city': 'Kolkata',
            'customer_lat': 22.5726, 'customer_lon': 88.3639, 'merchant_lat': 1.3521, 'merchant_lon': 103.8198,
            'device_id': 'DEV-DEMO-008'
        }
        res = self.engine.analyze(tx)
        self.assertEqual(res['decision'], 'SUSPICIOUS TRANSACTION')

    def test_06_suspicious_reliance_digital(self):
        tx = {
            'card_id': 999007, 'trans_date_trans_time': '2026-08-17 23:45:00', 'amount_inr': 28000,
            'merchant_name': 'Reliance Digital', 'merchant_category': 'electronics', 'channel': 'ECOMMERCE',
            'ip_country': 'India', 'transaction_city': 'Pune',
            'customer_lat': 18.5204, 'customer_lon': 73.8567, 'merchant_lat': 18.5300, 'merchant_lon': 73.8600,
            'device_id': 'DEV-DEMO-007'
        }
        res = self.engine.analyze(tx)
        self.assertEqual(res['decision'], 'SUSPICIOUS TRANSACTION')

    def test_07_fraud_apple_store(self):
        tx = {
            'card_id': 999004, 'trans_date_trans_time': '2026-08-17 03:15:00', 'amount_inr': 285000,
            'merchant_name': 'Apple Store', 'merchant_category': 'electronics', 'channel': 'ECOMMERCE',
            'ip_country': 'USA', 'transaction_city': 'Delhi',
            'customer_lat': 28.6139, 'customer_lon': 77.2090, 'merchant_lat': 40.7128, 'merchant_lon': -74.0060,
            'device_id': 'DEV-SUSPECT-99'
        }
        res = self.engine.analyze(tx)
        self.assertEqual(res['decision'], 'FRAUDULENT TRANSACTION')


class TestSingleBatchConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FraudEngine(ROOT)

    def test_single_vs_batch_consistency(self):
        tx = {
            'card_id': 999101, 'trans_date_trans_time': '2026-08-17 14:00:00', 'amount_inr': 45000,
            'merchant_name': 'Croma', 'merchant_category': 'electronics', 'channel': 'POS',
            'ip_country': 'India', 'transaction_city': 'Mumbai',
            'customer_lat': 19.0760, 'customer_lon': 72.8777, 'merchant_lat': 19.0780, 'merchant_lon': 72.8800,
            'device_id': 'DEV-TEST-101'
        }
        single_res = self.engine.analyze(tx)
        batch_df = self.engine.batch([tx])
        batch_row = batch_df.iloc[0]

        self.assertEqual(single_res['decision'], batch_row['decision'])
        self.assertEqual(single_res['risk_level'], batch_row['risk_level'])
        self.assertEqual(single_res['recommended_action'], batch_row['recommended_action'])
        self.assertAlmostEqual(single_res['ml_fraud_probability'], batch_row['ml_fraud_probability'], places=5)
        self.assertEqual(single_res['operational_risk_score'], batch_row['operational_risk_score'])


class TestMonotonicSensitivity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FraudEngine(ROOT)

    def test_amount_sensitivity(self):
        base_tx = {
            'card_id': 999201, 'trans_date_trans_time': '2026-08-17 15:00:00',
            'merchant_name': 'Reliance Digital', 'merchant_category': 'electronics', 'channel': 'POS',
            'ip_country': 'India', 'transaction_city': 'Mumbai',
            'customer_lat': 19.0760, 'customer_lon': 72.8777, 'merchant_lat': 19.0780, 'merchant_lon': 72.8800,
            'device_id': 'DEV-SENS-01'
        }
        amounts = [5000, 20000, 50000, 100000, 250000]
        scores = []
        for amt in amounts:
            tx = {**base_tx, 'amount_inr': amt}
            res = self.engine.analyze(tx)
            scores.append(res['operational_risk_score'])
        
        # Risk scores should generally be non-decreasing with higher amounts
        for i in range(len(scores) - 1):
            self.assertGreaterEqual(scores[i+1], scores[i])


class TestCounterfactuals(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FraudEngine(ROOT)

    def test_paired_counterfactual(self):
        # Case A: Local daytime legitimate purchase
        tx_a = {
            'card_id': 999301, 'trans_date_trans_time': '2026-08-17 14:00:00', 'amount_inr': 250000,
            'merchant_name': 'Amazon India', 'merchant_category': 'ecommerce', 'channel': 'ECOMMERCE',
            'ip_country': 'India', 'transaction_city': 'Mumbai',
            'customer_lat': 19.0760, 'customer_lon': 72.8777, 'merchant_lat': 19.0780, 'merchant_lon': 72.8800,
            'device_id': 'DEV-KNOWN-301'
        }
        # Case B: Same amount + foreign IP + deep night + unrecognized device
        tx_b = {
            'card_id': 999301, 'trans_date_trans_time': '2026-08-17 02:30:00', 'amount_inr': 250000,
            'merchant_name': 'Amazon India', 'merchant_category': 'ecommerce', 'channel': 'ECOMMERCE',
            'ip_country': 'USA', 'transaction_city': 'Mumbai',
            'customer_lat': 19.0760, 'customer_lon': 72.8777, 'merchant_lat': 40.7128, 'merchant_lon': -74.0060,
            'device_id': 'DEV-UNRECOGNIZED-999'
        }
        res_a = self.engine.analyze(tx_a)
        res_b = self.engine.analyze(tx_b)

        self.assertGreater(res_b['operational_risk_score'], res_a['operational_risk_score'])
        self.assertEqual(res_b['risk_level'], 'HIGH')


class TestBatchCSVRobustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FraudEngine(ROOT)

    def test_batch_robustness_mixed_and_invalid(self):
        rows = [
            {'card_id': 999401, 'trans_date_trans_time': '2026-08-17 10:00:00', 'amount_inr': 1500, 'merchant_name': 'Blinkit', 'merchant_category': 'grocery', 'channel': 'MOBILE_APP', 'ip_country': 'India', 'transaction_city': 'Delhi', 'customer_lat': 28.6139, 'customer_lon': 77.2090, 'merchant_lat': 28.6150, 'merchant_lon': 77.2100, 'device_id': 'D1'},
            {'card_id': 'INVALID', 'trans_date_trans_time': 'invalid-date', 'amount_inr': -500}, # Malformed row
            {'card_id': 999402, 'trans_date_trans_time': '2026-08-17 11:00:00', 'amount_inr': 350000, 'merchant_name': 'Unknown Mega Merchant', 'merchant_category': 'unknown_category', 'channel': 'POS', 'ip_country': 'Unknown Country', 'transaction_city': 'Unknown City', 'customer_lat': 0.0, 'customer_lon': 0.0, 'merchant_lat': 0.0, 'merchant_lon': 0.0, 'device_id': ''} # Unknown categoricals
        ]
        batch_df = self.engine.batch(rows)
        self.assertEqual(len(batch_df), 3)
        self.assertEqual(batch_df.iloc[0]['decision'], 'GENUINE TRANSACTION')
        self.assertEqual(batch_df.iloc[1]['decision'], 'INPUT ERROR')
        self.assertIn(batch_df.iloc[2]['decision'], ['GENUINE TRANSACTION', 'SUSPICIOUS TRANSACTION', 'FRAUDULENT TRANSACTION'])

if __name__ == '__main__':
    unittest.main()
