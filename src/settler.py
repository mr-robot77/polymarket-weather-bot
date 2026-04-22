import sqlite3
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from telegram_alerts import TelegramAlerts
import os
import config

class TradeSettler:
    def __init__(self, db_path: str = "trades.db"):
        self.db_path = db_path
        self.alerts = TelegramAlerts()
        self.archive_url = "https://archive-api.open-meteo.com/v1/archive"

    def settle_trades(self):
        logging.info("Checking for trades to settle...")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find OPEN trades where target_date has passed
        now = datetime.now()
        cursor.execute("SELECT id, city, target_date, min_temp, max_temp, amount, price, type, question FROM trades WHERE status = 'OPEN'")
        open_trades = cursor.fetchall()
        
        settled_count = 0
        from paper_trader import paper_trader
        
        for trade_id, city, target_date_str, min_temp, max_temp, amount, price, trade_type, question in open_trades:
            if not target_date_str or target_date_str == "Unknown":
                continue
                
            try:
                # Parse target date
                target_dt = datetime.strptime(f"{target_date_str} 2026", "%B %d %Y")
                # Wait until at least 1 day after target date to settle
                if now < target_dt + timedelta(days=1):
                    continue
                
                logging.info(f"Settling trade {trade_id} for {city} on {target_date_str}...")
                
                actual_temp = self.fetch_actual_temp(city, target_dt.strftime("%Y-%m-%d"))
                if actual_temp is not None:
                    # Determine win/loss
                    win = False
                    if min_temp is not None and max_temp is not None:
                        win = (min_temp <= actual_temp <= max_temp)
                    
                    # Calculate PnL correctly
                    # If we buy 'amount' dollars at 'price', we get 'amount / price' shares.
                    # Each share is worth $1 if win, $0 if loss.
                    if price and price > 0:
                        shares = amount / price
                        payout = shares if win else 0.0
                        pnl = payout - amount
                    else:
                        # Fallback to old simple logic if price is missing
                        pnl = amount if win else -amount
                    
                    cursor.execute("""
                        UPDATE trades 
                        SET pnl = ?, status = 'CLOSED', actual_value = ? 
                        WHERE id = ?
                    """, (pnl, actual_temp, trade_id))
                    
                    # Update paper balance if applicable
                    if trade_type == "PAPER" and win:
                        paper_trader.balance += (amount + pnl) # Add back investment + profit
                        paper_trader.save_balance()
                    elif trade_type == "PAPER" and not win:
                        # Investment already subtracted during execution, so nothing to add back
                        pass
                    
                    conn.commit()
                    settled_count += 1
                    
                    status_emoji = "✅" if win else "❌"
                    self.alerts.send_alert(
                        f"{status_emoji} <b>Trade Settled: {city}</b>\n"
                        f"Question: {question}\n"
                        f"Actual: {actual_temp:.1f}°\n"
                        f"Result: {'WIN (+$'+f'{pnl:.2f}'+')' if win else 'LOSS (-$'+f'{abs(pnl):.2f}'+')'}"
                    )
            except Exception as e:
                logging.error(f"Error settling trade {trade_id}: {e}")
                
        conn.close()
        if settled_count > 0:
            logging.info(f"Settled {settled_count} trades.")
        return settled_count

    def fetch_actual_temp(self, city: str, date_str: str) -> Optional[float]:
        # Special handling for Global
        if city == "Global":
            # Mock actual for global anomaly if needed, or fetch from reliable source
            # For now, let's assume we can't settle global automatically easily without specific API
            return None

        # Get coordinates from config or geocoding
        city_data = config.CITIES.get(city)
        if not city_data:
            return None
            
        lat = city_data.get("lat")
        lon = city_data.get("lon")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": date_str,
            "end_date": date_str,
            "daily": "temperature_2m_max",
            "timezone": "UTC"
        }
        
        try:
            resp = requests.get(self.archive_url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                temps = data.get("daily", {}).get("temperature_2m_max", [])
                if temps and temps[0] is not None:
                    # Open-Meteo returns Celsius. Our bot uses Fahrenheit in extract_forecast_temp
                    # But wait, market scanner might extract Celsius?
                    # Let's check backtest_weather.py: it uses Celsius from archive.
                    # src/main.py: extract_forecast_temp converts to Fahrenheit.
                    # We should be consistent.
                    f_temp = (temps[0] * 9/5) + 32
                    return f_temp
        except Exception as e:
            logging.error(f"Error fetching archive data for {city}: {e}")
            
        return None

settler = TradeSettler()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    settler.settle_trades()
