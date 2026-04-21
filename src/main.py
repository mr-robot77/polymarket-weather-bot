import sys
import os
import schedule
import time
import json
import argparse
from dotenv import load_dotenv

# Ensure the project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.logger import logger
from src.market_scanner import market_scanner
from src.edge_detector import edge_detector
from src.paper_trader import paper_trader
from src.real_trader import real_trader
from src.self_improver import self_improver

load_dotenv()

class WeatherBotOrchestrator:
    def __init__(self, mode=None):
        with open("config/config.json") as f:
            self.config = json.load(f)
        
        self.mode = mode or os.getenv("BOT_MODE", "paper")
        self.trader = paper_trader if self.mode == "paper" else real_trader
        self.trade_count = 0

    def run_cycle(self):
        logger.log_action("CYCLE_START", {"mode": self.mode})
        
        # 1. Scan Markets
        markets = market_scanner.scan_weather_markets()
        
        # 2. Find Edges
        edges = edge_detector.find_edges(markets)
        
        # 3. Execute Trades
        for edge in edges:
            self.trader.execute_trade(edge)
            self.trade_count += 1
            
            # Check for self-improvement trigger (every 10 trades)
            if self.trade_count % 10 == 0:
                self_improver.improve()

    def start(self):
        # Initial run
        self.run_cycle()
        
        # Schedule periodic runs
        interval = self.config.get("scan_interval_seconds", 300)
        schedule.every(interval).seconds.do(self.run_cycle)
        
        # Schedule daily improvement at 00:00 UTC
        schedule.every().day.at("00:00").do(self_improver.improve)
        
        logger.log_action("BOT_STARTED", {"interval": interval})
        
        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Weather Bot")
    parser.add_argument("--mode", type=str, choices=["paper", "real"], help="Trading mode (paper or real)")
    args = parser.parse_args()

    bot = WeatherBotOrchestrator(mode=args.mode)
    bot.start()
