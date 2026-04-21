from __future__ import annotations

CITIES = {
    "NYC": {"lat": 40.7128, "lon": -74.006, "rmse": 2.5},
    "Chicago": {"lat": 41.8781, "lon": -87.6298, "rmse": 3.0},
    "Dallas": {"lat": 32.78, "lon": -96.80, "rmse": 2.8},
    "Atlanta": {"lat": 33.749, "lon": -84.388, "rmse": 2.2},
    "Miami": {"lat": 25.7617, "lon": -80.1918, "rmse": 1.5}
}

EDGE_THRESHOLD = 0.08
KELLY_FRACTION = 0.15
MAX_TRADE_DOLLARS = 2.0
MAX_MARKET_DOLLARS = 4.0
MAX_TOTAL_EXPOSURE = 50.0
SCAN_INTERVAL_SECONDS = 300
MAX_HOURS_TO_RESOLUTION = 48
SLIPPAGE_TOLERANCE = 0.05
