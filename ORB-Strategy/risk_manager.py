from AlgorithmImports import *
import math


class RiskManager:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        # Per-symbol daily counters: {symbol_str: count}
        self._symbol_long_count = {}
        self._symbol_short_count = {}
        self._symbol_long_losses = {}
        self._symbol_short_losses = {}
        # Global daily counters
        self._total_long_entries = 0
        self._total_short_entries = 0
        self._total_losses = 0
        self.allocated_dollars = 0.0
        # Concurrent open position tracking
        self._open_longs = set()    # symbol strings currently open long
        self._open_shorts = set()   # symbol strings currently open short

    # Tier-based sizing multipliers (applied on top of regime multiplier)
    TIER_MULTIPLIERS = {1: 1.0, 2: 0.75, 3: 0.50}

    def calculate_shares(self, symbol, max_dd_pct, price, tier=None):
        """
        Replicates TTP spreadsheet formula.
        max_dd_pct: from variance backtest (e.g. -0.08 for -8% max drawdown)
        tier: variance tier (1/2/3) — scales regime multiplier down for lower tiers
        """
        regime = self.config.REGIME_CURRENT
        if tier is not None:
            regime *= self.TIER_MULTIPLIERS.get(tier, 1.0)
        adj_risk = self.config.BASE_DAILY_RISK * regime
        max_position_dollars = adj_risk / abs(max_dd_pct)
        shares = math.floor(max_position_dollars / price)
        return max(shares, 0)

    def check_allocation(self, shares, price):
        """Return True if adding this position stays within capital allocation limit."""
        new_dollars = shares * price
        return (self.allocated_dollars + new_dollars) <= self.config.MAX_TOTAL_ALLOCATED

    def add_allocation(self, shares, price):
        self.allocated_dollars += shares * price

    def remove_allocation(self, shares, price):
        self.allocated_dollars = max(0.0, self.allocated_dollars - (shares * price))

    def can_trade_long(self, symbol):
        """Check per-symbol limit, global limit, concurrent limit, and loss circuit breaker."""
        sym = str(symbol)
        count = self._symbol_long_count.get(sym, 0)
        losses = self._symbol_long_losses.get(sym, 0)
        return (count < self.config.MAX_DAILY_LONGS
                and losses < self.config.MAX_DAILY_LOSSES_LONG
                and self._total_long_entries < self.config.MAX_DAILY_TOTAL_LONGS
                and self._total_losses < self.config.MAX_DAILY_TOTAL_LOSSES
                and len(self._open_longs) < self.config.MAX_LONGS)

    def can_trade_short(self, symbol):
        """Check per-symbol limit, global limit, concurrent limit, and loss circuit breaker."""
        sym = str(symbol)
        count = self._symbol_short_count.get(sym, 0)
        losses = self._symbol_short_losses.get(sym, 0)
        return (count < self.config.MAX_DAILY_SHORTS
                and losses < self.config.MAX_DAILY_LOSSES_SHORT
                and self._total_short_entries < self.config.MAX_DAILY_TOTAL_SHORTS
                and self._total_losses < self.config.MAX_DAILY_TOTAL_LOSSES
                and len(self._open_shorts) < self.config.MAX_SHORTS)

    def record_long(self, symbol):
        sym = str(symbol)
        self._symbol_long_count[sym] = self._symbol_long_count.get(sym, 0) + 1
        self._total_long_entries += 1
        self._open_longs.add(sym)

    def record_short(self, symbol):
        sym = str(symbol)
        self._symbol_short_count[sym] = self._symbol_short_count.get(sym, 0) + 1
        self._total_short_entries += 1
        self._open_shorts.add(sym)

    def close_position(self, symbol):
        """Remove symbol from open position sets when exiting."""
        sym = str(symbol)
        self._open_longs.discard(sym)
        self._open_shorts.discard(sym)

    def record_loss(self, symbol, is_long):
        sym = str(symbol)
        self._total_losses += 1
        if is_long:
            self._symbol_long_losses[sym] = self._symbol_long_losses.get(sym, 0) + 1
        else:
            self._symbol_short_losses[sym] = self._symbol_short_losses.get(sym, 0) + 1

    def get_symbol_long_count(self, symbol):
        return self._symbol_long_count.get(str(symbol), 0)

    def get_symbol_short_count(self, symbol):
        return self._symbol_short_count.get(str(symbol), 0)

    def get_symbol_long_losses(self, symbol):
        return self._symbol_long_losses.get(str(symbol), 0)

    def get_symbol_short_losses(self, symbol):
        return self._symbol_short_losses.get(str(symbol), 0)

    def open_long_count(self):
        return len(self._open_longs)

    def open_short_count(self):
        return len(self._open_shorts)

    def total_long_entries(self):
        return self._total_long_entries

    def total_short_entries(self):
        return self._total_short_entries

    def total_losses(self):
        return self._total_losses

    def reset_daily(self):
        self._symbol_long_count.clear()
        self._symbol_short_count.clear()
        self._symbol_long_losses.clear()
        self._symbol_short_losses.clear()
        self._total_long_entries = 0
        self._total_short_entries = 0
        self._total_losses = 0
        self.allocated_dollars = 0.0
        self._open_longs.clear()
        self._open_shorts.clear()
