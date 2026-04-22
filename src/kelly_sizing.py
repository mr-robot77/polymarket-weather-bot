from __future__ import annotations
import config

class KellySizing:
    def calculate_bet_size(self, edge: float, true_prob: float, market_price: float, bankroll: float) -> float:
        rules = config.get_rules()
        cfg = config.get_config()
        
        if market_price <= 0 or market_price >= 1:
            return 0.0
            
        b = (1 - market_price) / market_price
        q = 1 - true_prob
        kelly_pct = (b * true_prob - q) / b
        
        if kelly_pct <= 0:
            return 0.0
            
        fractional_kelly = kelly_pct * rules.get("kelly_fraction", config.KELLY_FRACTION)
        
        raw_bet = bankroll * fractional_kelly
        
        # Respect max position size from config
        max_pos_pct = cfg.get("max_position_size_pct", 0.05)
        max_bankroll_pct = bankroll * max_pos_pct
        
        bet_size = min(
            raw_bet, 
            max_bankroll_pct, 
            rules.get("max_trade_dollars", config.MAX_TRADE_DOLLARS), 
            rules.get("max_market_dollars", config.MAX_MARKET_DOLLARS)
        )
        return max(0.0, bet_size)
