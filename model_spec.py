CAT_COLS = [
    "merchant_name", "merchant_category", "channel", "ip_country", "transaction_city", "transaction_state"
]

NUM_COLS = [
    "log_amount", "amount_inr_clipped", "transaction_zip", "city_population",
    "merchant_distance_km", "previous_location_distance_km", "implied_travel_speed_kmh",
    "hour", "day_of_week", "is_weekend", "is_night", "is_deep_night",
    "card_transaction_count_before", "hours_since_previous", "new_city", "new_device",
    "card_avg_amount_before", "card_std_amount_before", "amount_ratio_to_card_avg", "amount_zscore_to_card",
    "txns_last_1h", "txns_last_24h", "amount_last_1h", "amount_last_24h",
    "hour_deviation_from_usual", "card_txn_count_merchant_before", "card_txn_count_city_before",
    "card_txn_count_device_before", "amount_p95_flag", "amount_p99_flag", "foreign_ip_flag",
    "rapid_flag", "very_fast_flag", "channel_risk_flag", "amount_ratio_log",
    "new_device_high_amount", "new_city_high_amount", "night_high_amount", "rapid_new_city", "fast_new_city"
]

INPUT_COLS = [
    "card_id", "trans_date_trans_time", "amount_inr", "merchant_name", "merchant_category",
    "channel", "ip_country", "transaction_city", "customer_lat", "customer_lon",
    "merchant_lat", "merchant_lon", "device_id"
]

OPTIONAL_INPUT_COLS = ["transaction_state", "transaction_zip", "city_population"]
