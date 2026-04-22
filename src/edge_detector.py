import json
from logger import logger
from forecast_fetcher import forecast_fetcher
import config

ANALYSIS_PROMPT = """Analyze this Polymarket weather market:
Question: "{question}"
Current Yes price: {price} (implied prob)
Forecast consensus probability for this outcome: {forecast_prob}
Liquidity: {volume}
Historical similar markets win rate when forecast edge > 0.18: {hist_edge_winrate}

Decide: BUY, SELL, or HOLD.
Reason step-by-step. Output ONLY JSON: {"action": "BUY", "size_usdc": 2.0, "reason": "...", "confidence": 0.85}"""

class EdgeDetector:
    def __init__(self):
        self.cfg = config.get_config()
        self.rules = config.get_rules()
        self.cities = config.CITIES

    def find_edges(self, markets):
        edges = []
        for m in markets:
            # 1. Check for Statistical Edge vs Forecast
            city_key = m.get("city")
            city_info = self.cities.get(city_key)
            
            if city_info:
                # Use a dummy date for example, in real use we'd parse from question
                target_date = "2026-04-25" 
                
                # Determine if we should use Fahrenheit (default for US cities)
                is_fahrenheit = True
                if city_key in ["London", "Tokyo"] or "Celsius" in m.get("title", ""):
                    is_fahrenheit = False
                
                forecast_prob = forecast_fetcher.get_temperature_probability(
                    city_info["lat"], city_info["lon"], target_date, m["min_temp"], m["max_temp"], is_fahrenheit=is_fahrenheit
                )
                
                if forecast_prob is not None:
                    # Fetch market price
                    tokens = m.get("tokens", [])
                    market_price = float(tokens[0].get("price", 0.5)) if tokens else 0.5
                    
                    edge = forecast_prob - market_price
                    
                    if edge > self.rules.get("edge_threshold", 0.08):
                        edges.append({
                            "market": m,
                            "type": "statistical",
                            "forecast_prob": forecast_prob,
                            "market_price": market_price,
                            "edge": edge
                        })
        
        return edges

edge_detector = EdgeDetector()
