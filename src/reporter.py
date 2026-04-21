import sqlite3
import os
from datetime import datetime, timedelta
import logging
from telegram_alerts import TelegramAlerts

class Reporter:
    def __init__(self, db_path="trades.db"):
        self.db_path = db_path
        self.alerts = TelegramAlerts()

    def generate_enhanced_stats(self, rows, period_name):
        if not rows:
            return f"<b>{period_name} Report</b>\nNo trades.\n"
            
        pnl_total = 0.0
        city_pnl = {}
        morning_wins = 0
        morning_total = 0
        evening_wins = 0
        evening_total = 0
        
        for row in rows:
            # New schema: (id, date, market_id, city, amount, pnl, edge, is_morning)
            pnl = float(row[5] if row[5] is not None else 0.0)
            city = row[3]
            is_morning = row[7]
            
            pnl_total += pnl
            city_pnl[city] = city_pnl.get(city, 0.0) + pnl
            
            if is_morning:
                morning_total += 1
                if pnl > 0: morning_wins += 1
            else:
                evening_total += 1
                if pnl > 0: evening_wins += 1
                
        # Format the stats
        report = f"<b>{period_name} Report</b>\n"
        report += f"Total P&L: ${pnl_total:.2f}\n"
        
        # City breakdown (top 3)
        sorted_cities = sorted(city_pnl.items(), key=lambda x: x[1], reverse=True)
        report += "🏙 <b>Top Cities:</b>\n"
        for city, pnl in sorted_cities[:3]:
            report += f" - {city}: {'+' if pnl >= 0 else ''}${pnl:.2f}\n"
            
        # Morning vs Evening
        m_rate = (morning_wins/morning_total*100) if morning_total > 0 else 0
        e_rate = (evening_wins/evening_total*100) if evening_total > 0 else 0
        report += f"☀️ Morning WR: {m_rate:.1f}%\n"
        report += f"🌙 Evening WR: {e_rate:.1f}%\n"
            
        return report + "\n"

    def send_morning_report(self):
        if not os.path.exists(self.db_path):
            logging.info("No trades.db found for morning report.")
            return

        now = datetime.now()
        
        daily_rows = []
        weekly_rows = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Fetch with new columns
            cursor.execute("SELECT id, date, market_id, city, amount, pnl, edge, is_morning FROM trades")
            for row in cursor.fetchall():
                ts_str = row[1]
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str)
                except ValueError:
                    continue
                    
                days_diff = (now - ts).days
                
                if days_diff < 1:
                    daily_rows.append(row)
                if days_diff < 7:
                    weekly_rows.append(row)
            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Error reading from trades.db: {e}")
            return

        # Build combined message
        message = "📊 <b>Enhanced Trading Summary</b>\n\n"
        message += self.generate_enhanced_stats(daily_rows, "Last 24h")
        
        if now.weekday() == 0: # Monday
            message += self.generate_enhanced_stats(weekly_rows, "Weekly Performance")

        # Send via Telegram
        logging.info("Sending enhanced report to Telegram...")
        self.alerts.send_alert(message.strip())

reporter = Reporter()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reporter.send_morning_report()
