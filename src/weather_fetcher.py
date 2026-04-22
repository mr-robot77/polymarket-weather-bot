from __future__ import annotations
import requests
import logging
from typing import Dict, Any, Optional

class WeatherFetcher:
    def __init__(self) -> None:
        self.base_url_ensemble = "https://ensemble-api.open-meteo.com/v1/ensemble"
        self.base_url_forecast = "https://api.open-meteo.com/v1/forecast"
        self.quota_exhausted = False

    def get_coordinates(self, city_name: str) -> Optional[Dict[str, float]]:
        """
        Uses Open-Meteo Geocoding API to find lat/lon for any city name.
        """
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city_name, "count": 1, "language": "en", "format": "json"}
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results")
                if results:
                    return {"lat": results[0]["latitude"], "lon": results[0]["longitude"]}
        except Exception as e:
            logging.error(f"Geocoding error for {city_name}: {e}")
        return None

    def fetch_forecast(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        if not self.quota_exhausted:
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m",
                "models": "gfs_seamless"
            }
            try:
                response = requests.get(self.base_url_ensemble, params=params, timeout=10)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429: # Rate limit
                    self.quota_exhausted = True
                    logging.warning("Ensemble API quota exhausted, falling back to standard API.")
            except requests.RequestException as e:
                logging.error(f"Error fetching ensemble forecast: {e}")

        # Fallback
        params_fallback = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m"
        }
        try:
            response = requests.get(self.base_url_forecast, params=params_fallback, timeout=10)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logging.error(f"Error fetching standard forecast: {e}")

        return None
