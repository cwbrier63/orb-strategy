from AlgorithmImports import *


class OrbCalculator:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self.orb_high = {}
        self.orb_low = {}
        self.orb_range = {}
        self.locked = {}

    def reset(self, symbol):
        self.orb_high[symbol] = None
        self.orb_low[symbol] = None
        self.orb_range[symbol] = None
        self.locked[symbol] = False

    def update(self, symbol, bar):
        if self.locked.get(symbol, False):
            return

        bar_time = bar.time.time()

        if bar_time < self.config.ORB_OPEN_TIME:
            return

        if bar_time >= self.config.ORB_CLOSE_TIME:
            if self.orb_high.get(symbol) is not None:
                self.locked[symbol] = True
                self.orb_range[symbol] = self.orb_high[symbol] - self.orb_low[symbol]
                self.algo.debug(
                    f"[ORB LOCKED] {symbol} H={self.orb_high[symbol]:.2f} "
                    f"L={self.orb_low[symbol]:.2f} R={self.orb_range[symbol]:.2f}"
                )
            return

        # Bar is within ORB window (9:30–9:34 bars)
        if self.orb_high.get(symbol) is None:
            self.orb_high[symbol] = bar.high
            self.orb_low[symbol] = bar.low
        else:
            self.orb_high[symbol] = max(self.orb_high[symbol], bar.high)
            self.orb_low[symbol] = min(self.orb_low[symbol], bar.low)

    def is_locked(self, symbol):
        return self.locked.get(symbol, False)

    def get_high(self, symbol):
        return self.orb_high.get(symbol)

    def get_low(self, symbol):
        return self.orb_low.get(symbol)

    def get_range(self, symbol):
        return self.orb_range.get(symbol)
