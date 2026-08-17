# 🛡️ SENTINELPAY — Real-Time Transaction Risk Intelligence Platform

SentinelPay is a hackathon-ready, production-grade fraud risk detection platform that combines **calibrated XGBoost machine learning**, **past-only customer behavioral tracking**, and an **explainable business evidence engine** to evaluate credit card transactions in real time.

---

## 🏆 System Architecture & Hybrid Intelligence Pipeline

SentinelPay evaluates authorization requests through a **3-Layer Hybrid Fraud Intelligence Engine**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Input Authorization                      │
│            (Single API Call  or  CSV Batch Upload)          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Machine Learning & Calibration Engine              │
│  - XGBoost Classifier (ROC-AUC: 95.22%, PR-AUC: 74.88%)     │
│  - Platt Sigmoid Calibration (Calibrated Fraud Probability) │
│  - One-Hot Categorical & Standard Numerical Scaling         │
└──────────────────────────────┬──────────────────────────────┘
                               │ ML Fraud Probability (0.0 – 1.0)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Explainable Business Evidence Engine               │
│  - Evaluates independent anomaly signals across 5 families: │
│    1. Amount Anomalies (High ratio to card average, P95/P99)│
│    2. Time Anomalies (Deep night hours 0-6 AM)              │
│    3. Location Anomalies (Foreign IP, city mismatch)        │
│    4. Device Anomalies (Unrecognized device ID)             │
│    5. Velocity Anomalies (Rapid txns, high travel speed)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Rule Evidence Score & Anomalies
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Operational Risk Decision Engine                   │
│  - Combined Operational Risk Score (0 – 100)                │
│  - LOW RISK (0 – 39.99)    ──► ALLOW                        │
│  - MEDIUM RISK (40 – 69.99) ──► STEP-UP 2FA AUTHENTICATION  │
│  - HIGH RISK (70 – 100)    ──► BLOCK / DECLINE              │
└──────────────────────────────┘
```

---

## 🚀 Quick Start Guide

### Option A: Local Execution (Python 3.11+)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Automated Unit Test Suite**:
   ```bash
   python -m unittest discover tests
   ```

3. **Start SentinelPay Web Application**:
   ```bash
   python app.py
   ```

4. **Access in Browser**:
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

### Option B: Deployment to Vercel (GitHub → Vercel)

SentinelPay is fully configured for serverless deployment on Vercel:

1. **Push your code to GitHub**.
2. **Import project into Vercel**: Connect your GitHub repository to Vercel.
3. **Deploy**: Vercel automatically detects `vercel.json` and `api/index.py` and deploys the Flask application.

Alternatively via Vercel CLI:
```bash
vercel login
vercel deploy
```

---

## 📊 Validated Model Performance Metrics

Metrics were evaluated on an untouched future test split of 100,000 credit card transactions:

| Metric | Validated Score |
| :--- | :--- |
| **ROC-AUC** | **95.22%** |
| **PR-AUC** | **74.88%** |
| **F1 Score** | **67.11%** |
| **Precision** | **76.37%** |
| **Recall** | **59.84%** |
| **False Positive Rate** | **~1.00%** |
| **Brier Score** | **0.0229** |

---

## 📁 Clean Repository Structure

```
New/
├── app.py                     # Flask web server & route registration
├── engine.py                  # FraudEngine orchestration & model loading
├── features.py                # Feature engineering & past-only card history logic
├── risk_engine.py             # OperationalRiskEngine (Evidence & Decision Policy)
├── model_spec.py              # Column schemas & categorical mappings
├── train_model.py             # Model training & Platt calibration script
│
├── api/                       # Vercel serverless entry point
│   └── index.py               # WSGI handler for Vercel Python runtime
│
├── artifacts/                 # Serialized model pipelines & metadata
│   ├── model.joblib           # Trained XGBoost model
│   ├── calibrator.joblib      # Platt sigmoid calibrator
│   ├── preprocessor.joblib    # ColumnTransformer (OneHotEncoder + StandardScaler)
│   ├── contract.joblib        # Quantiles & decision threshold
│   ├── reference_data.joblib  # Fast runtime reference lookups
│   ├── history_df.joblib      # Compressed customer history
│   └── metadata.json          # Model evaluation report
│
├── templates/                 # HTML templates
│   ├── dashboard.html         # Live session analytics dashboard
│   ├── index.html             # Transaction Risk Assessment page
│   ├── batch.html             # Batch CSV Screening page
│   ├── fraud_intelligence.html# Fraud Intelligence overview
│   └── model.html             # Model & Technology documentation
│
├── static/                    # CSS & JavaScript assets
│   ├── style.css              # Dark navy fintech stylesheet
│   ├── app.js                 # Single transaction interactions & session tracking
│   └── batch.js               # CSV batch processing & multi-filtering
│
├── tests/                     # Automated test suite
│   ├── test_sentinelpay_scenarios.py
│   ├── test_csv_batch_robustness.py
│   └── model_health_report.py
│
├── vercel.json                # Vercel deployment routing manifest
├── .vercelignore              # Deployment bundle optimization rules
├── .gitignore                # Git repository ignore rules
├── requirements.txt           # Active runtime dependencies
└── README.md                  # Project documentation
```

---

## 📋 Required CSV Input Schema for Batch Uploads

Batch files uploaded to `/batch` or `POST /api/batch` must contain the following 13 columns:

`card_id, trans_date_trans_time, amount_inr, merchant_name, merchant_category, channel, ip_country, transaction_city, customer_lat, customer_lon, merchant_lat, merchant_lon, device_id`

---

## 🔌 API Endpoints

- `GET /` — Live Session Dashboard UI
- `GET /screen` — Single Transaction Risk Assessment UI
- `GET /batch` — Batch CSV Screening UI
- `GET /fraud-intelligence` — Fraud Intelligence Overview
- `GET /model` — Model & Technology Documentation
- `GET /api/options` — Form options metadata (cities, merchants, channels, countries)
- `GET /api/template.csv` — Downloadable input CSV template
- `POST /api/analyze` — Single transaction risk analysis endpoint
- `POST /api/batch` — CSV batch screening endpoint (chronological execution)
- `POST /api/report` — One-click downloadable PDF risk report

---

## ⚠️ Prototype Disclaimer

*SentinelPay is an AI-assisted transaction risk screening prototype. Metrics were evaluated on the project's benchmark dataset and are intended for demonstration and evaluation purposes.*
