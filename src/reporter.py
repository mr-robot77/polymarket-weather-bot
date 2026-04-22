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
            return f"<b>{period_name} Report</b>\nTrades: 0\nP&L: $0.00\n"
            
        pnl_total = 0.0
        city_pnl = {}
        morning_wins = 0
        morning_total = 0
        evening_wins = 0
        evening_total = 0
        total_trades = len(rows)
        
        for row in rows:
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
                
        report = f"<b>{period_name} Report</b>\n"
        report += f"Total Trades: {total_trades}\n"
        report += f"Net P&L: {'+' if pnl_total >= 0 else ''}${pnl_total:.2f}\n"
        
        # City breakdown
        sorted_cities = sorted(city_pnl.items(), key=lambda x: x[1], reverse=True)
        if sorted_cities:
            report += "🏙 <b>Top Cities:</b>\n"
            for city, pnl in sorted_cities[:3]:
                report += f" - {city}: {'+' if pnl >= 0 else ''}${pnl:.2f}\n"
            
        # Win Rates
        if morning_total > 0 or evening_total > 0:
            m_rate = (morning_wins/morning_total*100) if morning_total > 0 else 0
            e_rate = (evening_wins/evening_total*100) if evening_total > 0 else 0
            report += f"☀️ Morning WR: {m_rate:.1f}% ({morning_total} tr)\n"
            report += f"🌙 Evening WR: {e_rate:.1f}% ({evening_total} tr)\n"
            
        return report + "\n"

    def send_morning_report(self):
        if not os.path.exists(self.db_path):
            logging.info("No trades.db found for morning report.")
            return

        now = datetime.now()
        
        daily_rows = []
        weekly_rows = []
        all_rows = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, date, market_id, city, amount, pnl, edge, is_morning FROM trades")
            for row in cursor.fetchall():
                all_rows.append(row)
                ts_str = row[1]
                if not ts_str:
                    continue
                try:
                    if "T" in ts_str:
                        ts = datetime.fromisoformat(ts_str)
                    else:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d")
                except ValueError:
                    continue
                    
                time_diff = now - ts
                
                if time_diff <= timedelta(hours=24):
                    daily_rows.append(row)
                if time_diff <= timedelta(days=7):
                    weekly_rows.append(row)
            conn.close()
        except sqlite3.Error as e:
            logging.error(f"Error reading from trades.db: {e}")
            return

        # Build combined message
        from paper_trader import paper_trader
        staked = 0.0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(amount) FROM trades WHERE status = 'OPEN'")
            staked = cursor.fetchone()[0] or 0.0
            conn.close()
        except:
            pass

        message = "📊 <b>Enhanced Trading Summary</b>\n\n"
        message += f"🏦 <b>Bankroll:</b> ${paper_trader.balance:,.2f}\n"
        message += f"🔒 <b>Staked:</b> ${staked:,.2f}\n\n"
        
        message += self.generate_enhanced_stats(daily_rows, "Last 24h")
        message += self.generate_enhanced_stats(weekly_rows, "Last 7 Days")
        message += self.generate_enhanced_stats(all_rows, "Lifetime Performance")

        # Send via Telegram
        logging.info("Sending enhanced report to Telegram...")
        self.alerts.send_alert(message.strip())

reporter = Reporter()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    reporter.send_morning_report()
