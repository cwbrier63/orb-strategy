from AlgorithmImports import *


class SignalEngine:
    def __init__(self, algorithm, config, orb_calculator, indicator_manager):
        self.algo = algorithm
        self.config = config
        self.orb = orb_calculator
        self.indicators = indicator_manager
        # Previous bar tracking for higher/lower close filter
        self.prev_bars = {}
        self.current_bars = {}
        # Entry window tracking — bar index when breakout first detected
        self.long_breakout_bar = {}
        self.short_breakout_bar = {}
        self.bar_count = {}
        # Gap pct per symbol (set from main.py after direction tagging)
        self.gap_pcts = {}
        # Rejection counters — TRADE-level (one per symbol/reason/day)
        self.reject_counts = {
            "GAP_DIRECTION": 0,
            "VWAP": 0,
            "ATR_ZERO": 0,
            "TIME_CUTOFF": 0,
            "EMA_ALIGN": 0,
            "HIGHER_CLOSE": 0,
            "HIGHER_OPEN": 0,
            "VOLUME_RISING": 0,
            "WICK": 0,
            "ENTRY_WINDOW": 0,
        }
        self.breakout_candidates = 0
        # Daily dedup: symbol -> set of reasons already counted today
        self._daily_rejected = {}
        # Buffer for ObjectStore CSV (first rejection per symbol/reason/day)
        self._reject_buffer = []

    def reset_daily(self):
        self.long_breakout_bar.clear()
        self.short_breakout_bar.clear()
        self.bar_count.clear()
        self._daily_rejected.clear()

    def set_gap_pct(self, symbol, gap_pct):
        """Store gap pct (decimal) for gap direction gate."""
        self.gap_pcts[symbol] = gap_pct

    def get_reject_counts(self):
        return dict(self.reject_counts)

    def get_breakout_candidates(self):
        return self.breakout_candidates

    def get_and_clear_reject_buffer(self):
        """Return buffered rejections and clear. Called by main to write to ObjectStore."""
        buf = list(self._reject_buffer)
        self._reject_buffer.clear()
        return buf

    def update_prev_bar(self, symbol, bar):
        """Call from on_data() every bar to track previous bar.
        Must be called BEFORE check_long/check_short so prev_bars
        holds the bar BEFORE the current one."""
        # Shift: current becomes previous, then store new current
        self.prev_bars[symbol] = self.current_bars.get(symbol)
        self.current_bars[symbol] = bar
        self.bar_count[symbol] = self.bar_count.get(symbol, 0) + 1

    # ─── Raw filter evaluations (no toggle check) ────────────────

    def _eval_ema_align(self, symbol, is_long):
        ema9 = self.indicators.get_ema_fast(symbol)
        ema20 = self.indicators.get_ema_mid(symbol)
        return ema9 > ema20 if is_long else ema9 < ema20

    def _eval_vwap(self, symbol, bar, is_long):
        vwap = self.indicators.get_vwap(symbol)
        return bar.close > vwap if is_long else bar.close < vwap

    def _eval_higher_close(self, symbol, bar, is_long):
        prev = self.prev_bars.get(symbol)
        if prev is None:
            return True
        return bar.close > prev.close if is_long else bar.close < prev.close

    def _eval_higher_open(self, symbol, bar, is_long):
        prev = self.prev_bars.get(symbol)
        if prev is None:
            return True
        return bar.open > prev.open if is_long else bar.open < prev.open

    def _eval_volume_rising(self, symbol, bar):
        prev = self.prev_bars.get(symbol)
        if prev is None:
            return True
        return bar.volume > prev.volume

    def _eval_wick(self, bar, is_long):
        body = abs(bar.close - bar.open)
        if body == 0:
            return True
        if is_long:
            wick = bar.high - max(bar.close, bar.open)
        else:
            wick = min(bar.close, bar.open) - bar.low
        return (wick / body) * 100 <= self.config.MAX_WICK_PCT

    def _eval_entry_window_long(self, symbol):
        """Evaluate AND track entry window. Always called for tracking."""
        current = self.bar_count.get(symbol, 0)
        breakout_bar = self.long_breakout_bar.get(symbol)
        if breakout_bar is None:
            self.long_breakout_bar[symbol] = current
            return True
        if current - breakout_bar <= self.config.ENTRY_WINDOW_BARS:
            return True
        self.long_breakout_bar.pop(symbol, None)
        return False

    def _eval_entry_window_short(self, symbol):
        current = self.bar_count.get(symbol, 0)
        breakout_bar = self.short_breakout_bar.get(symbol)
        if breakout_bar is None:
            self.short_breakout_bar[symbol] = current
            return True
        if current - breakout_bar <= self.config.ENTRY_WINDOW_BARS:
            return True
        self.short_breakout_bar.pop(symbol, None)
        return False

    def _eval_gap_direction(self, symbol, is_long):
        """Check if gap is too large against the trade direction."""
        gap_pct = self.gap_pcts.get(symbol, 0)
        threshold = self.config.GAP_REJECT_THRESHOLD
        if is_long and gap_pct < -threshold:
            return False
        if not is_long and gap_pct > threshold:
            return False
        return True

    # ─── Counterfactual filter snapshot ──────────────────────────

    def evaluate_filters_at_entry(self, symbol, bar, is_long):
        """Evaluate all entry filters unconditionally at entry time.
        Returns dict of raw pass/fail for cf_ stamping on trade record."""
        # Entry window: read current state (already tracked by check_long/check_short)
        current = self.bar_count.get(symbol, 0)
        if is_long:
            breakout_bar = self.long_breakout_bar.get(symbol)
        else:
            breakout_bar = self.short_breakout_bar.get(symbol)
        if breakout_bar is None:
            entry_window_pass = True
        else:
            entry_window_pass = current - breakout_bar <= self.config.ENTRY_WINDOW_BARS

        return {
            'cf_gap_direction_pass': self._eval_gap_direction(symbol, is_long),
            'cf_ema_align_pass': self._eval_ema_align(symbol, is_long),
            'cf_vwap_pass': self._eval_vwap(symbol, bar, is_long),
            'cf_higher_close_pass': self._eval_higher_close(symbol, bar, is_long),
            'cf_higher_open_pass': self._eval_higher_open(symbol, bar, is_long),
            'cf_volume_rising_pass': self._eval_volume_rising(symbol, bar),
            'cf_max_wick_pass': self._eval_wick(bar, is_long),
            'cf_entry_window_pass': entry_window_pass,
        }

    # ─── Rejection logging (trade-level: one count per symbol/reason/day) ──

    def _log_reject(self, symbol, direction, reason, bar):
        """Count rejection once per symbol/reason/day. No QC log — saves to daily reject buffer."""
        sym_key = str(symbol)
        if sym_key not in self._daily_rejected:
            self._daily_rejected[sym_key] = set()

        # Only increment counter and buffer on first occurrence per symbol/reason/day
        if reason not in self._daily_rejected[sym_key]:
            self._daily_rejected[sym_key].add(reason)
            self.reject_counts[reason] = self.reject_counts.get(reason, 0) + 1
            # Buffer first rejection per symbol/reason for ObjectStore CSV
            self._reject_buffer.append({
                "time": self.algo.time.strftime("%Y-%m-%d %H:%M"),
                "symbol": str(symbol),
                "direction": direction,
                "reason": reason,
                "close": bar.close,
                "open": bar.open,
                "ema9": self.indicators.get_ema_fast(symbol),
                "ema20": self.indicators.get_ema_mid(symbol),
                "gap_pct": self.gap_pcts.get(symbol, 0),
            })

    # ─── Entry signal checks ────────────────────────────────────

    def check_long(self, symbol, bar):
        if not self.orb.is_locked(symbol):
            return False

        if not self.indicators.is_ready(symbol):
            return False

        orb_high = self.orb.get_high(symbol)
        if orb_high is None:
            return False

        # Price breaks above ORB high + long offset on completed 1m bar close
        if bar.close <= orb_high + self.config.LONG_BREAKOUT_OFFSET:
            return False

        # This is a breakout candidate — count it and log rejections from here
        self.breakout_candidates += 1

        # Gap direction gate (before all other filters)
        if self.config.USE_GAP_DIRECTION_GATE and not self._eval_gap_direction(symbol, is_long=True):
            self._log_reject(symbol, "LONG", "GAP_DIRECTION", bar)
            return False

        # Close > VWAP (toggleable)
        if self.config.LONG_REQUIRE_VWAP and not self._eval_vwap(symbol, bar, is_long=True):
            self._log_reject(symbol, "LONG", "VWAP", bar)
            return False

        # ATR > 0 (indicator is ready)
        if self.indicators.get_atr(symbol) <= 0:
            self._log_reject(symbol, "LONG", "ATR_ZERO", bar)
            return False

        # Current time < 3:30 PM ET (no new entries in last 30 min)
        if self.algo.time.time() >= time(15, 30):
            self._log_reject(symbol, "LONG", "TIME_CUTOFF", bar)
            return False

        # Filter 1: EMA alignment
        if self.config.LONG_REQUIRE_EMA_ALIGN and not self._eval_ema_align(symbol, is_long=True):
            self._log_reject(symbol, "LONG", "EMA_ALIGN", bar)
            return False

        # Filter 2: Higher close
        if self.config.LONG_REQUIRE_HIGHER_CLOSE and not self._eval_higher_close(symbol, bar, is_long=True):
            self._log_reject(symbol, "LONG", "HIGHER_CLOSE", bar)
            return False

        # Filter 3: Higher open
        if self.config.LONG_REQUIRE_HIGHER_OPEN and not self._eval_higher_open(symbol, bar, is_long=True):
            self._log_reject(symbol, "LONG", "HIGHER_OPEN", bar)
            return False

        # Filter 4: Volume rising
        if self.config.LONG_REQUIRE_VOLUME_RISING and not self._eval_volume_rising(symbol, bar):
            self._log_reject(symbol, "LONG", "VOLUME_RISING", bar)
            return False

        # Filter 5: Max wick %
        if self.config.LONG_REQUIRE_MAX_WICK and not self._eval_wick(bar, is_long=True):
            self._log_reject(symbol, "LONG", "WICK", bar)
            return False

        # Filter 6: Entry window (always evaluate for tracking, only gate on toggle)
        entry_window_ok = self._eval_entry_window_long(symbol)
        if self.config.LONG_REQUIRE_ENTRY_WINDOW and not entry_window_ok:
            self._log_reject(symbol, "LONG", "ENTRY_WINDOW", bar)
            return False

        return True

    def check_short(self, symbol, bar):
        if not self.orb.is_locked(symbol):
            return False

        if not self.indicators.is_ready(symbol):
            return False

        orb_low = self.orb.get_low(symbol)
        if orb_low is None:
            return False

        # Price breaks below ORB low - short offset on completed 1m bar close
        if bar.close >= orb_low - self.config.SHORT_BREAKOUT_OFFSET:
            return False

        # This is a breakout candidate — count it and log rejections from here
        self.breakout_candidates += 1

        # Gap direction gate (before all other filters)
        if self.config.USE_GAP_DIRECTION_GATE and not self._eval_gap_direction(symbol, is_long=False):
            self._log_reject(symbol, "SHORT", "GAP_DIRECTION", bar)
            return False

        # Close < VWAP (toggleable)
        if self.config.SHORT_REQUIRE_VWAP and not self._eval_vwap(symbol, bar, is_long=False):
            self._log_reject(symbol, "SHORT", "VWAP", bar)
            return False

        # ATR > 0 (indicator is ready)
        if self.indicators.get_atr(symbol) <= 0:
            self._log_reject(symbol, "SHORT", "ATR_ZERO", bar)
            return False

        # Current time < 3:30 PM ET
        if self.algo.time.time() >= time(15, 30):
            self._log_reject(symbol, "SHORT", "TIME_CUTOFF", bar)
            return False

        # Filter 1: EMA alignment
        if self.config.SHORT_REQUIRE_EMA_ALIGN and not self._eval_ema_align(symbol, is_long=False):
            self._log_reject(symbol, "SHORT", "EMA_ALIGN", bar)
            return False

        # Filter 2: Lower close
        if self.config.SHORT_REQUIRE_HIGHER_CLOSE and not self._eval_higher_close(symbol, bar, is_long=False):
            self._log_reject(symbol, "SHORT", "HIGHER_CLOSE", bar)
            return False

        # Filter 3: Lower open
        if self.config.SHORT_REQUIRE_HIGHER_OPEN and not self._eval_higher_open(symbol, bar, is_long=False):
            self._log_reject(symbol, "SHORT", "HIGHER_OPEN", bar)
            return False

        # Filter 4: Volume rising
        if self.config.SHORT_REQUIRE_VOLUME_RISING and not self._eval_volume_rising(symbol, bar):
            self._log_reject(symbol, "SHORT", "VOLUME_RISING", bar)
            return False

        # Filter 5: Max wick %
        if self.config.SHORT_REQUIRE_MAX_WICK and not self._eval_wick(bar, is_long=False):
            self._log_reject(symbol, "SHORT", "WICK", bar)
            return False

        # Filter 6: Entry window (always evaluate for tracking, only gate on toggle)
        entry_window_ok = self._eval_entry_window_short(symbol)
        if self.config.SHORT_REQUIRE_ENTRY_WINDOW and not entry_window_ok:
            self._log_reject(symbol, "SHORT", "ENTRY_WINDOW", bar)
            return False

        return True
