#  SentinelPay — AI-Powered Fraud Risk Intelligence Platform

**SentinelPay** is an enterprise-grade credit card fraud risk intelligence platform. It combines calibrated machine learning (XGBoost), past-only behavioral tracking, and an explainable rules-based evidence engine to evaluate transaction authorization requests in real time.

Designed for high-throughput payment systems, SentinelPay provides instant risk scoring, dynamic decisioning (**ALLOW**, **STEP-UP 2FA**, **BLOCK**), and single-click audit-ready PDF investigation reports.

---

##  System Architecture & Data Flow

SentinelPay evaluates authorization requests through a **3-Layer Hybrid Intelligence Pipeline**:

```text
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           1. AUTHORIZATION REQUEST                              │
│              (Single Transaction API  /  CSV Batch Screening Upload)            │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      LAYER 1: BEHAVIORAL FEATURE PIPELINE                       │
│  - Historical Card Profiling (Past-Only Customer Velocity & Amount Stats)       │
│  - Spatial & Geographic Geodesic Distances (Customer Lat/Lon vs. Merchant)      │
│  - Contextual Time Analysis (Deep Night Hours 0–6 AM & High Risk Categories)    │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Engineered Feature Vector
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    LAYER 2: CALIBRATED XGBOOST ML ENGINE                        │
│  - XGBoost Classifier (200 Estimators, Depth 4, Calibrated Learning Rate 0.03)  │
│  - Platt Sigmoid Logit Calibration (Outputs True Fraud Probabilities: 0.0–1.0) │
│  - Validated Operating Performance: ROC-AUC 95.22% | PR-AUC 74.88%               │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ Calibrated Fraud Probability
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   LAYER 3: HYBRID EVIDENCE & DECISION ENGINE                    │
│  - Evidence Signal Evaluation (Amount Ratios, Velocity Spikes, Device/IP Mismatch)│
│  - Combined Operational Risk Score (0.0 to 100.0 Scale)                         │
│                                                                                 │
│      ┌─────────────────────────┬─────────────────────────┬─────────────────┐    │
│      │   LOW RISK (0.0 – 39.9) │  MEDIUM RISK (40 – 69.9)│ HIGH RISK (70+) │    │
│      │      ALLOW (Green)      │   STEP-UP 2FA (Amber)   │   BLOCK (Red)   │    │
│      └─────────────────────────┴─────────────────────────┴─────────────────┘    │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        INVESTIGATION & PDF REPORT ENGINE                        │
│  - Interactive Fraud Investigation Dashboard (/investigation?id=TXN-...)        │
│  - Audit-Ready Fraud Investigation PDF Generator (In-Memory ReportLab Engine)   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

##  Core Features

- **Real-Time Single Screening**: Evaluate single authorization attempts instantly via standard web forms or REST APIs.
- **High-Throughput Batch Processing**: Process multi-transaction CSV files with chronological execution and interactive risk breakdown.
- **Audit-Ready Investigation PDF Reports**: Generate dynamic, one-click PDF fraud reports formatted with executive metrics, visual risk indicator bars, and complete transaction summaries.
- **Validated Model Analytics**: Transparent model health documentation displaying benchmark comparisons across 4 algorithms and exact confusion matrix verification.
- **Docker & Cloud Ready**: Fully Dockerized with `docker-compose` for local team setup, and production-ready for platforms like Render.

---

##  Model Performance & Metrics

Model metrics were evaluated on an untouched future test split of 15,000 credit card transactions at the target 1.00% False Positive Rate operating policy constraint:

| Metric | Validated Score | Operational Target / Context |
| :--- | :--- | :--- |
| **ROC-AUC** | **95.22%** | High discrimination capacity across unseen future transactions |
| **PR-AUC** | **74.88%** | Precision-Recall curve area on imbalanced fraud dataset |
| **Precision** | **76.37%** | High true-positive confidence |
| **Recall** | **59.84%** | Captures majority of fraudulent transactions |
| **F1 Score** | **67.11%** | Harmonic balance between Precision and Recall |
| **False Positive Rate** | **0.95%** | Under strict 1.00% operational policy limit |
| **Brier Score** | **0.0229** | Excellent probability calibration accuracy |

---

##  Project Directory Structure

```text
sentinelpay/
├── app.py                     # Flask Web Application & REST API Endpoints
├── db.py                      # Database Manager (PostgreSQL)
├── engine.py                  # FraudEngine Orchestrator (ML inference pipeline)
├── features.py                # Past-Only Feature Engineering & Behavioral Tracker
├── risk_engine.py             # Hybrid Risk Scoring & Evidence Rules Engine
├── model_spec.py              # Data Schemas & Categorical Options Specification
├── train_model.py             # Model Training, Grid Search & Platt Calibration
│
├── artifacts/                 # Serialized Production Artifacts
│   ├── model.joblib           # Calibrated XGBoost Classifier
│   ├── calibrator.joblib      # Platt Sigmoid Calibrator
│   ├── preprocessor.joblib    # Feature Preprocessing & Scaling Pipeline
│   ├── contract.joblib        # Model Specs, Quantiles & Decision Thresholds
│   ├── reference_data.joblib  # Pre-computed Merchant & City Statistics
│   ├── history_df.joblib      # Customer Historical Dataset
│   └── metadata.json          # Validated Benchmark & Operating Evaluation Report
│
├── templates/                 # Clean HTML Template Views
│   ├── dashboard.html         # Live Risk Intelligence Dashboard
│   ├── index.html             # Single Transaction Risk Assessment
│   ├── investigation.html     # Dedicated Fraud Investigation Report Page
│   ├── batch.html             # Batch CSV Upload & Screening Page
│   └── model.html             # Model Performance & Confusion Matrix Page
│
├── static/                    # Frontend Stylesheets & JavaScript Assets
│   ├── style.css              # Dark Fintech Design System
│   ├── app.js                 # Single Screening Interactions & Session State
│   └── batch.js               # CSV Batch Processing & Interactive Filters
│
├── tests/                     # Automated Test Suite (19/19 Unit Tests Passing)
│   ├── test_sentinelpay_scenarios.py
│   ├── test_csv_batch_robustness.py
│   └── model_health_report.py
│
├── Dockerfile                 # Container Build Configuration
├── docker-compose.yml         # Container Service Manifest (Port 8000)
├── .dockerignore              # Docker Build Exclusions
├── requirements.txt           # Active Python Dependencies (Gunicorn included)
├── README.md                  # System Documentation
└── MODEL_CARD.md              # Machine Learning Performance Card
```

---

##  Quick Start Guide

### Option 1: Run with Docker Compose (Recommended for Teams)

Ensure Docker Desktop is running, then execute:

```bash
docker compose up --build
```
Access the application at: **`http://localhost:8000`**

