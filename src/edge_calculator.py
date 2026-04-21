from __future__ import annotations
import scipy.stats # type: ignore

class EdgeCalculator:
    def calculate_probability(self, forecast_temp: float, rmse: float, min_temp: float, max_temp: float) -> float:
        min_t = min_temp if min_temp != float("-inf") else -1000.0
        max_t = max_temp if max_temp != float("inf") else 1000.0
        
        prob = scipy.stats.norm.cdf(max_t, loc=forecast_temp, scale=rmse) - \
               scipy.stats.norm.cdf(min_t, loc=forecast_temp, scale=rmse)
        return float(prob)
        
    def calculate_edge(self, true_prob: float, market_price: float) -> float:
        return true_prob - market_price
