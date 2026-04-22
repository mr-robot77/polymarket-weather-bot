import requests
import numpy as np
from datetime import datetime
from logger import logger

class ForecastFetcher:
    def __init__(self):
        self.base_url = "https://ensemble-api.open-meteo.com/v1/ensemble"

    def get_temperature_probability(self, lat, lon, target_date, temp_min, temp_max, is_fahrenheit=True):
        """
        Fetches ensemble forecast and calculates probability of temperature being between temp_min and temp_max.
        target_date: YYYY-MM-DD
        is_fahrenheit: If True, converts API Celsius results to Fahrenheit before comparing.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max",
            "timezone": "UTC",
            "start_date": target_date,
            "end_date": target_date,
            "models": "ecmwf_ifs04"
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            # Open-Meteo ensemble returns 50+ members for ECMWF
            daily_data = data.get("daily", {})
            temp_members = []
            
            for key, values in daily_data.items():
                if "temperature_2m_max" in key and values and len(values) > 0:
                    if values[0] is not None:
                        temp = values[0]
                        if is_fahrenheit:
                            temp = (temp * 9/5) + 32
                        temp_members.append(temp)
            
            if not temp_members:
                logger.log_action("FORECAST_ERROR", {"msg": "No ensemble data found", "date": target_date})
                return None
                
            # Calculate probability
            members_in_range = [t for t in temp_members if temp_min <= t <= temp_max]
            probability = len(members_in_range) / len(temp_members)
            
            logger.log_action("FORECAST_FETCHED", {
                "date": target_date,
                "range": [temp_min, temp_max],
                "prob": probability,
                "sample_size": len(temp_members),
                "unit": "F" if is_fahrenheit else "C"
            })
            
            return probability
            
        except Exception as e:
            logger.log_action("FORECAST_EXCEPTION", {"error": str(e)})
            return None

forecast_fetcher = ForecastFetcher()
