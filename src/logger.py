import logging
import json
import csv
import os
from datetime import datetime

class BotLogger:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Standard logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(f"{log_dir}/bot.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("WeatherBot")

    def log_action(self, action_type, details):
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "action": action_type,
            "details": details
        }
        
        # JSON Logging
        json_file = f"{self.log_dir}/actions.json"
        with open(json_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        self.logger.info(f"{action_type}: {json.dumps(details)}")

    def log_trade(self, trade_data):
        # CSV Logging for trades
        csv_file = f"{self.log_dir}/trades.csv"
        file_exists = os.path.isfile(csv_file)
        
        headers = [
            "timestamp", "market", "city", "outcome", "price", "prob", "edge", 
            "size", "type", "pnl", "status", "is_morning"
        ]
        
        with open(csv_file, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()
            
            trade_data["timestamp"] = datetime.now().isoformat()
            writer.writerow(trade_data)
            
        self.log_action("TRADE_EXECUTED", trade_data)

logger = BotLogger()
