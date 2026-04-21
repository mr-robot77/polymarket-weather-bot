from __future__ import annotations
import requests
import re
from typing import List, Dict, Any

class PolymarketClient:
    def __init__(self) -> None:
        self.gamma_api = "https://gamma-api.polymarket.com/events"
    
    def fetch_active_temperature_markets(self, pages: int = 30) -> List[Dict[str, Any]]:
        markets = []
        for page in range(pages):
            params: Dict[str, Any] = {
                "limit": 100,
                "offset": page * 100,
                "active": "true",
                "closed": "false"
            }
            try:
                resp = requests.get(self.gamma_api, params=params, timeout=10)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                
                for event in data:
                    title = event.get("title", "").lower()
                    if "temperature" in title or "high" in title or "low" in title:
                        markets.append(event)
            except requests.RequestException:
                break
        return markets

    def parse_market_details(self, title: str) -> Dict[str, Any]:
        details: Dict[str, Any] = {"city": "Unknown", "date": "Unknown", "min_temp": None, "max_temp": None}
        
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
            details["min_temp"] = float(range_match.group(1))
            details["max_temp"] = float(range_match.group(2))
        elif "above" in title.lower() or "higher" in title.lower() or "more than" in title.lower():
            val_match = re.search(r"(?:above|higher than|more than)\s+(\d+)", title, re.IGNORECASE)
            if not val_match:
                val_match = re.search(r"(\d+)(?:°F|°C|F|C)?\s+(?:or above|or higher)", title, re.IGNORECASE)
            if val_match:
                details["min_temp"] = float(val_match.group(1))
                details["max_temp"] = float("inf")
        elif "below" in title.lower() or "lower" in title.lower() or "less than" in title.lower():
            val_match = re.search(r"(?:below|lower than|less than)\s+(\d+)", title, re.IGNORECASE)
            if not val_match:
                val_match = re.search(r"(\d+)(?:°F|°C|F|C)?\s+(?:or below|or lower)", title, re.IGNORECASE)
            if val_match:
                details["min_temp"] = float("-inf")
                details["max_temp"] = float(val_match.group(1))
                
        return details
