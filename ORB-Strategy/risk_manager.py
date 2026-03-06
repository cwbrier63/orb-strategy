from AlgorithmImports import *
import math


class RiskManager:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self.daily_long_count = 0
        self.daily_short_count = 0
        self.daily_long_losses = 0
        self.daily_short_losses = 0

    def calculate_shares(self, symbol, max_dd_pct, price):
        """
        Replicates TTP spreadsheet formula.
        max_dd_pct: from variance backtest (e.g. -0.08 for -8% max drawdown)
        """
        adj_risk = self.config.BASE_DAILY_RISK * self.config.REGIME_CURRENT
        max_position_dollars = adj_risk / abs(max_dd_pct)
        shares = math.floor(max_position_dollars / price)
        return max(shares, 0)

    def can_trade_long(self):
        return (self.daily_long_count < self.config.MAX_DAILY_LONGS
                and self.daily_long_losses < self.config.MAX_DAILY_LOSSES_LONG)

    def can_trade_short(self):
        return (self.daily_short_count < self.config.MAX_DAILY_SHORTS
                and self.daily_short_losses < self.config.MAX_DAILY_LOSSES_SHORT)

    def record_long(self):
        self.daily_long_count += 1

    def record_short(self):
        self.daily_short_count += 1

    def record_loss(self, is_long):
        if is_long:
            self.daily_long_losses += 1
        else:
            self.daily_short_losses += 1

    def reset_daily(self):
        self.daily_long_count = 0
        self.daily_short_count = 0
        self.daily_long_losses = 0
        self.daily_short_losses = 0
