from AlgorithmImports import *
import math


class RiskManager:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self.daily_trade_count = 0

    def calculate_shares(self, symbol, max_dd_pct, price):
        """
        Replicates TTP spreadsheet formula.
        max_dd_pct: from variance backtest (e.g. -0.08 for -8% max drawdown)
        """
        adj_risk = self.config.BASE_DAILY_RISK * self.config.REGIME_CURRENT
        max_position_dollars = adj_risk / abs(max_dd_pct)
        shares = math.floor(max_position_dollars / price)
        return max(shares, 0)

    def can_trade(self):
        return self.daily_trade_count < self.config.MAX_DAILY_TRADES

    def record_trade(self):
        self.daily_trade_count += 1

    def reset_daily(self):
        self.daily_trade_count = 0
