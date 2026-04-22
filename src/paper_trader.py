import json
import os
from datetime import datetime
from logger import logger

class PaperTrader:
    def __init__(self, balance=10000.0):
        self.state_file = "data/paper_balance.json"
        os.makedirs("data", exist_ok=True)
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    self.balance = json.load(f)["balance"]
            except:
                self.balance = balance
                self.save_balance()
        else:
            self.balance = balance
            self.save_balance()

    def save_balance(self):
        with open(self.state_file, "w") as f:
            json.dump({"balance": self.balance}, f)

    def execute_trade(self, trade, size, edge, prob, city):
        now = datetime.now()
        is_morning = 1 if 4 <= now.hour < 12 else 0

        trade_record = {
            "market": trade['title'],
            "city": city,
            "outcome": "Yes",
            "price": trade.get("tokens", [{"price": 0.5}])[0].get("price", 0.5) if trade.get("tokens") else 0.5,
            "prob": prob,
            "edge": edge,
            "size": size,
            "type": "PAPER",
            "pnl": 0.0, 
            "status": "OPEN",
            "is_morning": is_morning
        }

        # Simulate buying (subtract from balance)
        self.balance -= size
        self.save_balance()
        
        logger.log_trade(trade_record)
        return trade_record

paper_trader = PaperTrader()
