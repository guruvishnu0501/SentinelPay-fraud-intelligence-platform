import numpy as np
import pandas as pd

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(np.clip(a, 0.0, 1.0)), np.sqrt(np.clip(1.0 - a, 0.0, 1.0)))
    return R * c

def add_model_features(df, train_amount_quantiles=None):
    x = df.copy()
    if isinstance(x, pd.Series):
        x = pd.DataFrame([x])

    for col in ['customer_lat', 'customer_lon', 'merchant_lat', 'merchant_lon', 
                'hours_since_previous', 'implied_travel_speed_kmh', 
                'previous_location_distance_km', 'amount_ratio_to_card_avg', 
                'amount_zscore_to_card']:
        if col in x.columns:
            x[col] = pd.to_numeric(x[col], errors='coerce')

    if 'merchant_distance_km' not in x.columns or x['merchant_distance_km'].isna().all():
        x['merchant_distance_km'] = haversine_km(x['customer_lat'], x['customer_lon'], x['merchant_lat'], x['merchant_lon'])

    amounts = pd.to_numeric(x['amount_inr'], errors='coerce').fillna(0).clip(lower=0)
    if train_amount_quantiles is None:
        q95 = float(amounts.quantile(0.95))
        q99 = float(amounts.quantile(0.99))
    else:
        q95, q99 = train_amount_quantiles

    x['log_amount'] = np.log1p(amounts)
    x['amount_inr_clipped'] = np.clip(amounts, 0, 500000)
    x['amount_p95_flag'] = (amounts >= q95).astype('int8')
    x['amount_p99_flag'] = (amounts >= q99).astype('int8')

    x['foreign_ip_flag'] = (x['ip_country'].fillna('India').astype(str).str.strip() != 'India').astype('int8')

    x['trans_date_trans_time'] = pd.to_datetime(x['trans_date_trans_time'])
    hours = x['trans_date_trans_time'].dt.hour.fillna(12).astype(int)

    x['day_of_week'] = x['trans_date_trans_time'].dt.dayofweek.fillna(0).astype(int)
    x['is_weekend'] = (x['day_of_week'] >= 5).astype('int8')
    x['is_night'] = ((hours < 6) | (hours >= 23)).astype('int8')
    x['is_deep_night'] = ((hours >= 0) & (hours < 6)).astype('int8')

    x['rapid_flag'] = (pd.to_numeric(x.get('hours_since_previous'), errors='coerce').fillna(999) <= 1).astype('int8')
    speed = pd.to_numeric(x.get('implied_travel_speed_kmh'), errors='coerce').fillna(0)
    hrs_prev = pd.to_numeric(x.get('hours_since_previous'), errors='coerce').fillna(999)
    x['very_fast_flag'] = ((speed > 550) & (hrs_prev < 8)).astype('int8')
    x['channel_risk_flag'] = x['channel'].fillna('').astype(str).isin(['ECOMMERCE', 'MOBILE_APP']).astype('int8')

    ratio = pd.to_numeric(x.get('amount_ratio_to_card_avg'), errors='coerce').fillna(1.0)
    x['amount_ratio_log'] = np.log1p(np.clip(ratio, 0, 50))
    x['high_amount_ratio_flag'] = (ratio >= 3.0).astype('int8')

    new_dev = pd.to_numeric(x.get('new_device'), errors='coerce').fillna(0).astype(int)
    new_cty = pd.to_numeric(x.get('new_city'), errors='coerce').fillna(0).astype(int)

    x['new_device_high_amount'] = ((new_dev == 1) & (amounts >= q95)).astype('int8')
    x['new_city_high_amount'] = ((new_cty == 1) & (amounts >= q95)).astype('int8')
    x['night_high_amount'] = ((x['is_night'] == 1) & (x['amount_p95_flag'] == 1)).astype('int8')
    x['rapid_new_city'] = ((x['rapid_flag'] == 1) & (new_cty == 1)).astype('int8')
    x['fast_new_city'] = ((x['very_fast_flag'] == 1) & (new_cty == 1)).astype('int8')

    return x

