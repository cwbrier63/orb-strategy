from AlgorithmImports import *

# ═══════════════════════════════════════════
# Trade Log Column Definitions
# ═══════════════════════════════════════════
TRADE_LOG_COLUMNS = [
    # Group 1: Trade Identity & Outcome
    'trade_id', 'date', 'symbol', 'direction',
    'entry_time', 'exit_time', 'duration_bars',
    'entry_price', 'exit_price', 'shares', 'pnl', 'pnl_pct',
    'mae', 'mae_pct', 'mfe', 'mfe_pct', 'mfe_captured_pct',
    'highest', 'lowest', 'reason',
    # Group 2: Stop State at Exit
    'trail_activated', 'trail_stop', 'hard_stop',
    # Group 3: Market Context at Entry
    'orb_high', 'orb_low', 'orb_range', 'gap_pct',
    'atr_entry', 'vwap_entry', 'ema9_entry', 'ema20_entry', 'ema50_entry',
    # Group 4: Config Parameters (direction-specific)
    'p_orb_minutes', 'p_breakout_offset', 'p_hard_stop_pct',
    'p_atr_base_mult', 'p_atr_tier1_mult', 'p_atr_tier2_mult',
    'p_atr_profit_tier1', 'p_atr_profit_tier2', 'p_atr_activation_pct', 'p_r_target',
    # Group 4: Config Parameters (shared)
    'p_account_size', 'p_base_daily_risk', 'p_max_total_allocated', 'p_regime_current',
    'p_gap_filter_pct', 'p_ema_fast', 'p_ema_mid', 'p_ema_slow', 'p_atr_period',
    'p_max_daily_longs', 'p_max_daily_shorts',
    'p_max_daily_losses_long', 'p_max_daily_losses_short', 'p_force_direction',
    # Group 5: Filter Flags at Entry (config state: True/False)
    'f_gap_direction_gate', 'f_ema_align', 'f_vwap',
    'f_higher_close', 'f_higher_open', 'f_volume_rising',
    'f_max_wick', 'f_entry_window',
    'f_ema_cross_exit', 'f_vwap_recross_exit',
    # Group 6: Counterfactual Entry Filter Evaluation (raw pass/fail at entry)
    'cf_gap_direction_pass', 'cf_ema_align_pass', 'cf_vwap_pass',
    'cf_higher_close_pass', 'cf_higher_open_pass', 'cf_volume_rising_pass',
    'cf_max_wick_pass', 'cf_entry_window_pass',
    # Group 7: Counterfactual Exit Analysis
    'cf_r0p5_price', 'cf_r0p5_hit',
    'cf_r1_price', 'cf_r1_hit',
    'cf_r1p5_price', 'cf_r1p5_hit',
    'cf_r2_price', 'cf_r2_hit',
    'cf_r3_price', 'cf_r3_hit',
    'cf_trail_activation_price', 'cf_trail_activation_hit',
    'cf_vwap_recross_price', 'cf_vwap_recross_hit',
    'cf_ema_cross_at_entry', 'cf_ema9_minus_ema20',
    'cf_breakeven_price', 'cf_above_breakeven_at_exit',
]


