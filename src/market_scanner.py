import requests
import re
import json
from datetime import datetime
from logger import logger

class MarketScanner:
    def __init__(self):
        self.gamma_api_url = "https://gamma-api.polymarket.com/events"

    def scan_weather_markets(self, pages=100):
        """
        Scans for weather-related markets on Polymarket.
        Iterates through events and their child markets.
        """
        weather_markets = []
        total_scanned = 0
        # Specific keywords with word boundaries to avoid false positives like "below" matching "low"
        keywords = ["temperature", "degrees", "fahrenheit", "celsius", "weather", "hottest", "coldest", "precipitation", "rain", "snow"]
        secondary_keywords = ["high", "low", "warm", "cold"]
        
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
                events = response.json()
                if not events:
                    break
                
                total_scanned += len(events)
                for event in events:
                    event_title = event.get("title", "").lower()
                    
                    # Check if the event itself is weather-related
                    is_weather_event = any(k in event_title for k in keywords)
                    
                    # Check markets within the event
                    markets = event.get("markets", [])
                    for m in markets:
                        m_question = m.get("question", "").lower()
                        
                        # A market is relevant if:
                        # 1. The event is a weather event
                        # 2. The question contains weather keywords
                        is_relevant = is_weather_event or any(k in m_question for k in keywords)
                        if not is_relevant:
                            # Secondary keywords must be combined with "temperature" or "weather" context 
                            # or be standalone but in a weather-related event title
                            for k in secondary_keywords:
                                if re.search(rf"\b{k}\b", m_question):
                                    if any(wk in event_title for wk in keywords):
                                        is_relevant = True
                                        break
                        
                        if is_relevant:
                            parsed = self.parse_market_details(m, event.get("title", ""))
                            if parsed:
                                weather_markets.append(parsed)
            
            logger.log_action("SCAN_COMPLETE", {
                "weather_count": len(weather_markets),
                "total_scanned": total_scanned
            })
            self.save_markets(weather_markets)
            return weather_markets
            
        except Exception as e:
            logger.log_action("SCAN_EXCEPTION", {"error": str(e)})
            return weather_markets

    def save_markets(self, markets):
        """Saves found markets to a JSON file for other components to access."""
        try:
            with open("logs/found_markets.json", "w") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "markets": markets
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving found markets: {e}")

    def parse_market_details(self, market, event_title=""):
        """
        Extracts City, Date, and Temperature Range from the market title/question.
        """
        question = market.get("question") or ""
        title = market.get("title") or question or ""
        
        # Combine question and event_title for better context
        search_text = f"{question} {event_title}"
        
        # Parse JSON strings if necessary
        def parse_json_if_str(val):
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except:
                    return val
            return val

        details = {
            "id": market.get("id"),
            "question": question,
            "title": title,
            "city": "Unknown",
            "date": "Unknown",
            "min_temp": None,
            "max_temp": None,
            "tokens": parse_json_if_str(market.get("tokens")) or [],
            "clobTokenIds": parse_json_if_str(market.get("clobTokenIds")) or [],
            "outcomes": parse_json_if_str(market.get("outcomes")) or [],
            "market_slug": market.get("slug")
        }
        
        # Extract price from outcomePrices if tokens are missing
        outcome_prices = parse_json_if_str(market.get("outcomePrices"))
        if not details["tokens"] and outcome_prices:
            # Create dummy token objects for the bot to use price
            details["tokens"] = [{"price": float(p)} for p in outcome_prices]
        
        # Comprehensive city extraction from unified config
        from config import CITIES
        
        found_city = False
        for city_key, city_data in CITIES.items():
            aliases = city_data.get("aliases", [])
            for alias in aliases:
                # Use word boundaries to avoid substring matches (e.g., "la" in "Manila")
                if re.search(rf"\b{re.escape(alias.lower())}\b", search_text.lower()):
                    details["city"] = city_key
                    found_city = True
                    break
            if found_city:
                break
        
        # If not in predefined list, try to extract a word that looks like a city
        if not found_city:
            match = re.search(r"in ([\w\s]+) (?:on|temperature|be|reach|go)", search_text)
            if match:
                details["city"] = match.group(1).strip()
            else:
                words = re.findall(r"([A-Z][a-z]+)", search_text)
                common = ["Will", "The", "How", "High", "Low", "Is", "Temperature", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December", "Degrees", "Fahrenheit", "Celsius", "Weather", "City", "Increase", "Decrease", "Average", "Global", "Normal", "Trend", "Anomaly"]
                for w in words:
                    if w not in common and len(w) > 2:
                        details["city"] = w
                        break
                
        # Parse date
        date_match = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+([1-9]|[12]\d|3[01])(?!\d)", search_text, re.IGNORECASE)
        if date_match:
            month = date_match.group(1).title()
            day = date_match.group(2)
            details["date"] = f"{month} {day}"
        else:
            # Try month only
            month_match = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b", search_text, re.IGNORECASE)
            if month_match:
                details["date"] = f"{month_match.group(1).title()} 15" # Default to mid-month
            else:
                date_match = re.search(r"by\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+([1-9]|[12]\d|3[01])(?!\d)", search_text, re.IGNORECASE)
                if date_match:
                    details["date"] = f"{date_match.group(1).title()} {date_match.group(2)}"
            
        # Parse range from question
        # 1. Between X and Y
        between_match = re.search(r"between\s+(\d+(?:\.\d+)?)[^\d]+and\s+(\d+(?:\.\d+)?)", question, re.IGNORECASE)
        if between_match:
            details["min_temp"] = float(between_match.group(1))
            details["max_temp"] = float(between_match.group(2))
        else:
            # 2. X-Y dash format
            range_match = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", question)
            if range_match:
                details["min_temp"] = float(range_match.group(1))
                details["max_temp"] = float(range_match.group(2))
            else:
                # 3. Above/Below
                # Use word boundaries and more flexible value matching
                if re.search(r"\b(above|higher|more)\b", question, re.IGNORECASE):
                    val_match = re.search(r"(\d+(?:\.\d+)?)", question) # Just find the first number
                    if val_match:
                        details["min_temp"] = float(val_match.group(1))
                        details["max_temp"] = float("inf")
                elif re.search(r"\b(below|lower|less)\b", question, re.IGNORECASE):
                    val_match = re.search(r"(\d+(?:\.\d+)?)", question) # Just find the first number
                    if val_match:
                        details["min_temp"] = float("-inf")
                        details["max_temp"] = float(val_match.group(1))
        
        # Final validation
        if details["min_temp"] is None and details["max_temp"] is None:
            return None
            
        if details["city"] == "Unknown":
            if "global" in search_text.lower():
                details["city"] = "Global"
            else:
                return None
                
        return details

market_scanner = MarketScanner()
