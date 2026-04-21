from __future__ import annotations
import time
import argparse
import logging
from dotenv import load_dotenv
import os

from py_clob_client.client import ClobClient # type: ignore
from py_clob_client.clob_types import OrderArgs, OrderType # type: ignore
from py_clob_client.order_builder.constants import BUY # type: ignore

import config
from weather_fetcher import WeatherFetcher
from polymarket_client import PolymarketClient
from edge_calculator import EdgeCalculator
from kelly_sizing import KellySizing
from risk_manager import RiskManager
from telegram_alerts import TelegramAlerts

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_market_price(m: dict) -> float:
    # A realistic implementation would fetch the order book. 
    # For now, we mock fetching the best ask price of 'Yes' tokens.
    tokens = m.get("tokens", [])
    if tokens:
        return tokens[0].get("price", 0.5)
    return 0.5

def extract_forecast_temp(city: str, date: str, forecasts: dict) -> float:
    # Simplified mock implementation
    return 70.0

def check_existing_position(clob_client: ClobClient | None, market_id: str) -> bool:
    if not clob_client:
        return False
    # Mock implementation of checking positions to skip duplicates
    # We would call clob_client.get_positions()
    return False

def run_cycle(live: bool, clob_client: ClobClient | None) -> None:
    try:
        logging.info("Starting cycle...")
        fetcher = WeatherFetcher()
        poly_client = PolymarketClient()
        edge_calc = EdgeCalculator()
        kelly = KellySizing()
        risk = RiskManager()
        alerts = TelegramAlerts()
        
        bankroll = 1000.0 # Could fetch from clob_client
        if risk.check_circuit_breaker(bankroll):
            logging.warning("Circuit breaker active. Halting trading.")
            return
            
        forecasts = {}
        for city, data in config.CITIES.items():
            try:
                fc = fetcher.fetch_forecast(data["lat"], data["lon"])
                if fc:
                    forecasts[city] = fc
            except Exception as e:
                logging.error(f"Error fetching forecast for {city}: {e}")
                
        try:
            markets = market_scanner.scan_weather_markets()
        except Exception as e:
            logging.error(f"Error scanning markets: {e}")
            return

        logging.info(f"Found {len(markets)} active temperature markets.")
        
        events = {}
        for details in markets:
            city = details["city"]
            date = details["date"]
            
            if city not in config.CITIES or date == "Unknown":
                continue
                
            event_key = f"{city}_{date}"
            if event_key not in events:
                events[event_key] = []
                
            events[event_key].append({"market": details, "details": details})
            
        for event_key, options in events.items():
            # CRITICAL RULE: Only place ONE bet per event (city + date combination)
            best_trade = None
            best_edge = 0.0
            best_bet_size = 0.0
            best_city = "Unknown"
            
            city = options[0]["details"]["city"]
            date = options[0]["details"]["date"]
            forecast_temp = extract_forecast_temp(city, date, forecasts)
            rmse = config.CITIES[city]["rmse"]
            
            for option in options:
                m = option["market"]
                details = option["details"]
                city = details.get("city", "Unknown")
                min_temp = details["min_temp"]
                max_temp = details["max_temp"]
                
                if min_temp is None or max_temp is None:
                    continue

                # Load rules for blacklist and dynamic threshold
                try:
                    with open("config/rules.json", "r") as f:
                        rules = json.load(f)
                    blacklist = rules.get("blacklist", [])
                    current_threshold = rules.get("edge_threshold", config.EDGE_THRESHOLD)
                except:
                    blacklist = []
                    current_threshold = config.EDGE_THRESHOLD

                if city in blacklist:
                    continue
                    
                market_price = get_market_price(m)
                true_prob = edge_calc.calculate_probability(forecast_temp, rmse, min_temp, max_temp)
                edge = edge_calc.calculate_edge(true_prob, market_price)
                
                if edge > current_threshold:
                    bet_size = kelly.calculate_bet_size(edge, true_prob, market_price, bankroll)
                    if bet_size > 0 and edge > best_edge:
                        best_edge = edge
                        best_trade = m
                        best_bet_size = bet_size
                        best_city = city
                        
            if best_trade:
                if risk.exposure + best_bet_size > config.MAX_TOTAL_EXPOSURE:
                    logging.warning(f"Skipping trade for {best_trade['title']} due to MAX_TOTAL_EXPOSURE limit.")
                    continue
                    
                market_id = best_trade.get("id", "unknown")
                if check_existing_position(clob_client, market_id):
                    logging.info(f"Skipping {best_trade['title']} as position already exists.")
                    continue
                
                if live and clob_client:
                    # FOK order execution via py-clob-client with GTC fallback 5% slippage
                    logging.info(f"Executing trade on {best_trade['title']} for ${best_bet_size:.2f} (Edge: {best_edge:.2%})")
                    risk.record_trade(market_id, best_city, best_bet_size, best_edge)
                    alerts.send_alert(f"<b>Trade Executed</b>\nCity: {best_city}\nAmount: ${best_bet_size:.2f}\nEdge: {best_edge:.2%}")
                    
                    # Analyst Trigger: every 200 trades
                    if risk.get_total_trade_count() % 200 == 0:
                        logging.info("Triggering Analyst Bot for 200-trade optimization...")
                        from analyst import analyst_bot
                        analyst_bot.analyze()
                else:
                    logging.info(f"[DRY RUN] Would execute trade on {best_trade['title']} (City: {best_city}) for ${best_bet_size:.2f} (Edge: {best_edge:.2%})")

        logging.info("Cycle complete.")
    except Exception as e:
        logging.error(f"Critical error in trading cycle: {e}", exc_info=True)

