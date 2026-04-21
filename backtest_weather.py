import pandas as pd
import numpy as np
import re
from datetime import datetime, timedelta, timezone
import requests
import math

def norm_cdf(x, mean, std):
    if std == 0: return 1.0 if x >= mean else 0.0
    return 0.5 * (1 + math.erf((x - mean) / (std * math.sqrt(2))))

# Configuration
EDGE_THRESHOLD = -1.0
INITIAL_BALANCE = 1000.0
TRADE_SIZE_USDC = 10.0

# City coordinates
CITY_COORDS = {
    "New York": (40.7128, -74.0060),
    "Chicago": (41.8781, -87.6298),
    "London": (51.5074, -0.1278),
    "Tokyo": (35.6895, 139.6917),
    "Los Angeles": (34.0522, -118.2437),
    "Ankara": (39.9334, 32.8597),
    "Lagos": (6.5244, 3.3792),
    "Paris": (48.8566, 2.3522),
    "Sao Paulo": (-23.5505, -46.6333),
    "Berlin": (52.5200, 13.4050),
    "Sydney": (-33.8688, 151.2093),
}

def parse_question(q):
    city_match = re.search(r"in ([\w\s]+) be", q)
    if not city_match: return None
    city = city_match.group(1).strip()
    
    date_match = re.search(r"on (\w+ \d+)", q)
    if not date_match: return None
    date_str = date_match.group(1) + " 2026"
    try:
        target_date = datetime.strptime(date_str, "%B %d %Y").strftime("%Y-%m-%d")
    except:
        return None
        
    temp_match = re.search(r"(\d+)°C", q)
    if not temp_match: return None
    temp = float(temp_match.group(1))
    
    op = "eq"
    if "or below" in q: op = "le"
    elif "or above" in q or "or higher" in q: op = "ge"
    
    return {"city": city, "date": target_date, "temp": temp, "op": op}

class WeatherCache:
    def __init__(self):
        self.data = {}

    def prefetch(self, cities):
        start_date = "2021-01-01"
        end_date = "2026-04-21"
        for city in cities:
            if city not in CITY_COORDS: continue
            lat, lon = CITY_COORDS[city]
            url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_max&timezone=UTC"
            try:
                resp = requests.get(url, timeout=20).json()
                self.data[city] = {
                    "time": resp["daily"]["time"],
                    "temp": resp["daily"]["temperature_2m_max"]
                }
            except Exception as e:
                print(f"Failed to fetch {city}: {e}")

    def get_stats(self, city, target_date):
        if city not in self.data: return None, None
        
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        historical_temps = []
        for year in [2021, 2022, 2023, 2024, 2025]:
            hist_date = target_dt.replace(year=year).strftime("%Y-%m-%d")
            try:
                idx = self.data[city]["time"].index(hist_date)
                val = self.data[city]["temp"][idx]
                if val is not None:
                    historical_temps.append(val)
            except ValueError:
                continue
        
        if len(historical_temps) < 3: return None, None
        return np.mean(historical_temps), np.std(historical_temps)

    def get_actual(self, city, target_date):
        if city not in self.data: return None
        try:
            idx = self.data[city]["time"].index(target_date)
            return self.data[city]["temp"][idx]
        except ValueError:
            return None

def calculate_metrics(pnl_history):
    if not pnl_history:
        return 0, 0, 0
    
    daily_returns = np.array(pnl_history) / INITIAL_BALANCE
    total_return = np.sum(pnl_history) / INITIAL_BALANCE
    
    if len(daily_returns) > 1 and np.std(daily_returns) > 0:
        sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(365)
    else:
        sharpe = 0
        
    cumulative = np.cumsum([INITIAL_BALANCE] + pnl_history)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    max_drawdown = np.min(drawdowns)
    
    return sharpe, total_return, max_drawdown

def run_backtest():
    df = pd.read_csv('recent_weather_markets.csv')
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at')

    cache = WeatherCache()
    cities_to_fetch = set()
    for _, row in df.iterrows():
        parsed = parse_question(row['question'])
        if parsed and parsed['city'] in CITY_COORDS:
            cities_to_fetch.add(parsed['city'])
    
    cache.prefetch(list(cities_to_fetch))

    pnl_history = []
    trades = []

    for _, row in df.iterrows():
        parsed = parse_question(row['question'])
        if not parsed or parsed['city'] not in CITY_COORDS:
            continue
            
        mean, std = cache.get_stats(parsed['city'], parsed['date'])
        if mean is None: continue
        
        if parsed['op'] == 'eq':
            prob = norm_cdf(parsed['temp'] + 0.5, mean, std) - norm_cdf(parsed['temp'] - 0.5, mean, std)
        elif parsed['op'] == 'le':
            prob = norm_cdf(parsed['temp'], mean, std)
        elif parsed['op'] == 'ge':
            prob = 1 - norm_cdf(parsed['temp'], mean, std)
            
        market_price = 0.4 # Simulation: entry at 0.4
        edge = prob - market_price
        
        if edge > EDGE_THRESHOLD:
            actual_temp = cache.get_actual(parsed['city'], parsed['date'])
            if actual_temp is None: continue
            
            if parsed['op'] == 'eq':
                win = (parsed['temp'] - 0.5 <= actual_temp <= parsed['temp'] + 0.5)
            elif parsed['op'] == 'le':
                win = (actual_temp <= parsed['temp'])
            elif parsed['op'] == 'ge':
                win = (actual_temp >= parsed['temp'])
                
            pnl = TRADE_SIZE_USDC if win else -TRADE_SIZE_USDC
            pnl_history.append(pnl)
            trades.append({
                "city": parsed['city'],
                "date": parsed['date'],
                "prob": prob,
                "actual": actual_temp,
                "win": win,
                "pnl": pnl
            })

    sharpe, total_return, max_drawdown = calculate_metrics(pnl_history)
    
    print("\n=== Backtest Results (Last 30 Days) ===")
    print(f"Total Markets Analyzed: {len(df)}")
    print(f"Total Trades Executed: {len(trades)}")
    if len(trades) > 0:
        print(f"Total P&L: ${np.sum(pnl_history):.2f}")
        print(f"Total Return: {total_return*100:.2f}%")
        print(f"Sharpe Ratio: {sharpe:.2f}")
        print(f"Max Drawdown: {max_drawdown*100:.2f}%")
        
        print("\nSample Trades:")
        for t in trades[:10]:
            print(f"{t['date']} {t['city']}: Prob={t['prob']:.2f}, Actual={t['actual']:.1f}, Win={t['win']}")

if __name__ == "__main__":
    run_backtest()
