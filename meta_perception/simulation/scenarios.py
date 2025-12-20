"""Stress scenario definitions."""
import numpy as np

STRESS_SCENARIOS = {
    "flash_crash": {
        "description": "50% price drop in 5 minutes",
        "expected_behavior": {
            "should_act": False,
            "alert_operator": True,
            "recommended_risk_mode": "DEFENSIVE"
        }
    },
    "funding_explosion": {
        "description": "Funding rate spikes to 5%",
        "expected_behavior": {
            "shock_events_count": 1,
            "shock_severity": "CRITICAL"
        }
    }
}

def generate_flash_crash_data():
    """Generate flash crash scenario data."""
    prices = list(range(50000, 25000, -500))  # 50% drop
    return {"BTC": prices, "ETH": [p * 0.06 for p in prices]}

def generate_funding_explosion_data():
    """Generate funding explosion data."""
    normal = [0.0001] * 95
    spike = [0.05] * 5  # 5% funding
    return {"BTC": [50000.0] * 100, "funding_rate": normal + spike}