### Option 2: Local Python Execution

1. **Clone & Install Dependencies**:
   ```bash
   git clone https://github.com/vijayendravarma111/SentinelPay-fraud-intelligence-platform.git
   cd SentinelPay-fraud-intelligence-platform
   pip install -r requirements.txt
   ```

2. **Run Automated Test Suite**:
   ```bash
   python -m unittest discover tests
   ```

3. **Launch SentinelPay Web Server**:
   ```bash
   python app.py
   ```
   Open **`http://127.0.0.1:8000`** in your browser.

---

##  REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /` | `GET` | Live Risk Intelligence Dashboard |
| `GET /screen` | `GET` | Single Transaction Screening UI |
| `GET /investigation?id=<tx_id>` | `GET` | Dedicated Fraud Investigation Report Page |
| `GET /batch` | `GET` | Batch CSV Screening UI |
| `GET /model` | `GET` | Model Performance & Confusion Matrix Page |
| `GET /api/transaction/<tx_id>` | `GET` | Fetch saved transaction record by ID |
| `GET /api/transactions` | `GET` | Fetch recent screening transactions from database |
| `GET /api/options` | `GET` | Fetch dropdown options (cities, merchants, categories, countries) |
| `GET /api/template.csv` | `GET` | Download sample CSV template for batch screening |
| `POST /api/analyze` | `POST` | Execute real-time risk analysis on single transaction |
| `POST /api/batch` | `POST` | Upload and process CSV batch file chronologically |
| `POST /api/report` | `POST` | Generate and download audit-ready PDF investigation report |
| `POST /api/clear-session` | `POST` | Clear session screening history and database records |

---


