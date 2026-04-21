import json
from src.logger import logger
from src.forecast_fetcher import forecast_fetcher

ANALYSIS_PROMPT = """Analyze this Polymarket weather market:
Question: "{question}"
Current Yes price: {price} (implied prob)
Forecast consensus probability for this outcome: {forecast_prob}
Liquidity: {volume}
Historical similar markets win rate when forecast edge > 0.18: {hist_edge_winrate}

Decide: BUY, SELL, or HOLD.
Reason step-by-step. Output ONLY JSON: {"action": "BUY", "size_usdc": 2.0, "reason": "...", "confidence": 0.85}"""

class EdgeDetector:
    def __init__(self, config_path="config/config.json", rules_path="config/rules.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        with open(rules_path) as f:
            self.rules = json.load(f)
        
        self.cities = {c["name"]: c for c in self.config["cities"]}

    def find_edges(self, markets):
        edges = []
        for m in markets:
            # 1. Check for Risk-Free Arb (Yes + No sum < 0.98)
            # In production, we'd fetch actual orderbook prices
            # For now, we assume some prices exist in the market object for simplicity
            
            # 2. Check for Statistical Edge vs Forecast
            city_info = self.cities.get(m["city"])
            if city_info:
                # Use a dummy date for example, in real use we'd parse from question
                target_date = "2026-04-25" 
                forecast_prob = forecast_fetcher.get_temperature_probability(
                    city_info["lat"], city_info["lon"], target_date, m["temp_min"], m["temp_max"]
                )
                
                if forecast_prob is not None:
                    # Assume market price is 0.5 if not provided (placeholder)
                    market_price = 0.5 
                    edge = forecast_prob - market_price
                    
                    if edge > self.rules["edge_threshold"]:
                        edges.append({
                            "market": m,
                            "type": "statistical",
                            "forecast_prob": forecast_prob,
                            "market_price": market_price,
                            "edge": edge
                        })
        
        return edges

edge_detector = EdgeDetector()
