import requests
import re
from src.logger import logger

class MarketScanner:
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com/markets"

    def scan_weather_markets(self):
        """
        Scans for weather-related markets on Polymarket.
        Filters for 'temperature', city names, and active status.
        """
        params = {
            "active": "true",
            "closed": "false",
            "limit": 100
        }
        
        try:
            response = requests.get(self.gamma_api_url, params=params, timeout=20)
            response.raise_for_status()
            markets = response.json()
            
            weather_markets = []
            keywords = ["temperature", "highest", "lowest", "degrees", "celsius", "fahrenheit"]
            
            for m in markets:
                question = m.get("question", "").lower()
                if any(k in question for k in keywords):
                    parsed = self.parse_market_details(m)
                    if parsed:
                        weather_markets.append(parsed)
            
            logger.log_action("SCAN_COMPLETE", {"found_count": len(weather_markets)})
            return weather_markets
            
        except Exception as e:
            logger.log_action("SCAN_EXCEPTION", {"error": str(e)})
            return []

    def parse_market_details(self, market):
        """
        Extracts City, Date, and Temperature Range from the market question.
        Example: "Will the temperature in Chicago be 80-84 degrees on April 25?"
        """
        question = market.get("question", "")
        # Very basic regex parser - in production this would be more robust or use LLM parsing
        city_match = re.search(r"in ([\w\s]+)", question)
        range_match = re.search(r"(\d+)-(\d+)", question)
        date_match = re.search(r"on (\w+ \d+)", question)
        
        if not (city_match and range_match):
            return None
            
        return {
            "id": market.get("id"),
            "question": question,
            "city": city_match.group(1).strip(),
            "temp_min": float(range_match.group(1)),
            "temp_max": float(range_match.group(2)),
            "tokens": market.get("tokens"),
            "clobTokenIds": market.get("clobTokenIds"),
            "outcomes": market.get("outcomes"),
            "market_slug": market.get("marketSlug")
        }

market_scanner = MarketScanner()
