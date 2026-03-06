from AlgorithmImports import *


class TradeManager:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self.stops = {}
        self.entries = {}

    def register_entry(self, symbol, entry_price, is_long):
        self.entries[symbol] = {"price": entry_price, "is_long": is_long}
        if is_long:
            self.stops[symbol] = 0
        else:
            self.stops[symbol] = float("inf")

    def update_trail(self, symbol, current_price, atr):
        if symbol not in self.entries:
            return

        entry_price = self.entries[symbol]["price"]
        is_long = self.entries[symbol]["is_long"]

        profit_in_atrs = abs(current_price - entry_price) / atr if atr > 0 else 0

        # Select direction-specific ATR trail parameters
        if is_long:
            tier2_threshold = self.config.LONG_ATR_PROFIT_TIER2
            tier1_threshold = self.config.LONG_ATR_PROFIT_TIER1
            tier2_mult = self.config.LONG_ATR_TIER2_MULTIPLIER
            tier1_mult = self.config.LONG_ATR_TIER1_MULTIPLIER
            base_mult = self.config.LONG_ATR_BASE_MULTIPLIER
        else:
            tier2_threshold = self.config.SHORT_ATR_PROFIT_TIER2
            tier1_threshold = self.config.SHORT_ATR_PROFIT_TIER1
            tier2_mult = self.config.SHORT_ATR_TIER2_MULTIPLIER
            tier1_mult = self.config.SHORT_ATR_TIER1_MULTIPLIER
            base_mult = self.config.SHORT_ATR_BASE_MULTIPLIER

        if profit_in_atrs >= tier2_threshold:
            multiplier = tier2_mult
        elif profit_in_atrs >= tier1_threshold:
            multiplier = tier1_mult
        else:
            multiplier = base_mult

        trail_distance = atr * multiplier

        if is_long:
            new_stop = current_price - trail_distance
            # Ratchet: stop only moves up, never down
            self.stops[symbol] = max(new_stop, self.stops.get(symbol, 0))
        else:
            new_stop = current_price + trail_distance
            # Ratchet: stop only moves down, never up
            self.stops[symbol] = min(new_stop, self.stops.get(symbol, float("inf")))

    def check_stop(self, symbol, current_price):
        if symbol not in self.entries:
            return False

        is_long = self.entries[symbol]["is_long"]
        stop = self.stops.get(symbol)

        if stop is None:
            return False

        if is_long and current_price <= stop:
            return True
        if not is_long and current_price >= stop:
            return True

        return False

    def get_stop(self, symbol):
        return self.stops.get(symbol)

    def is_long(self, symbol):
        if symbol not in self.entries:
            return None
        return self.entries[symbol]["is_long"]

    def remove(self, symbol):
        self.entries.pop(symbol, None)
        self.stops.pop(symbol, None)

    def reset(self):
        self.entries.clear()
        self.stops.clear()