def normalize_raw_transaction(tx, city_reference):
    x = dict(tx)
    x["card_id"] = str(x["card_id"]).strip()
    x["trans_date_trans_time"] = pd.Timestamp(x["trans_date_trans_time"])
    x["amount_inr"] = float(x["amount_inr"])
    for c in ["customer_lat", "customer_lon", "merchant_lat", "merchant_lon"]:
        x[c] = float(x[c])
    city = str(x["transaction_city"])
    ref = city_reference.get(city, {})
    x["transaction_state"] = str(x.get("transaction_state") or ref.get("transaction_state") or "Unknown")
    x["transaction_zip"] = int(float(x.get("transaction_zip") or ref.get("transaction_zip") or 0))
    x["city_population"] = int(float(x.get("city_population") or ref.get("city_population") or 0))
    for c in ["merchant_name", "merchant_category", "channel", "ip_country", "transaction_city", "device_id"]:
        x[c] = str(x.get(c) or "Unknown")
    return x

def current_behavior_features(tx, history, q95, q99):
    """Compute features derived only from past transactions available before current transaction time."""
    t = pd.Timestamp(tx["trans_date_trans_time"])
    h = history.copy() if history is not None else pd.DataFrame()
    if not h.empty:
        h["trans_date_trans_time"] = pd.to_datetime(h["trans_date_trans_time"], errors="coerce")
        h = h[h["trans_date_trans_time"] < t].sort_values("trans_date_trans_time")
        
    out = dict(tx)
    amount = float(tx["amount_inr"])
    out["hour"] = int(t.hour)
    out["day_of_week"] = int(t.dayofweek)
    out["is_weekend"] = int(t.dayofweek >= 5)
    out["is_night"] = int(t.hour < 6 or t.hour >= 23)
    out["is_deep_night"] = int(0 <= t.hour < 6)
    out["merchant_distance_km"] = float(haversine_km(tx["customer_lat"], tx["customer_lon"], tx["merchant_lat"], tx["merchant_lon"]))
    
    if h.empty:
        out.update({
            "card_transaction_count_before": 0,
            "hours_since_previous": np.nan,
            "new_city": 1,
            "new_device": 1,
            "card_avg_amount_before": np.nan,
            "card_std_amount_before": np.nan,
            "amount_ratio_to_card_avg": np.nan,
            "amount_zscore_to_card": np.nan,
            "txns_last_1h": 0,
            "txns_last_24h": 0,
            "amount_last_1h": 0.0,
            "amount_last_24h": 0.0,
            "previous_location_distance_km": np.nan,
            "implied_travel_speed_kmh": np.nan,
            "hour_deviation_from_usual": np.nan,
            "card_txn_count_merchant_before": 0,
            "card_txn_count_city_before": 0,
            "card_txn_count_device_before": 0
        })
    else:
        times = h.trans_date_trans_time
        delta = (t - times).dt.total_seconds() / 3600
        vals = h.amount_inr.astype(float)
        out["card_transaction_count_before"] = int(len(h))
        out["hours_since_previous"] = float(delta.iloc[-1])
        mean = float(vals.mean())
        std = float(vals.std(ddof=0))
        out["card_avg_amount_before"] = mean
        out["card_std_amount_before"] = std
        out["amount_ratio_to_card_avg"] = amount / mean if mean > 0 else np.nan
        out["amount_zscore_to_card"] = (amount - mean) / std if std > 1e-9 else 0.0
        last1 = delta <= 1
        last24 = delta <= 24
        out["txns_last_1h"] = int(last1.sum())
        out["txns_last_24h"] = int(last24.sum())
        out["amount_last_1h"] = float(vals[last1].sum())
        out["amount_last_24h"] = float(vals[last24].sum())
        out["new_city"] = int(str(tx["transaction_city"]) not in set(h.transaction_city.astype(str)))
        out["new_device"] = int(str(tx["device_id"]) not in set(h.device_id.astype(str)))
        out["previous_location_distance_km"] = float(haversine_km(h.customer_lat.iloc[-1], h.customer_lon.iloc[-1], tx["customer_lat"], tx["customer_lon"]))
        hours = out["hours_since_previous"]
        out["implied_travel_speed_kmh"] = float(out["previous_location_distance_km"] / hours) if hours > 0 else np.nan
        out["hour_deviation_from_usual"] = float(abs(((t.hour - float(h.trans_date_trans_time.dt.hour.mean() + 12) + 24) % 24) - 12))
        out["card_txn_count_merchant_before"] = int((h.merchant_name.astype(str) == str(tx["merchant_name"])).sum())
        out["card_txn_count_city_before"] = int((h.transaction_city.astype(str) == str(tx["transaction_city"])).sum())
        out["card_txn_count_device_before"] = int((h.device_id.astype(str) == str(tx["device_id"])).sum())
        
    f = pd.DataFrame([out])
    f = add_model_features(f, (q95, q99))
    return f.iloc[0].to_dict()
