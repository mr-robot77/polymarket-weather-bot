import json
import os
import logging

# Path to config files
CONFIG_PATH = "config/config.json"
RULES_PATH = "config/rules.json"

def get_config():
    """Returns the base configuration from config.json."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading config.json: {e}")
    return {}

def get_cities():
    """Returns the cities configuration, reloading from config.json if possible."""
    cfg = get_config()
    return cfg.get("cities", {})

# Initial load for static constants
_initial_config = get_config()

# For backward compatibility, but code should prefer get_cities()
CITIES = _initial_config.get("cities", {})
SCAN_INTERVAL_SECONDS = _initial_config.get("scan_interval_seconds", 300)

# Default Rules (can be overridden by rules.json)
EDGE_THRESHOLD = 0.08
KELLY_FRACTION = 0.15
MAX_TRADE_DOLLARS = 2.0
MAX_MARKET_DOLLARS = 4.0
MAX_TOTAL_EXPOSURE = 50.0
MAX_HOURS_TO_RESOLUTION = 48
SLIPPAGE_TOLERANCE = 0.05

def get_rules():
    """
    Returns the current active rules, merging static defaults with dynamic rules.json.
    """
    defaults = {
        "edge_threshold": EDGE_THRESHOLD,
        "kelly_fraction": KELLY_FRACTION,
        "max_trade_dollars": MAX_TRADE_DOLLARS,
        "max_market_dollars": MAX_MARKET_DOLLARS,
        "max_total_exposure": MAX_TOTAL_EXPOSURE,
        "blacklist": []
    }
    
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH, "r") as f:
                dynamic_rules = json.load(f)
                return {**defaults, **dynamic_rules}
        except Exception as e:
            logging.error(f"Error loading rules.json: {e}")
    return defaults
