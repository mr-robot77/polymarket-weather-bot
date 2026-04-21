from __future__ import annotations
import config

class KellySizing:
    def calculate_bet_size(self, edge: float, true_prob: float, market_price: float, bankroll: float) -> float:
        if edge <= config.EDGE_THRESHOLD:
            return 0.0
        if market_price <= 0 or market_price >= 1:
            return 0.0
            
        b = (1 - market_price) / market_price
        q = 1 - true_prob
        kelly_pct = (b * true_prob - q) / b
        
        if kelly_pct <= 0:
            return 0.0
            
        fractional_kelly = kelly_pct * config.KELLY_FRACTION
        
        raw_bet = bankroll * fractional_kelly
        max_bankroll_pct = bankroll * 0.05
        
        bet_size = min(raw_bet, max_bankroll_pct, config.MAX_TRADE_DOLLARS, config.MAX_MARKET_DOLLARS)
        return max(0.0, bet_size)
