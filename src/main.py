from __future__ import annotations
import time
import argparse
import logging
import signal
import sys
import threading
from datetime import datetime
from dotenv import load_dotenv
import os
import json

import schedule
from py_clob_client.client import ClobClient # type: ignore
from py_clob_client.clob_types import OrderArgs, OrderType, ApiCreds # type: ignore
from py_clob_client.order_builder.constants import BUY # type: ignore
from eth_account import Account

import config
from weather_fetcher import WeatherFetcher
from polymarket_client import PolymarketClient
from edge_calculator import EdgeCalculator
from kelly_sizing import KellySizing
from risk_manager import RiskManager
from telegram_alerts import TelegramAlerts
from market_scanner import market_scanner
from wisdom import wisdom_manager
from settler import settler
from paper_trader import paper_trader
from reporter import reporter
from telegram_bot import run_telegram_bot
from logger import logger as bot_logger

class AutonomousBot:
    def __init__(self, live: bool = False):
        self.live = live
        self.clob_client = None
        self.fetcher = WeatherFetcher()
        self.edge_calc = EdgeCalculator()
        self.kelly = KellySizing()
        self.risk = RiskManager()
        self.alerts = TelegramAlerts()
        self.paper_trader = paper_trader
        self.running = True
        self.tg_thread = None
        
        # Stats tracking
        self.start_time = datetime.now()
        self.cycles_completed = 0
        self.errors_encountered = 0
        
        self._setup_signals()
        self._initialize_client()

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        logging.info(f"Received signal {signum}. Shutting down gracefully...")
        self.running = False
        try:
            self.alerts.send_alert("⚠️ <b>Bot Shutting Down</b>\nSignal received. Cleaning up...")
        except:
            pass
        sys.exit(0)

    def _initialize_client(self):
        if not self.live:
            logging.info("Paper Trading mode initialized.")
            return

        load_dotenv(override=True)
        private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        mnemonic = os.getenv("POLYMARKET_MNEMONIC")
        chain_id = 137 # Polygon Mainnet
        host = "https://clob.polymarket.com"

        if mnemonic:
            try:
                logging.info("Deriving Private Key from Mnemonic...")
                Account.enable_unaudited_hdwallet_features()
                acct = Account.from_mnemonic(mnemonic)
                private_key = acct.key.hex()
                logging.info(f"Derived Signer Address: {acct.address}")
            except Exception as e:
                logging.error(f"Failed to derive key from mnemonic: {e}")
                return

        if not private_key or "your_64_char" in private_key:
            logging.error("CRITICAL: POLYMARKET_PRIVATE_KEY or MNEMONIC is not set or invalid in .env")
            return

        try:
            logging.info("Initializing Polymarket CLOB Client...")
            safe_address = os.getenv("POLYMARKET_SAFE_ADDRESS")
            
            self.clob_client = ClobClient(
                host, 
                key=private_key, 
                chain_id=chain_id,
                signature_type=1 # 1 for EOA
            )

            logging.info("Fetching/Deriving API Credentials from Polymarket...")
            creds = self.clob_client.create_or_derive_api_creds()
            if creds:
                self.clob_client.set_api_creds(creds)
                logging.info("Polymarket CLOB Client fully initialized.")
            else:
                logging.error("Failed to derive API credentials.")
                return
            
            if safe_address and "0x" in safe_address:
                try:
                    self.clob_client.set_proxy_address(safe_address)
                    logging.info(f"Using Safe Address: {safe_address}")
                except:
                    pass
        except Exception as e:
            logging.error(f"Failed to initialize CLOB Client: {e}")

    def get_market_price(self, m: dict) -> float:
        tokens = m.get("tokens", [])
        if tokens:
            return float(tokens[0].get("price", 0.5))
        return 0.5

    def extract_forecast_temp(self, city: str, date_str: str, forecasts: dict) -> float:
        if city not in forecasts:
            return 70.0
        
        data = forecasts[city]
        if "hourly" not in data:
            return 70.0
            
        try:
            dt = datetime.strptime(f"{date_str} 2026", "%B %d %Y")
            target_date = dt.strftime("%Y-%m-%d")
            
            temps = []
            for t, temp in zip(data["hourly"]["time"], data["hourly"]["temperature_2m"]):
                if target_date in t:
                    f_temp = (temp * 9/5) + 32
                    temps.append(f_temp)
            
            if temps:
                return max(temps)
        except Exception as e:
            logging.error(f"Error extracting forecast for {city} on {date_str}: {e}")
            
        return 70.0

    def check_existing_position(self, market_id: str) -> bool:
        return self.risk.has_open_position(market_id)

    def run_trading_cycle(self):
        try:
            logging.info("Starting trading cycle...")
            
            # Use actual bankroll
            if self.live:
                bankroll = 1000.0 # Default if can't fetch
                if self.clob_client:
                    try:
                        # Try to get actual balance if live
                        pass 
                    except:
                        pass
            else:
                bankroll = self.paper_trader.balance

            if self.risk.check_circuit_breaker(bankroll):
                logging.warning("Circuit breaker active. Halting trading.")
                return
                
            markets = market_scanner.scan_weather_markets()
            if not markets:
                logging.info("No candidate weather markets found in this scan.")
                return

            logging.info(f"Found {len(markets)} candidate weather markets.")
            
            forecasts = {}
            # Global temperature anomaly doesn't need a coordinate-based forecast in the same way
            forecasts["Global"] = {"current_anomaly": 1.17} # Hardcoded approximate for April 2026 based on market context

            current_cities = config.get_cities()
            for city, data in current_cities.items():
                try:
                    fc = self.fetcher.fetch_forecast(data["lat"], data["lon"])
                    if fc:
                        forecasts[city] = fc
                except Exception as e:
                    logging.error(f"Error fetching forecast for {city}: {e}")

            events = {}
            for details in markets:
                city = details["city"]
                date = details["date"]
                
                if city == "Unknown" or date == "Unknown":
                    # Try to parse Global markets even if date is Unknown (we default it to mid-month now)
                    if city != "Global":
                        continue
                
                if city not in forecasts and city not in current_cities:
                    if city == "Global":
                        pass # Handled above
                    else:
                        logging.info(f"Discovered new city: {city}. Attempting to get coordinates...")
                        coords = self.fetcher.get_coordinates(city)
                        if coords:
                            fc = self.fetcher.fetch_forecast(coords["lat"], coords["lon"])
                            if fc:
                                forecasts[city] = fc
                                # We can't easily update config.json here without potentially corrupting it if multiple threads,
                                # but the scanner/fetcher can handle it.
                        else:
                            continue
                    
                event_key = f"{city}_{date}"
                if event_key not in events:
                    events[event_key] = []
                events[event_key].append(details)
                
            for event_key, options in events.items():
                best_trade = None
                best_edge = 0.0
                best_bet_size = 0.0
                best_prob = 0.0
                
                city = options[0]["city"]
                date = options[0]["date"]
                
                # Special handling for Global
                if city == "Global":
                    forecast_temp = forecasts["Global"]["current_anomaly"]
                    rmse = 0.05 # Much smaller RMSE for global anomalies
                else:
                    forecast_temp = self.extract_forecast_temp(city, date, forecasts)
                    rmse = current_cities.get(city, {"rmse": 2.0}).get("rmse", 2.0)
                
                rules = config.get_rules()
                blacklist = rules.get("blacklist", [])
                
                # Lower threshold for paper trading to encourage activity
                current_threshold = rules.get("edge_threshold", 0.08)
                if not self.live:
                    current_threshold = min(current_threshold, 0.02)

                if city in blacklist:
                    continue
                    
                for m in options:
                    min_temp = m["min_temp"]
                    max_temp = m["max_temp"]
                    if min_temp is None or max_temp is None:
                        continue
                        
                    market_price = self.get_market_price(m)
                    true_prob = self.edge_calc.calculate_probability(forecast_temp, rmse, min_temp, max_temp)
                    edge = self.edge_calc.calculate_edge(true_prob, market_price)
                    
                    if edge > 0.01: # Debug log any positive edge
                        logging.info(f"Market: {m['title']} | Price: {market_price} | Prob: {true_prob:.2f} | Edge: {edge:.2%}")

                    if edge > current_threshold:
                        bet_size = self.kelly.calculate_bet_size(edge, true_prob, market_price, bankroll)
                        if bet_size > 0 and edge > best_edge:
                            best_edge = edge
                            best_trade = m
                            best_bet_size = bet_size
                            best_prob = true_prob
                            
                if best_trade:
                    if self.risk.exposure + best_bet_size > rules.get("max_total_exposure"):
                        logging.warning(f"Skipping trade for {best_trade['title']} due to exposure limit.")
                        continue
                        
                    if self.check_existing_position(best_trade.get("id", "")):
                        continue
                    
                    if self.live and self.clob_client:
                        self.execute_real_trade(best_trade, best_bet_size, best_edge, best_prob, city)
                    else:
                        self.execute_paper_trade(best_trade, best_bet_size, best_edge, best_prob, city)

            self.cycles_completed += 1
            logging.info("Cycle complete.")
        except Exception as e:
            self.errors_encountered += 1
            logging.error(f"Critical error in trading cycle: {e}", exc_info=True)

    def execute_real_trade(self, trade, size, edge, prob, city):
        logging.info(f"Executing REAL trade on {trade['title']} for ${size:.2f} (Edge: {edge:.2%})")
        try:
            token_id = trade.get("clobTokenIds", [None])[0]
            if not token_id:
                logging.error(f"No Token ID found for {trade['title']}")
                return

            price = self.get_market_price(trade)
            order_args = OrderArgs(
                price=price,
                size=float(size),
                side=BUY,
                token_id=token_id
            )
            order = self.clob_client.create_order(order_args)
            resp = self.clob_client.post_order(order)
            
            if resp and resp.get("success"):
                logging.info(f"Trade successful! Order ID: {resp.get('orderID')}")
                self.risk.record_trade(
                    trade.get("id"), city, size, price, edge, trade_type="REAL",
                    min_temp=trade.get("min_temp"),
                    max_temp=trade.get("max_temp"),
                    target_date=trade.get("date"),
                    question=trade.get("question")
                )
                bot_logger.log_trade({
                    "market": trade['title'], "city": city, "outcome": "Yes",
                    "price": price, "prob": prob, "edge": edge,
                    "size": size, "type": "REAL", "pnl": 0.0, "status": "OPEN",
                    "is_morning": 1 if 4 <= datetime.now().hour < 12 else 0
                })
                self.alerts.send_alert(f"✅ <b>Trade Executed (LIVE)</b>\nCity: {city}\nAmount: ${size:.2f}\nEdge: {edge:.2%}")
                
                if self.risk.get_total_trade_count() % 200 == 0:
                    analyst_bot.analyze()
            else:
                logging.error(f"Trade failed: {resp}")
        except Exception as e:
            logging.error(f"Error placing real order: {e}")

    def execute_paper_trade(self, trade, size, edge, prob, city):
        logging.info(f"[PAPER TRADING] Executing trade on {trade['title']} (City: {city}) for ${size:.2f} (Edge: {edge:.2%})")
        self.paper_trader.execute_trade(trade, size, edge, prob, city)
        price = self.get_market_price(trade)
        self.risk.record_trade(
            trade.get("id"), city, size, price, edge, trade_type="PAPER",
            min_temp=trade.get("min_temp"),
            max_temp=trade.get("max_temp"),
            target_date=trade.get("date"),
            question=trade.get("question")
        )
        self.alerts.send_alert(f"📝 <b>Paper Trade Executed</b>\nCity: {city}\nAmount: ${size:.2f}\nEdge: {edge:.2%}")

    def run_reflection_cycle(self):
        try:
            logging.info("Starting reflection cycle (Settlement & Wisdom)...")
            settled_count = settler.settle_trades()
            if settled_count > 0:
                logging.info(f"Settled {settled_count} trades. Triggering deep wisdom reflection...")
                wisdom_manager.reflect_and_improve(cycles=self.cycles_completed)
            else:
                logging.info("No trades settled. Skipping wisdom reflection for now.")
        except Exception as e:
            logging.error(f"Error in reflection cycle: {e}")

    def run_wisdom_cycle(self):
        try:
            logging.info("Running autonomous deep wisdom cycle...")
            wisdom_manager.reflect_and_improve(cycles=self.cycles_completed)
        except Exception as e:
            logging.error(f"Error in wisdom cycle: {e}")

    def heartbeat(self):
        uptime = datetime.now() - self.start_time
        logging.info(f"Heartbeat: Uptime={uptime}, Cycles={self.cycles_completed}, Errors={self.errors_encountered}")
        if self.errors_encountered > 0 or datetime.now().hour % 12 == 0:
            self.alerts.send_alert(f"💓 <b>Bot Heartbeat</b>\nUptime: {str(uptime).split('.')[0]}\nCycles: {self.cycles_completed}\nErrors: {self.errors_encountered}")

    def run_forever(self):
        logging.info(f"Starting 24/7 autonomous mode (Live={self.live}).")
        self.alerts.send_alert(f"🚀 <b>Weather Bot Started</b>\nMode: {'LIVE' if self.live else 'Paper Trading'}\nTime: {datetime.now().strftime('%H:%M:%S')}")
        
        # Initial Cycles
        self.run_trading_cycle()
        self.run_reflection_cycle()
        
        # Schedule Tasks
        schedule.every(config.SCAN_INTERVAL_SECONDS).seconds.do(self.run_trading_cycle)
        schedule.every(4).hours.do(self.run_reflection_cycle)
        schedule.every(24).hours.do(self.run_wisdom_cycle)
        schedule.every().day.at("08:00").do(reporter.send_morning_report)
        schedule.every(6).hours.do(self.heartbeat)
        
        # Start Telegram Bot in background
        self.tg_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        self.tg_thread.start()
        
        while self.running:
            try:
                if not self.tg_thread.is_alive():
                    logging.error("Telegram bot thread died! Attempting to restart...")
                    self.tg_thread = threading.Thread(target=run_telegram_bot, daemon=True)
                    self.tg_thread.start()
                    
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                time.sleep(10)

def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket Weather Trading Bot")
    parser.add_argument("--live", action="store_true", help="Run with real money")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args()
    
    bot = AutonomousBot(live=args.live)
    if args.once:
        bot.run_trading_cycle()
    else:
        bot.run_forever()

if __name__ == "__main__":
    main()