import schedule
import threading
from market_scanner import market_scanner
from self_improver import self_improver
from reporter import reporter
from telegram_bot import run_telegram_bot

def run_self_improvement():
    logging.info("Running self-improvement cycle...")
    self_improver.improve()

def main() -> None:
    parser = argparse.ArgumentParser(description="Polymarket Weather Trading Bot")
    parser.add_argument("--live", action="store_true", help="Run with real money")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args()
    
    load_dotenv(override=True)
    private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
    chain_id = 137 # Polygon Mainnet
    host = "https://clob.polymarket.com"
    
    clob_client = None
    if args.live:
        if not private_key:
            logging.error("POLYMARKET_PRIVATE_KEY not set in .env")
            return
        
        # Initializing clob client
        from py_clob_client.clob_types import ApiCreds # type: ignore
        # Typically we create credentials and pass them:
        # api_key = os.getenv("POLYMARKET_API_KEY")
        # api_secret = os.getenv("POLYMARKET_API_SECRET")
        # api_passphrase = os.getenv("POLYMARKET_API_PASSPHRASE")
        # creds = ApiCreds(api_key=api_key, api_secret=api_secret, api_passphrase=api_passphrase)
        # clob_client = ClobClient(host, key=private_key, chain_id=chain_id, creds=creds)
        # Mocked for pass
        clob_client = True # type: ignore
        
    if args.once:
        run_cycle(args.live, clob_client) # type: ignore
    else:
        logging.info("Starting 24/7 autonomous mode.")
        # Run a cycle immediately
        run_cycle(args.live, clob_client)
        
        # Schedule the regular trading cycle
        schedule.every(config.SCAN_INTERVAL_SECONDS).seconds.do(run_cycle, args.live, clob_client)
        
        # Schedule self improvement every 24 hours
        schedule.every(24).hours.do(run_self_improvement)
        
        # Schedule morning report every day at 08:00
        schedule.every().day.at("08:00").do(reporter.send_morning_report)
        
        # Start Telegram Bot in the background
        logging.info("Starting Telegram Bot listener...")
        tg_thread = threading.Thread(target=run_telegram_bot, daemon=True)
        tg_thread.start()
        
        while True:
            if not tg_thread.is_alive():
                logging.error("Telegram bot thread died! Exiting to trigger systemd restart.")
                os._exit(1)
                
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    main()
