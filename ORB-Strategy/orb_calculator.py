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

        # Use direction-specific close time during forced optimization
        if self.config.FORCE_DIRECTION == 1:
            lock_time = self.config.LONG_ORB_CLOSE_TIME
        elif self.config.FORCE_DIRECTION == -1:
            lock_time = self.config.SHORT_ORB_CLOSE_TIME
        else:
            lock_time = max(self.config.LONG_ORB_CLOSE_TIME, self.config.SHORT_ORB_CLOSE_TIME)

        if bar_time >= lock_time:
            if self.orb_high.get(symbol) is not None:
                self.locked[symbol] = True
                self.orb_range[symbol] = self.orb_high[symbol] - self.orb_low[symbol]
                self.algo.debug(
                    f"[ORB LOCKED] {symbol} H={self.orb_high[symbol]:.2f} "
                    f"L={self.orb_low[symbol]:.2f} R={self.orb_range[symbol]:.2f}"
                )
            return

        # Bar is within ORB window
        if self.orb_high.get(symbol) is None:
            self.orb_high[symbol] = bar.high
            self.orb_low[symbol] = bar.low
        else:
            self.orb_high[symbol] = max(self.orb_high[symbol], bar.high)
            self.orb_low[symbol] = min(self.orb_low[symbol], bar.low)

    def backfill(self, symbol, history_df):
        """Build ORB retroactively from historical minute bars when bot starts late.
        history_df: DataFrame from self.history() with columns high, low and a datetime index."""
        if self.locked.get(symbol, False):
            return  # Already locked

        orb_open = self.config.ORB_OPEN_TIME
        # Use the latest close time across directions
        if self.config.FORCE_DIRECTION == 1:
            lock_time = self.config.LONG_ORB_CLOSE_TIME
        elif self.config.FORCE_DIRECTION == -1:
            lock_time = self.config.SHORT_ORB_CLOSE_TIME
        else:
            lock_time = max(self.config.LONG_ORB_CLOSE_TIME, self.config.SHORT_ORB_CLOSE_TIME)

        if history_df is None or history_df.empty:
            return

        # Handle MultiIndex (Symbol + Time levels) from self.history(symbol, ...)
        if hasattr(history_df.index, 'levels'):
            # Extract data for this symbol from MultiIndex
            try:
                df = history_df.loc[symbol]
            except KeyError:
                return
        else:
            df = history_df

        # Now filter by time on the datetime index
        orb_bars = df[
            (df.index.time >= orb_open) & (df.index.time < lock_time)
        ]
        if orb_bars.empty:
            return

        self.orb_high[symbol] = float(orb_bars["high"].max())
        self.orb_low[symbol] = float(orb_bars["low"].min())
        self.orb_range[symbol] = self.orb_high[symbol] - self.orb_low[symbol]
        self.locked[symbol] = True
        self.algo.debug(
            f"[ORB BACKFILL] {symbol} H={self.orb_high[symbol]:.2f} "
            f"L={self.orb_low[symbol]:.2f} R={self.orb_range[symbol]:.2f} "
            f"(from {len(orb_bars)} bars)"
        )

    def is_locked(self, symbol):
        return self.locked.get(symbol, False)

    def get_high(self, symbol):
        return self.orb_high.get(symbol)

    def get_low(self, symbol):
        return self.orb_low.get(symbol)

    def get_range(self, symbol):
        return self.orb_range.get(symbol)
