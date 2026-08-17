import sys
import unittest
import json
import io
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.append(str(ROOT))

from app import app
from engine import FraudEngine

class TestCSVBatchParserRobustness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()
        cls.engine = FraudEngine(ROOT)
        
        # Build 100 valid sample rows
        cls.valid_header = "card_id,trans_date_trans_time,amount_inr,merchant_name,merchant_category,channel,ip_country,transaction_city,customer_lat,customer_lon,merchant_lat,merchant_lon,device_id\n"
        rows = []
        for i in range(100):
            card_id = 999000 + (i % 10) + 1
            amt = 500 + i * 150
            rows.append(f"{card_id},2026-08-17 12:00:00,{amt},Amazon India,ecommerce,ECOMMERCE,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-{i:03d}")
        cls.csv_100_valid = cls.valid_header + "\n".join(rows)

    def test_A_100_row_valid_csv(self):
        data = {'file': (io.BytesIO(self.csv_100_valid.encode('utf-8')), 'test_100.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertEqual(json_data['summary']['total_rows'], 100)
        self.assertEqual(json_data['summary']['error_count'], 0)
        self.assertIn('csv', json_data)
        self.assertIsNotNone(json_data['csv'])

    def test_B_missing_header_column(self):
        invalid_header = "card_id,trans_date_trans_time,amount_inr,merchant_name,merchant_category,channel,ip_country,transaction_city,customer_lat,customer_lon,merchant_lat,merchant_lon\n" # Missing device_id
        csv_str = invalid_header + "999001,2026-08-17 12:00:00,1500,Amazon India,ecommerce,ECOMMERCE,India,Mumbai,19.0760,72.8777,19.0780,72.8800\n"
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'test_missing_header.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data['ok'])
        self.assertIn("device_id", json_data['error'])

    def test_C_extra_column_in_row(self):
        # Header has 13 cols, row 2 has 14 cols
        csv_str = self.valid_header + "999001,2026-08-17 12:00:00,1500,Amazon India,ecommerce,ECOMMERCE,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-001\n" + \
                  "999002,2026-08-17 12:05:00,2500,Croma,electronics,POS,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-002,EXTRA_VALUE\n"
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'test_extra_col.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertEqual(json_data['summary']['total_rows'], 2)
        self.assertEqual(json_data['summary']['error_count'], 1)
        self.assertEqual(json_data['rows'][1]['decision'], 'INPUT ERROR')

    def test_D_empty_csv(self):
        data = {'file': (io.BytesIO(b""), 'empty.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 400)
        json_data = res.get_json()
        self.assertFalse(json_data['ok'])
        self.assertIn("empty", json_data['error'].lower())

    def test_E_blank_lines_between_rows(self):
        csv_str = self.valid_header + "\n\n999001,2026-08-17 12:00:00,1500,Amazon India,ecommerce,ECOMMERCE,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-001\n\n\n999002,2026-08-17 12:05:00,2500,Croma,electronics,POS,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-002\n\n"
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'blank_lines.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertEqual(json_data['summary']['total_rows'], 2)

    def test_F_crlf_windows_line_endings(self):
        csv_str = self.valid_header.replace('\n', '\r\n') + "999001,2026-08-17 12:00:00,1500,Amazon India,ecommerce,ECOMMERCE,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-001\r\n"
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'windows_crlf.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertEqual(json_data['summary']['total_rows'], 1)

    def test_G_quoted_merchant_names(self):
        csv_str = self.valid_header + '999001,2026-08-17 12:00:00,1500,"Reliance Digital, India",electronics,ECOMMERCE,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-001\n'
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'quoted.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertEqual(json_data['rows'][0]['merchant_name'], "Reliance Digital, India")

    def test_H_unknown_merchant_category(self):
        csv_str = self.valid_header + '999001,2026-08-17 12:00:00,1500,Unknown Store X,unseen_category,UNKNOWN_CHANNEL,Unknown Country,Unknown City,19.0760,72.8777,19.0780,72.8800,DEV-001\n'
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'unknown_cat.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertIn(json_data['rows'][0]['decision'], ['GENUINE TRANSACTION', 'SUSPICIOUS TRANSACTION', 'FRAUDULENT TRANSACTION'])

    def test_I_whitespace_padding(self):
        csv_str = " card_id , trans_date_trans_time , amount_inr , merchant_name , merchant_category , channel , ip_country , transaction_city , customer_lat , customer_lon , merchant_lat , merchant_lon , device_id \n" + \
                  " 999001 , 2026-08-17 12:00:00 , 1500 , Amazon India , ecommerce , ECOMMERCE , India , Mumbai , 19.0760 , 72.8777 , 19.0780 , 72.8800 , DEV-001 \n"
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'whitespace.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertEqual(json_data['rows'][0]['merchant_name'], "Amazon India")

    def test_J_one_malformed_row_among_valid_rows(self):
        csv_str = self.valid_header + \
                  "999001,2026-08-17 12:00:00,1500,Amazon India,ecommerce,ECOMMERCE,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-001\n" + \
                  "MALFORMED_ROW_MISSING_MOST_COLS\n" + \
                  "999002,2026-08-17 12:05:00,2500,Croma,electronics,POS,India,Mumbai,19.0760,72.8777,19.0780,72.8800,DEV-002\n"
        data = {'file': (io.BytesIO(csv_str.encode('utf-8')), 'one_malformed.csv')}
        res = self.client.post('/api/batch', data=data, content_type='multipart/form-data')
        self.assertEqual(res.status_code, 200)
        json_data = res.get_json()
        self.assertTrue(json_data['ok'])
        self.assertEqual(json_data['summary']['total_rows'], 3)
        self.assertEqual(json_data['summary']['genuine_count'], 2)
        self.assertEqual(json_data['summary']['error_count'], 1)
        self.assertEqual(json_data['rows'][1]['decision'], 'INPUT ERROR')

if __name__ == '__main__':
    unittest.main()