class TradeManager:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self.stops = {}
        self.entries = {}
        self.open_records = {}

    # ─── Entry Registration ───────────────────────────────────────

    def register_entry(self, symbol, entry_price, is_long, atr, orb_range):
        if is_long:
            hard_stop = entry_price * (1 - self.config.LONG_HARD_STOP_PCT)
            activation_pct = self.config.LONG_ATR_ACTIVATION_PCT
            r_target = self.config.LONG_R_TARGET
        else:
            hard_stop = entry_price * (1 + self.config.SHORT_HARD_STOP_PCT)
            activation_pct = self.config.SHORT_ATR_ACTIVATION_PCT
            r_target = self.config.SHORT_R_TARGET

        # R-target take profit price (0 = disabled)
        r_take_profit = None
        if r_target > 0 and orb_range is not None and orb_range > 0:
            if is_long:
                r_take_profit = entry_price + orb_range * r_target
            else:
                r_take_profit = entry_price - orb_range * r_target

        self.entries[symbol] = {
            "price": entry_price,
            "is_long": is_long,
            "hard_stop": hard_stop,
            "atr": atr,
            "activation_threshold": atr * (activation_pct / 100),
            "trail_activated": False,
            "highest_since_entry": entry_price,
            "lowest_since_entry": entry_price,
            "r_take_profit": r_take_profit,
            "prev_ema_fast": None,
            "prev_ema_mid": None,
        }
        if is_long:
            self.stops[symbol] = 0
        else:
            self.stops[symbol] = float("inf")

    # ─── Unified Per-Bar Processing ─────────────────────────────────

    def process_bar(self, symbol, bar_close, bar_high, bar_low, atr, vwap_current=None):
        """Unified per-bar evaluation with strict ordering.
        Returns (exited: bool, reason: str).

        Order:
          Step 1 — Update MAE/MFE/highest/lowest tracking
          Step 2 — Check trail activation (uses bar_high/bar_low, not close)
          Step 3 — If trail activated, evaluate trail stop
          Step 4a — VWAP recross exit (before hard stop)
          Step 4b — Evaluate hard stop (only if trail did NOT exit)
          Step 5 — Evaluate R-target and other exits
        """
        if symbol not in self.entries:
            return False, ""

        entry = self.entries[symbol]
        entry_price = entry["price"]
        is_long = entry["is_long"]

        # ── STEP 1: Update tracking ──
        self.update_record(symbol, bar_close, bar_high, bar_low)

        # Update highest/lowest since entry using bar extremes (for trail logic)
        if bar_high > entry["highest_since_entry"]:
            entry["highest_since_entry"] = bar_high
        if bar_low < entry["lowest_since_entry"]:
            entry["lowest_since_entry"] = bar_low

        # ── STEP 2: Check trail activation (bar_high for LONG, bar_low for SHORT) ──
        if is_long:
            peak_profit = bar_high - entry_price
        else:
            peak_profit = entry_price - bar_low

        just_activated = False
        if not entry["trail_activated"]:
            if peak_profit >= entry["activation_threshold"]:
                entry["trail_activated"] = True
                just_activated = True
                self.algo.log(f"[TRAIL ACTIVATED] {symbol} profit={peak_profit:.2f} threshold={entry['activation_threshold']:.2f}")

        # If trail is activated (either just now or previously), compute trail stop
        if entry["trail_activated"]:
            self._compute_trail_stop(symbol, bar_close, atr)

        # ── STEP 3: Trail stop check (uses bar_low for LONG, bar_high for SHORT) ──
        if entry["trail_activated"]:
            stop = self.stops.get(symbol)
            if stop is not None:
                if is_long and bar_low <= stop:
                    self.algo.log(f"[TRAIL STOP] {symbol} bar_low={bar_low:.2f} trail={stop:.2f}")
                    return True, "TRAIL_STOP"
                if not is_long and bar_high >= stop:
                    self.algo.log(f"[TRAIL STOP] {symbol} bar_high={bar_high:.2f} trail={stop:.2f}")
                    return True, "TRAIL_STOP"

        # ── STEP 4a: VWAP recross exit ──
        if self.config.USE_VWAP_RECROSS_EXIT and vwap_current is not None:
            duration = self.open_records[symbol]['duration_bars'] if symbol in self.open_records else 0
            if duration >= self.config.VWAP_RECROSS_MIN_BARS:
                if is_long and bar_low <= vwap_current:
                    self.algo.log(f"[VWAP RECROSS] {symbol} LONG bar_low={bar_low:.2f} vwap={vwap_current:.2f} bars={duration}")
                    return True, "VWAP_RECROSS"
                if not is_long and bar_high >= vwap_current:
                    self.algo.log(f"[VWAP RECROSS] {symbol} SHORT bar_high={bar_high:.2f} vwap={vwap_current:.2f} bars={duration}")
                    return True, "VWAP_RECROSS"

        # ── STEP 4b: Hard stop check (uses bar_low for LONG, bar_high for SHORT) ──
        hard_stop = entry["hard_stop"]
        if is_long and bar_low <= hard_stop:
            # Verification warning: did price reach trail activation during this trade?
            act_price = entry_price + entry["activation_threshold"]
            if entry.get("highest_since_entry", 0) >= act_price:
                self.algo.log(f"[WARN] {symbol} HARD_STOP but activation price {act_price:.2f} was reached (high={entry['highest_since_entry']:.2f})")
            self.algo.log(f"[HARD STOP] {symbol} bar_low={bar_low:.2f} hard_stop={hard_stop:.2f}")
            return True, "HARD_STOP"
        if not is_long and bar_high >= hard_stop:
            act_price = entry_price - entry["activation_threshold"]
            if entry.get("lowest_since_entry", float('inf')) <= act_price:
                self.algo.log(f"[WARN] {symbol} HARD_STOP but activation price {act_price:.2f} was reached (low={entry['lowest_since_entry']:.2f})")
            self.algo.log(f"[HARD STOP] {symbol} bar_high={bar_high:.2f} hard_stop={hard_stop:.2f}")
            return True, "HARD_STOP"

        # ── STEP 5: R-target take profit ──
        r_tp = entry.get("r_take_profit")
        if r_tp is not None:
            if is_long and bar_high >= r_tp:
                self.algo.log(f"[R TARGET] {symbol} bar_high={bar_high:.2f} target={r_tp:.2f}")
                return True, "R_TARGET"
            if not is_long and bar_low <= r_tp:
                self.algo.log(f"[R TARGET] {symbol} bar_low={bar_low:.2f} target={r_tp:.2f}")
                return True, "R_TARGET"

        return False, ""

    def _compute_trail_stop(self, symbol, current_price, atr):
        """Compute tiered ATR trail stop and apply ratchet."""
        entry = self.entries[symbol]
        entry_price = entry["price"]
        is_long = entry["is_long"]

        if is_long:
            peak = entry["highest_since_entry"]
            current_profit = peak - entry_price
        else:
            trough = entry["lowest_since_entry"]
            current_profit = entry_price - trough

        profit_in_atrs = current_profit / atr if atr > 0 else 0

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
            self.stops[symbol] = max(new_stop, self.stops.get(symbol, 0))
        else:
            new_stop = current_price + trail_distance
            self.stops[symbol] = min(new_stop, self.stops.get(symbol, float("inf")))

    def check_ema_cross_exit(self, symbol, ema_fast, ema_mid):
        """Check if EMA9 crossed EMA20 against the position direction."""
        if symbol not in self.entries:
            return False
        if not self.config.EMA_CROSS_EXIT:
            return False

        entry = self.entries[symbol]
        prev_fast = entry.get("prev_ema_fast")
        prev_mid = entry.get("prev_ema_mid")

        # Store current values for next bar's comparison
        entry["prev_ema_fast"] = ema_fast
        entry["prev_ema_mid"] = ema_mid

        # Need previous values to detect a cross
        if prev_fast is None or prev_mid is None:
            return False

        is_long = entry["is_long"]

        if is_long:
            # Long exit: EMA9 was above EMA20, now crosses below
            if prev_fast > prev_mid and ema_fast < ema_mid:
                self.algo.log(f"[EMA CROSS EXIT] {symbol} LONG — EMA9 crossed below EMA20")
                return True
        else:
            # Short exit: EMA9 was below EMA20, now crosses above
            if prev_fast < prev_mid and ema_fast > ema_mid:
                self.algo.log(f"[EMA CROSS EXIT] {symbol} SHORT — EMA9 crossed above EMA20")
                return True

        return False

    # ─── Accessors ────────────────────────────────────────────────

    def get_stop(self, symbol):
        return self.stops.get(symbol)

    def is_long(self, symbol):
        if symbol not in self.entries:
            return None
        return self.entries[symbol]["is_long"]

    # ─── Cleanup ──────────────────────────────────────────────────

    def remove(self, symbol):
        self.entries.pop(symbol, None)
        self.stops.pop(symbol, None)
        self.open_records.pop(symbol, None)

    def reset(self):
        self.entries.clear()
        self.stops.clear()
        self.open_records.clear()

    # ═══════════════════════════════════════════
    # Trade Record System
    # ═══════════════════════════════════════════

    def create_record(self, symbol, trade_id, shares, snapshot, config, filter_evals=None):
        """Create trade record at entry time. Call after register_entry()."""
        entry = self.entries[symbol]
        entry_price = entry["price"]
        is_long = entry["is_long"]
        hard_stop = entry["hard_stop"]
        atr = entry["atr"]

        # R value = risk per share (distance to hard stop)
        r = abs(entry_price - hard_stop)

        # Direction-specific config stamps
        if is_long:
            dir_p = {
                'p_orb_minutes': config.LONG_ORB_MINUTES,
                'p_breakout_offset': config.LONG_BREAKOUT_OFFSET,
                'p_hard_stop_pct': config.LONG_HARD_STOP_PCT,
                'p_atr_base_mult': config.LONG_ATR_BASE_MULTIPLIER,
                'p_atr_tier1_mult': config.LONG_ATR_TIER1_MULTIPLIER,
                'p_atr_tier2_mult': config.LONG_ATR_TIER2_MULTIPLIER,
                'p_atr_profit_tier1': config.LONG_ATR_PROFIT_TIER1,
                'p_atr_profit_tier2': config.LONG_ATR_PROFIT_TIER2,
                'p_atr_activation_pct': config.LONG_ATR_ACTIVATION_PCT,
                'p_r_target': config.LONG_R_TARGET,
            }
        else:
            dir_p = {
                'p_orb_minutes': config.SHORT_ORB_MINUTES,
                'p_breakout_offset': config.SHORT_BREAKOUT_OFFSET,
                'p_hard_stop_pct': config.SHORT_HARD_STOP_PCT,
                'p_atr_base_mult': config.SHORT_ATR_BASE_MULTIPLIER,
                'p_atr_tier1_mult': config.SHORT_ATR_TIER1_MULTIPLIER,
                'p_atr_tier2_mult': config.SHORT_ATR_TIER2_MULTIPLIER,
                'p_atr_profit_tier1': config.SHORT_ATR_PROFIT_TIER1,
                'p_atr_profit_tier2': config.SHORT_ATR_PROFIT_TIER2,
                'p_atr_activation_pct': config.SHORT_ATR_ACTIVATION_PCT,
                'p_r_target': config.SHORT_R_TARGET,
            }

        # Counterfactual R-target prices
        cf_r = {}
        for label, mult in [('0p5', 0.5), ('1', 1.0), ('1p5', 1.5), ('2', 2.0), ('3', 3.0)]:
            if r > 0:
                cf_r[label] = round(entry_price + mult * r, 2) if is_long else round(entry_price - mult * r, 2)
            else:
                cf_r[label] = 0.0

        # Trail activation price
        act_thresh = entry["activation_threshold"]
        cf_trail_act = entry_price + act_thresh if is_long else entry_price - act_thresh

        # EMA cross state at entry
        ema9 = snapshot.get("ema9", 0)
        ema20 = snapshot.get("ema20", 0)
        cf_ema_cross = (ema9 < ema20) if is_long else (ema9 > ema20)

        vwap = snapshot.get("vwap", 0)

        fe = filter_evals or {}

        rec = {
            # Group 1: Trade Identity & Outcome
            'trade_id': trade_id,
            'date': self.algo.time.strftime("%Y-%m-%d"),
            'symbol': str(symbol),
            'direction': 'LONG' if is_long else 'SHORT',
            'entry_time': self.algo.time.strftime("%H:%M"),
            'exit_time': '',
            'duration_bars': 0,
            'entry_price': round(entry_price, 2),
            'exit_price': 0.0,
            'shares': shares,
            'pnl': 0.0,
            'pnl_pct': 0.0,
            'mae': 0.0,
            'mae_pct': 0.0,
            'mfe': 0.0,
            'mfe_pct': 0.0,
            'mfe_captured_pct': 0.0,
            'highest': entry_price,
            'lowest': entry_price,
            'reason': '',
            # Group 2: Stop State at Exit
            'trail_activated': False,
            'trail_stop': 0.0,
            'hard_stop': round(hard_stop, 2),
            # Group 3: Market Context at Entry
            'orb_high': round(snapshot.get("orb_high", 0) or 0, 2),
            'orb_low': round(snapshot.get("orb_low", 0) or 0, 2),
            'orb_range': round(snapshot.get("orb_range", 0) or 0, 2),
            'gap_pct': round((snapshot.get("gap_pct", 0) or 0) * 100, 3),
            'atr_entry': round(atr, 4),
            'vwap_entry': round(vwap, 2),
            'ema9_entry': round(ema9, 2),
            'ema20_entry': round(ema20, 2),
            'ema50_entry': round(snapshot.get("ema50", 0), 2),
            # Group 4: Config Parameters (direction-specific)
            **dir_p,
            # Group 4: Config Parameters (shared)
            'p_account_size': config.ACCOUNT_SIZE,
            'p_base_daily_risk': config.BASE_DAILY_RISK,
            'p_max_total_allocated': config.MAX_TOTAL_ALLOCATED,
            'p_regime_current': config.REGIME_CURRENT,
            'p_gap_filter_pct': config.GAP_FILTER_PCT,
            'p_ema_fast': config.EMA_FAST,
            'p_ema_mid': config.EMA_MID,
            'p_ema_slow': config.EMA_SLOW,
            'p_atr_period': config.ATR_PERIOD,
            'p_max_daily_longs': config.MAX_DAILY_LONGS,
            'p_max_daily_shorts': config.MAX_DAILY_SHORTS,
            'p_max_daily_losses_long': config.MAX_DAILY_LOSSES_LONG,
            'p_max_daily_losses_short': config.MAX_DAILY_LOSSES_SHORT,
            'p_force_direction': config.FORCE_DIRECTION,
            # Group 5: Filter Flags at Entry (config state: True/False)
            'f_gap_direction_gate': config.USE_GAP_DIRECTION_GATE,
            'f_ema_align': config.LONG_REQUIRE_EMA_ALIGN if is_long else config.SHORT_REQUIRE_EMA_ALIGN,
            'f_vwap': config.LONG_REQUIRE_VWAP if is_long else config.SHORT_REQUIRE_VWAP,
            'f_higher_close': config.LONG_REQUIRE_HIGHER_CLOSE if is_long else config.SHORT_REQUIRE_HIGHER_CLOSE,
            'f_higher_open': config.LONG_REQUIRE_HIGHER_OPEN if is_long else config.SHORT_REQUIRE_HIGHER_OPEN,
            'f_volume_rising': config.LONG_REQUIRE_VOLUME_RISING if is_long else config.SHORT_REQUIRE_VOLUME_RISING,
            'f_max_wick': config.LONG_REQUIRE_MAX_WICK if is_long else config.SHORT_REQUIRE_MAX_WICK,
            'f_entry_window': config.LONG_REQUIRE_ENTRY_WINDOW if is_long else config.SHORT_REQUIRE_ENTRY_WINDOW,
            'f_ema_cross_exit': config.EMA_CROSS_EXIT,
            'f_vwap_recross_exit': config.USE_VWAP_RECROSS_EXIT,
            # Group 6: Counterfactual Entry Filter Evaluation
            'cf_gap_direction_pass': fe.get('cf_gap_direction_pass', True),
            'cf_ema_align_pass': fe.get('cf_ema_align_pass', True),
            'cf_vwap_pass': fe.get('cf_vwap_pass', True),
            'cf_higher_close_pass': fe.get('cf_higher_close_pass', True),
            'cf_higher_open_pass': fe.get('cf_higher_open_pass', True),
            'cf_volume_rising_pass': fe.get('cf_volume_rising_pass', True),
            'cf_max_wick_pass': fe.get('cf_max_wick_pass', True),
            'cf_entry_window_pass': fe.get('cf_entry_window_pass', True),
            # Group 7: Counterfactual Exit Analysis
            'cf_r0p5_price': cf_r['0p5'],
            'cf_r0p5_hit': False,
            'cf_r1_price': cf_r['1'],
            'cf_r1_hit': False,
            'cf_r1p5_price': cf_r['1p5'],
            'cf_r1p5_hit': False,
            'cf_r2_price': cf_r['2'],
            'cf_r2_hit': False,
            'cf_r3_price': cf_r['3'],
            'cf_r3_hit': False,
            'cf_trail_activation_price': round(cf_trail_act, 2),
            'cf_trail_activation_hit': False,
            'cf_vwap_recross_price': round(vwap, 2),
            'cf_vwap_recross_hit': False,
            'cf_ema_cross_at_entry': cf_ema_cross,
            'cf_ema9_minus_ema20': round(ema9 - ema20, 4),
            'cf_breakeven_price': round(entry_price, 2),
            'cf_above_breakeven_at_exit': False,
            # Internal tracking (excluded from CSV output)
            '_is_long': is_long,
            '_high_extreme': entry_price,
            '_low_extreme': entry_price,
        }
        self.open_records[symbol] = rec

    def update_record(self, symbol, bar_close, bar_high, bar_low):
        """Update trade record each bar. Call from on_data() for invested symbols."""
        if symbol not in self.open_records:
            return
        rec = self.open_records[symbol]
        rec['duration_bars'] += 1
        is_long = rec['_is_long']
        entry_price = rec['entry_price']

        # Update close-based tracking (for highest/lowest columns)
        if bar_close > rec['highest']:
            rec['highest'] = bar_close
        if bar_close < rec['lowest']:
            rec['lowest'] = bar_close

        # Update high/low extremes (for MAE/MFE and counterfactual hits)
        if bar_high > rec['_high_extreme']:
            rec['_high_extreme'] = bar_high
        if bar_low < rec['_low_extreme']:
            rec['_low_extreme'] = bar_low

        # MAE/MFE from extremes (per-share, always positive)
        if is_long:
            rec['mfe'] = max(0, rec['_high_extreme'] - entry_price)
            rec['mae'] = max(0, entry_price - rec['_low_extreme'])
        else:
            rec['mfe'] = max(0, entry_price - rec['_low_extreme'])
            rec['mae'] = max(0, rec['_high_extreme'] - entry_price)

        # Sync trail_activated from entries
        if symbol in self.entries:
            rec['trail_activated'] = self.entries[symbol].get('trail_activated', False)

    def finalize_record(self, symbol, exit_price, exit_time, pnl, shares, reason):
        """Finalize trade record at exit. Returns record dict or None."""
        if symbol not in self.open_records:
            return None
        rec = self.open_records[symbol]
        is_long = rec['_is_long']
        entry_price = rec['entry_price']

        # Exit fields
        rec['exit_time'] = exit_time.strftime("%H:%M")
        rec['exit_price'] = round(exit_price, 2)
        rec['reason'] = reason
        rec['pnl'] = round(pnl, 2)
        rec['pnl_pct'] = round((pnl / (entry_price * shares)) * 100, 3) if entry_price * shares > 0 else 0.0

        # Finalize MAE/MFE
        rec['mae_pct'] = round((rec['mae'] / entry_price) * 100, 3) if entry_price > 0 else 0.0
        rec['mfe_pct'] = round((rec['mfe'] / entry_price) * 100, 3) if entry_price > 0 else 0.0
        rec['mae'] = round(rec['mae'], 2)
        rec['mfe'] = round(rec['mfe'], 2)

        # MFE captured: what fraction of peak unrealized was realized
        mfe_total = rec['mfe'] * shares
        rec['mfe_captured_pct'] = round((pnl / mfe_total) * 100, 1) if mfe_total > 0 else 0.0

        # Round highest/lowest
        rec['highest'] = round(rec['highest'], 2)
        rec['lowest'] = round(rec['lowest'], 2)

        # Trail stop at exit
        stop = self.stops.get(symbol, 0)
        rec['trail_stop'] = round(stop, 2) if stop != float('inf') else 0.0
        if symbol in self.entries:
            rec['trail_activated'] = self.entries[symbol].get('trail_activated', False)

        # ── Evaluate counterfactual hits ──
        high_ext = rec['_high_extreme']
        low_ext = rec['_low_extreme']

        # R-target hits
        for suffix in ['0p5', '1', '1p5', '2', '3']:
            price_key = f'cf_r{suffix}_price'
            hit_key = f'cf_r{suffix}_hit'
            target = rec[price_key]
            if target > 0:
                if is_long:
                    rec[hit_key] = high_ext >= target
                else:
                    rec[hit_key] = low_ext <= target

        # Trail activation hit
        trail_target = rec['cf_trail_activation_price']
        if is_long:
            rec['cf_trail_activation_hit'] = high_ext >= trail_target
        else:
            rec['cf_trail_activation_hit'] = low_ext <= trail_target

        # VWAP recross hit
        vwap = rec['cf_vwap_recross_price']
        if is_long:
            rec['cf_vwap_recross_hit'] = low_ext <= vwap
        else:
            rec['cf_vwap_recross_hit'] = high_ext >= vwap

        # Breakeven at exit
        if is_long:
            rec['cf_above_breakeven_at_exit'] = exit_price > entry_price
        else:
            rec['cf_above_breakeven_at_exit'] = exit_price < entry_price

        return rec

    @staticmethod
    def format_record_row(record):
        """Format record dict as CSV row string (column order matches TRADE_LOG_COLUMNS)."""
        vals = []
        for col in TRADE_LOG_COLUMNS:
            v = record.get(col, '')
            if isinstance(v, float):
                vals.append(str(round(v, 4)))
            elif isinstance(v, bool):
                vals.append(str(v))
            else:
                vals.append(str(v))
        return ','.join(vals)
