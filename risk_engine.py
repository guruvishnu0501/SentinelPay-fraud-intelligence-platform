import math

def evidence(f):
    families = {}
    reasons = []
    score = 0
    
    amount = float(f.get("amount_inr", 0) or 0)
    ratio = f.get("amount_ratio_to_card_avg")
    p95 = int(f.get("amount_p95_flag", 0))
    p99 = int(f.get("amount_p99_flag", 0))
    
    # Amount Evidence
    if p99 or amount >= 100000:
        score += 25
        families["amount"] = 1
        if amount >= 100000:
            reasons.append("High-value transaction exceeding ₹1,00,000.")
        else:
            reasons.append("Transaction amount is in the extreme top 1% of historical distribution.")
    elif amount >= 50000:
        score += 18
        families["amount"] = 1
        reasons.append("High-value transaction exceeding ₹50,000.")
    elif amount >= 40000:
        score += 14
        families["amount"] = 1
        reasons.append("Transaction amount is in the top 5% of historical distribution.")
    elif amount >= 25000 or p95:
        score += 10
        families["amount"] = 1
        reasons.append("Elevated transaction amount exceeding ₹25,000.")
        
    if ratio == ratio and ratio is not None and not math.isnan(ratio):
        if ratio >= 5:
            score += 20
            families["amount"] = 1
            reasons.append(f"Transaction is {ratio:.1f}× the card's historical average amount.")
        elif ratio >= 3:
            score += 12
            families["amount"] = 1
            reasons.append(f"Transaction is {ratio:.1f}× the card's historical average amount.")
            
    # Merchant & Channel Risk
    category = str(f.get("merchant_category", "")).lower()
    channel = str(f.get("channel", "")).upper()
    if category in ["travel", "electronics", "digital_goods"] and amount >= 25000:
        score += 10
        families["merchant"] = 1
        reasons.append(f"High-value transaction in sensitive merchant category ({category.title()}).")
        
    # Time Evidence
    is_deep_night = int(f.get("is_deep_night", 0))
    is_night = int(f.get("is_night", 0))
    if is_deep_night and amount >= 25000:
        score += 18
        families["time"] = 1
        reasons.append("High-value transaction occurred during deep-night hours (00:00–05:59).")
    elif is_night and amount >= 25000:
        score += 10
        families["time"] = 1
        reasons.append("High-value transaction occurred during late-night hours.")
        
    # Velocity Evidence
    tx1 = int(f.get("txns_last_1h", 0) or 0)
    tx24 = int(f.get("txns_last_24h", 0) or 0)
    if tx1 >= 5:
        score += 28
        families["velocity"] = 1
        reasons.append(f"Extreme velocity anomaly ({tx1} transactions within 1 hour).")
    elif tx1 >= 3:
        score += 18
        families["velocity"] = 1
        reasons.append(f"High transaction velocity ({tx1} transactions within 1 hour).")
    elif tx24 >= 8:
        score += 12
        families["velocity"] = 1
        reasons.append(f"High transaction volume ({tx24} transactions within 24 hours).")
        
    # Geographic & IP Evidence
    dist = f.get("previous_location_distance_km")
    speed = f.get("implied_travel_speed_kmh")
    foreign_ip = int(f.get("foreign_ip_flag", 0))
    new_city = int(f.get("new_city", 0))
    
    if speed == speed and speed is not None and not math.isnan(speed) and speed >= 550:
        score += 25
        families["geo"] = 1
        reasons.append(f"Impossible travel speed detected ({speed:.0f} km/h).")
    elif dist == dist and dist is not None and not math.isnan(dist) and dist >= 1500:
        score += 20
        families["geo"] = 1
        reasons.append(f"Large distance from previous transaction ({dist:.0f} km).")
        
    if foreign_ip and new_city:
        score += 22
        families["geo"] = 1
        reasons.append(f"Foreign network IP ({f.get('ip_country', 'Unknown')}) combined with unvisited city.")
    elif foreign_ip:
        score += 12
        families["geo"] = 1
        reasons.append(f"Foreign network IP address ({f.get('ip_country', 'Unknown')}).")
        
    # Device Evidence
    new_device = int(f.get("new_device", 0))
    tx_count_before = int(f.get("card_transaction_count_before", 0))
    if new_device and tx_count_before >= 1:
        score += 12
        families["device"] = 1
        reasons.append("Transaction initiated from a new, unrecognized device.")
        
    # ATM Anomaly
    if channel == "ATM" and foreign_ip:
        score += 15
        families["channel"] = 1
        reasons.append("Overseas ATM transaction detected.")
        
    evidence_score = min(score, 100)
    return evidence_score, families, reasons

def final_decision(prob, evidence_score, families, threshold):
    """
    STRICT HYBRID OPERATIONAL DECISION POLICY:
    
    Operational Risk Score (0-100) = 38% ML Probability Percent + 45% Rule Evidence Score + 17% Anomaly Intensity
    - ML Probability Percent: float in range [0, 100]
    - Rule Evidence Score: float in range [0, 100]
    - Anomaly Intensity Score: min(100, num_families * 20.0) in range [0, 100]
    
    Strict Operational Tier Mapping:
    - LOW    (0.00 to 39.99)  -> GENUINE TRANSACTION              -> ALLOW
    - MEDIUM (40.00 to 69.99) -> SUSPICIOUS TRANSACTION             -> STEP-UP AUTHENTICATION / REVIEW
    - HIGH   (70.00 to 100.0) -> FRAUDULENT TRANSACTION             -> BLOCK
    """
    ml_score = 100.0 * prob
    num_families = len(families)
    anomaly_intensity = min(100.0, num_families * 20.0)
    
    operational_score = min(100.0, max(0.0, 0.38 * ml_score + 0.45 * evidence_score + 0.17 * anomaly_intensity))
    
    if operational_score >= 70.0:
        classification = "FRAUDULENT TRANSACTION"
        risk_level = "HIGH"
        action = "BLOCK"
    elif operational_score >= 40.0:
        classification = "SUSPICIOUS TRANSACTION"
        risk_level = "MEDIUM"
        action = "STEP-UP AUTHENTICATION / REVIEW"
    else:
        classification = "GENUINE TRANSACTION"
        risk_level = "LOW"
        action = "ALLOW"
        
    return classification, risk_level, action, round(operational_score, 2)
