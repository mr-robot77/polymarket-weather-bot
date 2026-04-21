import requests
import re
from logger import logger

class MarketScanner:
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com/events"

    def scan_weather_markets(self, pages=30):
        """
        Scans for weather-related markets on Polymarket.
        Filters for 'temperature', city names, and active status.
        """
        weather_markets = []
        keywords = ["temperature", "highest", "lowest", "degrees", "celsius", "fahrenheit", "high", "low"]
        
        try:
            for page in range(pages):
                params = {
                    "active": "true",
                    "closed": "false",
                    "limit": 100,
                    "offset": page * 100
                }
                response = requests.get(self.gamma_api_url, params=params, timeout=20)
                if response.status_code != 200:
                    break
                markets = response.json()
                if not markets:
                    break
                
                for m in markets:
                    title = m.get("title", "").lower()
                    if any(k in title for k in keywords):
                        parsed = self.parse_market_details(m)
                        if parsed:
                            weather_markets.append(parsed)
            
            logger.log_action("SCAN_COMPLETE", {"found_count": len(weather_markets)})
            return weather_markets
            
        except Exception as e:
            logger.log_action("SCAN_EXCEPTION", {"error": str(e)})
            return weather_markets

    def parse_market_details(self, market):
        """
        Extracts City, Date, and Temperature Range from the market title.
        """
        title = market.get("title", "")
        details = {
            "id": market.get("id"),
            "question": title,
            "title": title,
            "city": "Unknown",
            "date": "Unknown",
            "temp_min": None,
            "temp_max": None,
            "tokens": market.get("tokens"),
            "clobTokenIds": market.get("clobTokenIds"),
            "outcomes": market.get("outcomes"),
            "market_slug": market.get("slug")
        }
        
        # Parse city
        from config import CITIES
        for c in CITIES.keys():
            if c.lower() in title.lower():
                details["city"] = c
                break
                
        # Parse date
        date_match = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d+", title, re.IGNORECASE)
        if date_match:
            details["date"] = date_match.group(0).title()
            
        # Parse range
        range_match = re.search(r"(\d+)-(\d+)", title)
        if range_match:
            details["temp_min"] = float(range_match.group(1))
            details["temp_max"] = float(range_match.group(2))
        elif "above" in title.lower() or "higher" in title.lower() or "more than" in title.lower():
            val_match = re.search(r"(?:above|higher than|more than)\s+(\d+)", title, re.IGNORECASE)
            if not val_match:
                val_match = re.search(r"(\d+)(?:°F|°C|F|C)?\s+(?:or above|or higher)", title, re.IGNORECASE)
            if val_match:
                details["temp_min"] = float(val_match.group(1))
                details["temp_max"] = float("inf")
        elif "below" in title.lower() or "lower" in title.lower() or "less than" in title.lower():
            val_match = re.search(r"(?:below|lower than|less than)\s+(\d+)", title, re.IGNORECASE)
            if not val_match:
                val_match = re.search(r"(\d+)(?:°F|°C|F|C)?\s+(?:or below|or lower)", title, re.IGNORECASE)
            if val_match:
                details["temp_min"] = float("-inf")
                details["temp_max"] = float(val_match.group(1))
                
        return details

market_scanner = MarketScanner()
