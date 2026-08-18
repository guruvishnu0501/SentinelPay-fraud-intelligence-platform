import os
import json
import logging
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "sentinelpay_db")

logger = logging.getLogger("sentinelpay.db")

def _safe_float(val, default=0.0):
    if val is None or val == "":
        return default
    try:
        import math
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default

def _safe_str(val, default=""):
    if val is None:
        return default
    return str(val)

class DatabaseManager:
    """
    Resilient Database Manager supporting MySQL with automatic SQLite fallback.
    Ensures zero application downtime regardless of database availability.
    """
    def __init__(self):
        self.use_mysql = False
        self.db_path = self._resolve_sqlite_db_path()
        self._init_db()

    def _resolve_sqlite_db_path(self):
        # 1. Direct file path from environment variable
        for env_var in ["SENTINELPAY_DB_PATH", "DB_PATH"]:
            val = os.getenv(env_var)
            if val:
                p = Path(val)
                target = p if p.suffix == ".db" else p / "sentinelpay.db"
                target.parent.mkdir(parents=True, exist_ok=True)
                return target

        # 2. Directory path from environment variable (e.g. Render DATA_DIR=/var/data)
        data_dir = os.getenv("DATA_DIR")
        if data_dir:
            p = Path(data_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p / "sentinelpay.db"

        # 3. Standard Render persistent disk mount locations
        for mount in [Path("/var/data"), Path("/data")]:
            if mount.exists() and os.access(mount, os.W_OK):
                return mount / "sentinelpay.db"

        # 4. Fallback to local application directory
        local_path = Path(__file__).parent / "sentinelpay.db"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return local_path

    def _get_sqlite_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    def _get_mysql_connection(self, select_db=True):
        import pymysql
        kwargs = {
            "host": MYSQL_HOST,
            "port": MYSQL_PORT,
            "user": MYSQL_USER,
            "password": MYSQL_PASSWORD,
            "autocommit": True,
            "cursorclass": pymysql.cursors.DictCursor
        }
        if select_db:
            kwargs["database"] = MYSQL_DB
        return pymysql.connect(**kwargs)

    def _init_db(self):
        # Try MySQL initialization first
        if MYSQL_PASSWORD:
            try:
                import pymysql
                # Connect without database to ensure database exists
                conn = self._get_mysql_connection(select_db=False)
                with conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DB}` CHARACTER SET utf8mb4;")
                conn.close()

                # Connect to sentinelpay_db and create table
                conn = self._get_mysql_connection(select_db=True)
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS transactions (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            transaction_id VARCHAR(64) UNIQUE,
                            card_id VARCHAR(64),
                            trans_date_trans_time VARCHAR(64),
                            amount_inr DOUBLE,
                            merchant_name VARCHAR(255),
                            merchant_category VARCHAR(100),
                            channel VARCHAR(50),
                            ip_country VARCHAR(100),
                            transaction_city VARCHAR(100),
                            device_id VARCHAR(100),
                            ml_fraud_probability DOUBLE,
                            operational_risk_score DOUBLE,
                            risk_level VARCHAR(20),
                            decision VARCHAR(50),
                            recommended_action VARCHAR(100),
                            reasons TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                    """)
                conn.close()
                self.use_mysql = True
                logger.info(f"MySQL initialized successfully on database '{MYSQL_DB}'")
                return
            except Exception as e:
                logger.warning(f"MySQL initialization failed ({e}). Falling back to SQLite.")

        # Fallback SQLite initialization
        try:
            conn = self._get_sqlite_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT UNIQUE,
                    card_id TEXT,
                    trans_date_trans_time TEXT,
                    amount_inr REAL,
                    merchant_name TEXT,
                    merchant_category TEXT,
                    channel TEXT,
                    ip_country TEXT,
                    transaction_city TEXT,
                    device_id TEXT,
                    ml_fraud_probability REAL,
                    operational_risk_score REAL,
                    risk_level TEXT,
                    decision TEXT,
                    recommended_action TEXT,
                    reasons TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
            logger.info(f"SQLite database initialized at '{self.db_path}'")
        except Exception as e:
            logger.error(f"SQLite initialization failed: {e}")

    def save_transaction(self, tx_res):
        """Save a single analyzed transaction result."""
        if not tx_res or not isinstance(tx_res, dict):
            return

        reasons_json = json.dumps(tx_res.get("reasons", []))
        
        tx_id = _safe_str(tx_res.get("transaction_id", ""))
        card_id = _safe_str(tx_res.get("card_id", ""))
        trans_time = _safe_str(tx_res.get("trans_date_trans_time", ""))
        amount_inr = _safe_float(tx_res.get("amount_inr"))
        merchant_name = _safe_str(tx_res.get("merchant_name"))
        merchant_category = _safe_str(tx_res.get("merchant_category"))
        channel = _safe_str(tx_res.get("channel"))
        ip_country = _safe_str(tx_res.get("ip_country"))
        transaction_city = _safe_str(tx_res.get("transaction_city"))
        device_id = _safe_str(tx_res.get("device_id"))
        ml_prob = _safe_float(tx_res.get("ml_fraud_probability"))
        op_score = _safe_float(tx_res.get("operational_risk_score"))
        risk_level = _safe_str(tx_res.get("risk_level"))
        decision = _safe_str(tx_res.get("decision"))
        action = _safe_str(tx_res.get("recommended_action"))

        if self.use_mysql:
            try:
                conn = self._get_mysql_connection(select_db=True)
                with conn.cursor() as cursor:
                    sql = """
                        INSERT INTO transactions (
                            transaction_id, card_id, trans_date_trans_time, amount_inr,
                            merchant_name, merchant_category, channel, ip_country,
                            transaction_city, device_id, ml_fraud_probability,
                            operational_risk_score, risk_level, decision,
                            recommended_action, reasons
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            operational_risk_score = VALUES(operational_risk_score),
                            risk_level = VALUES(risk_level),
                            decision = VALUES(decision);
                    """
                    cursor.execute(sql, (
                        tx_id, card_id, trans_time, amount_inr,
                        merchant_name, merchant_category, channel, ip_country,
                        transaction_city, device_id, ml_prob,
                        op_score, risk_level, decision,
                        action, reasons_json
                    ))
                conn.close()
                return
            except Exception as e:
                logger.error(f"Failed to save transaction to MySQL: {e}")

        # SQLite Fallback
        try:
            conn = self._get_sqlite_connection()
            cursor = conn.cursor()
            sql = """
                INSERT OR REPLACE INTO transactions (
                    transaction_id, card_id, trans_date_trans_time, amount_inr,
                    merchant_name, merchant_category, channel, ip_country,
                    transaction_city, device_id, ml_fraud_probability,
                    operational_risk_score, risk_level, decision,
                    recommended_action, reasons
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            cursor.execute(sql, (
                tx_id, card_id, trans_time, amount_inr,
                merchant_name, merchant_category, channel, ip_country,
                transaction_city, device_id, ml_prob,
                op_score, risk_level, decision,
                action, reasons_json
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save transaction to SQLite: {e}")

    def save_batch_transactions(self, tx_list):
        """Save a list of analyzed transaction results from batch CSV processing."""
        if not tx_list:
            return
        for tx_res in tx_list:
            self.save_transaction(tx_res)

    def _row_to_dict(self, row):
        if not row:
            return None
        # Handle dict (MySQL) or tuple (SQLite)
        if isinstance(row, dict):
            d = dict(row)
        else:
            cols = ["id", "transaction_id", "card_id", "trans_date_trans_time", "amount_inr",
                    "merchant_name", "merchant_category", "channel", "ip_country",
                    "transaction_city", "device_id", "ml_fraud_probability",
                    "operational_risk_score", "risk_level", "decision",
                    "recommended_action", "reasons", "created_at"]
            d = dict(zip(cols, row))
        
        reasons_val = d.get("reasons")
        if isinstance(reasons_val, str):
            try:
                d["reasons"] = json.loads(reasons_val)
            except Exception:
                d["reasons"] = [reasons_val] if reasons_val else []
        elif not isinstance(reasons_val, list):
            d["reasons"] = []
            
        return d

    def get_transaction(self, tx_id):
        """Retrieve a saved transaction by transaction_id."""
        if not tx_id:
            return None

        if self.use_mysql:
            try:
                conn = self._get_mysql_connection(select_db=True)
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM transactions WHERE transaction_id = %s LIMIT 1", (tx_id,))
                    row = cursor.fetchone()
                conn.close()
                return self._row_to_dict(row) if row else None
            except Exception as e:
                logger.error(f"Failed to fetch transaction from MySQL: {e}")

        # SQLite Fallback
        try:
            conn = self._get_sqlite_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions WHERE transaction_id = ? LIMIT 1", (tx_id,))
            row = cursor.fetchone()
            conn.close()
            return self._row_to_dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to fetch transaction from SQLite: {e}")
        return None

    def get_recent_transactions(self, limit=1000):
        """Retrieve recent saved transactions."""
        results = []
        if self.use_mysql:
            try:
                conn = self._get_mysql_connection(select_db=True)
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT %s", (limit,))
                    rows = cursor.fetchall()
                conn.close()
                return [self._row_to_dict(r) for r in rows if r]
            except Exception as e:
                logger.error(f"Failed to fetch recent transactions from MySQL: {e}")

        # SQLite Fallback
        try:
            conn = self._get_sqlite_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [self._row_to_dict(r) for r in rows if r]
        except Exception as e:
            logger.error(f"Failed to fetch recent transactions from SQLite: {e}")
        return results

    def clear_transactions(self):
        """Clear all stored transactions for session reset."""
        if self.use_mysql:
            try:
                conn = self._get_mysql_connection(select_db=True)
                with conn.cursor() as cursor:
                    cursor.execute("TRUNCATE TABLE transactions;")
                conn.close()
                return
            except Exception as e:
                logger.error(f"Failed to clear transactions from MySQL: {e}")
        try:
            conn = self._get_sqlite_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transactions;")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to clear transactions from SQLite: {e}")

# Instantiate singleton DB manager
db_manager = DatabaseManager()

