import json
import os
from src.logger import logger

class PaperTrader:
    def __init__(self, balance=1000.0):
        self.state_file = "data/paper_balance.json"
        if os.path.exists(self.state_file):
            with open(self.state_file) as f:
                self.balance = json.load(f)["balance"]
        else:
            self.balance = balance
            self.save_balance()

    def save_balance(self):
        with open(self.state_file, "w") as f:
            json.dump({"balance": self.balance}, f)

    def execute_trade(self, edge_info):
        market = edge_info["market"]
        # Dummy size: 2% of balance
        size = self.balance * 0.02
        
        trade_record = {
            "market": market["question"],
            "outcome": "Yes",
            "price": edge_info["market_price"],
            "prob": edge_info["forecast_prob"],
            "edge": edge_info["edge"],
            "size": size,
            "type": edge_info["type"],
            "pnl": 0.0, # Will be updated when market closes
            "status": "PAPER_OPEN"
        }
        
        # Simulate buying (subtract from balance)
        # Note: in real paper trading we'd track the tokens and wait for resolution
        self.balance -= size
        self.save_balance()
        
        logger.log_trade(trade_record)
        return trade_record

paper_trader = PaperTrader()
