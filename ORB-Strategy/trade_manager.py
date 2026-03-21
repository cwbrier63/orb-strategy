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
    'p_orb_minutes', 'p_breakout_offset', 'p_hard_stop_mode', 'p_hard_stop_pct', 'p_hard_stop_atr_mult',
    'p_atr_base_mult', 'p_atr_tier1_mult', 'p_atr_tier2_mult',
    'p_atr_profit_tier1', 'p_atr_profit_tier2', 'p_atr_activation_pct',
    'p_use_take_profit', 'p_r_tp1', 'p_r_tp2', 'p_r_tp3',
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
    # Group 6: Universe Selection Context
    'u_source', 'u_tier', 'u_max_dd',
    'u_scanner_gap_pct', 'u_scanner_atr', 'u_scanner_adv',
    # Group 6c: Universe Sheet Fields (from Google Sheets Universe tab)
    'u_gap_pct_sheet', 'u_catalyst', 'u_cat_quality', 'u_var_tier', 'u_final_tier',
    'u_max_dd_sheet', 'u_net_perf', 'u_expectancy', 'u_notes',
    'u_ti_timestamp', 'u_ti_price', 'u_ti_chg_dollar', 'u_ti_chg_pct',
    'u_ti_volume', 'u_ti_rel_vol', 'u_ti_gap_pct', 'u_ti_float',
    'u_ti_atr', 'u_ti_avg_vol_5d', 'u_ti_dist_vwap',
    # Group 6b: Universe Filter Thresholds (config at time of selection)
    'u_min_price', 'u_min_adv', 'u_min_today_volume',
    'u_min_atr', 'u_gap_pct_min', 'u_gap_pct_max',
    'u_max_short_float', 'u_min_float_shares',
    'u_require_eps', 'u_min_market_cap',
    'u_no_earnings_today', 'u_max_symbols', 'u_max_price',
    # Group 7: Real-Time Entry Bar Data
    'prior_close', 'today_open',
    'entry_bar_volume', 'entry_bar_range', 'entry_spread', 'entry_spread_pct',
    'p_max_spread_pct',
    # Group 8: Counterfactual Entry Filter Evaluation (raw pass/fail at entry)
    'cf_gap_direction_pass', 'cf_ema_align_pass', 'cf_vwap_pass',
    'cf_higher_close_pass', 'cf_higher_open_pass', 'cf_volume_rising_pass',
    'cf_max_wick_pass', 'cf_entry_window_pass',
    # Group 9: Counterfactual Exit Analysis
    'cf_r0p5_price', 'cf_r0p5_hit',
    'cf_r1_price', 'cf_r1_hit',
    'cf_r1p5_price', 'cf_r1p5_hit',
    'cf_r2_price', 'cf_r2_hit',
    'cf_r3_price', 'cf_r3_hit',
    'cf_trail_activation_price', 'cf_trail_activation_hit',
    'cf_vwap_recross_price', 'cf_vwap_recross_hit',
    'cf_ema_cross_at_entry', 'cf_ema9_minus_ema20',
    'cf_breakeven_price', 'cf_above_breakeven_at_exit',
    # Group 10: Take Profit Tracking
    'tp1_price', 'tp1_hit', 'tp1_shares', 'tp1_fill_price',
    'tp2_price', 'tp2_hit', 'tp2_shares', 'tp2_fill_price',
    'tp3_price', 'tp3_hit', 'tp3_shares', 'tp3_fill_price',
    # Group 11: SpotGamma Options Data at Entry
    'sg_gamma_regime', 'sg_call_wall', 'sg_put_wall', 'sg_hedge_wall',
    'sg_key_gamma_strike', 'sg_key_delta_strike',
    'sg_cw_dist_pct', 'sg_pw_dist_pct', 'sg_hw_dist_pct',
    'sg_options_impact', 'sg_impact_tier',
    'sg_impl_move_dollar', 'sg_impl_move_pct',
    'sg_est_move_high', 'sg_est_move_low',
    'sg_iv_rank', 'sg_iv_rank_tier',
    'sg_inst_conviction', 'sg_dpi_trend', 'sg_skew_signal',
    'sg_net_gamma', 'sg_gamma_tilt', 'sg_opex_proximity',
    # Group 11b: SpotGamma Filter Counterfactuals
    'cf_sg_gamma_regime_pass', 'cf_sg_conviction_pass', 'cf_sg_range_validation_pass',
    'cf_sg_opex_pass',
    # Group 11c: SpotGamma Config Flags
    'f_sg_enabled', 'f_sg_gamma_regime', 'f_sg_conviction',
    'f_sg_range_validation', 'f_sg_wall_targets', 'f_sg_opex_filter',
]


class TradeManager:
    def __init__(self, algorithm, config, spotgamma_mgr=None):
        self.algo = algorithm
        self.config = config
        self.sg = spotgamma_mgr
        self.stops = {}
        self.entries = {}
        self.open_records = {}

    # ─── Entry Registration ───────────────────────────────────────

    def register_entry(self, symbol, entry_price, is_long, atr, orb_range, total_shares=0):
        if is_long:
            mode = self.config.LONG_HARD_STOP_MODE
            if mode == "atr" and atr > 0:
                hard_stop = entry_price - atr * self.config.LONG_HARD_STOP_ATR_MULT
            else:
                hard_stop = entry_price * (1 - self.config.LONG_HARD_STOP_PCT)
            activation_pct = self.config.LONG_ATR_ACTIVATION_PCT
            r_levels = [self.config.LONG_R_TP1, self.config.LONG_R_TP2, self.config.LONG_R_TP3]
        else:
            mode = self.config.SHORT_HARD_STOP_MODE
            if mode == "atr" and atr > 0:
                hard_stop = entry_price + atr * self.config.SHORT_HARD_STOP_ATR_MULT
            else:
                hard_stop = entry_price * (1 + self.config.SHORT_HARD_STOP_PCT)
            activation_pct = self.config.SHORT_ATR_ACTIVATION_PCT
            r_levels = [self.config.SHORT_R_TP1, self.config.SHORT_R_TP2, self.config.SHORT_R_TP3]

        # Compute TP prices for each active level (R > 0 and valid ORB range)
        tp_prices = [None, None, None]
        if orb_range is not None and orb_range > 0:
            for i, r in enumerate(r_levels):
                if r > 0:
                    if is_long:
                        tp_prices[i] = entry_price + orb_range * r
                    else:
                        tp_prices[i] = entry_price - orb_range * r

        # Auto-size shares per active TP level
        active_count = sum(1 for p in tp_prices if p is not None)
        tp_shares = [0, 0, 0]
        if active_count > 0 and total_shares > 0:
            per_tp = total_shares // active_count
            remainder = total_shares - per_tp * active_count
            idx = 0
            for i in range(3):
                if tp_prices[i] is not None:
                    tp_shares[i] = per_tp + (1 if idx < remainder else 0)
                    idx += 1

        self.entries[symbol] = {
            "price": entry_price,
            "is_long": is_long,
            "hard_stop": hard_stop,
            "atr": atr,
            "orb_range": orb_range,
            "activation_threshold": atr * (activation_pct / 100),
            "trail_activated": False,
            "breakeven_activated": False,
            "highest_since_entry": entry_price,
            "lowest_since_entry": entry_price,
            "tp_prices": tp_prices,
            "tp_shares": tp_shares,
            "tp_hit": [False, False, False],
            "tp_fill_prices": [None, None, None],
            "original_shares": total_shares,
            "prev_ema_fast": None,
            "prev_ema_mid": None,
            "vwap_wrong_side_bars": 0,
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
                self.algo.debug(f"[TRAIL ACTIVATED] {symbol} profit={peak_profit:.2f} threshold={entry['activation_threshold']:.2f}")

        # ── STEP 2b: Breakeven stop — move hard stop to entry when R-trigger is hit ──
        if self.config.USE_BREAKEVEN_STOP and not entry.get("breakeven_activated", False):
            orb_range = entry.get("orb_range", 0)
            if orb_range and orb_range > 0:
                be_distance = orb_range * self.config.BREAKEVEN_R_TRIGGER
                if is_long and (bar_high - entry_price) >= be_distance:
                    entry["hard_stop"] = entry_price
                    entry["breakeven_activated"] = True
                    self.algo.debug(f"[BREAKEVEN] {symbol} LONG hard stop moved to entry {entry_price:.2f}")
                elif not is_long and (entry_price - bar_low) >= be_distance:
                    entry["hard_stop"] = entry_price
                    entry["breakeven_activated"] = True
                    self.algo.debug(f"[BREAKEVEN] {symbol} SHORT hard stop moved to entry {entry_price:.2f}")

        # If trail is activated (either just now or previously), compute trail stop
        if entry["trail_activated"]:
            self._compute_trail_stop(symbol, bar_close, atr)

        # ── STEP 3: Trail stop check (uses bar_low for LONG, bar_high for SHORT) ──
        if entry["trail_activated"]:
            stop = self.stops.get(symbol)
            if stop is not None:
                if is_long and bar_low <= stop:
                    self.algo._log(f"[TRAIL STOP] {symbol} bar_low={bar_low:.2f} trail={stop:.2f}")
                    return True, "TRAIL_STOP"
                if not is_long and bar_high >= stop:
                    self.algo._log(f"[TRAIL STOP] {symbol} bar_high={bar_high:.2f} trail={stop:.2f}")
                    return True, "TRAIL_STOP"

        # ── STEP 4a: VWAP recross exit (consecutive bars wrong side) ──
        if self.config.USE_VWAP_RECROSS_EXIT and vwap_current is not None:
            wrong_side = False
            if is_long and bar_close < vwap_current:
                wrong_side = True
            elif not is_long and bar_close > vwap_current:
                wrong_side = True

            if wrong_side:
                entry["vwap_wrong_side_bars"] += 1
            else:
                entry["vwap_wrong_side_bars"] = 0

            if entry["vwap_wrong_side_bars"] >= self.config.VWAP_RECROSS_MIN_BARS:
                if is_long:
                    self.algo._log(f"[VWAP RECROSS] {symbol} LONG close={bar_close:.2f} vwap={vwap_current:.2f} consecutive={entry['vwap_wrong_side_bars']}")
                else:
                    self.algo._log(f"[VWAP RECROSS] {symbol} SHORT close={bar_close:.2f} vwap={vwap_current:.2f} consecutive={entry['vwap_wrong_side_bars']}")
                return True, "VWAP_RECROSS"

        # ── STEP 4b: Hard stop check (uses bar_low for LONG, bar_high for SHORT) ──
        hard_stop = entry["hard_stop"]
        if is_long and bar_low <= hard_stop:
            # Verification warning: did price reach trail activation during this trade?
            act_price = entry_price + entry["activation_threshold"]
            if entry.get("highest_since_entry", 0) >= act_price:
                self.algo._log(f"[WARN] {symbol} HARD_STOP but activation price {act_price:.2f} was reached (high={entry['highest_since_entry']:.2f})")
            self.algo._log(f"[HARD STOP] {symbol} bar_low={bar_low:.2f} hard_stop={hard_stop:.2f}")
            return True, "HARD_STOP"
        if not is_long and bar_high >= hard_stop:
            act_price = entry_price - entry["activation_threshold"]
            if entry.get("lowest_since_entry", float('inf')) <= act_price:
                self.algo._log(f"[WARN] {symbol} HARD_STOP but activation price {act_price:.2f} was reached (low={entry['lowest_since_entry']:.2f})")
            self.algo._log(f"[HARD STOP] {symbol} bar_high={bar_high:.2f} hard_stop={hard_stop:.2f}")
            return True, "HARD_STOP"

        # ── STEP 5: Tiered R take profit (partial exits) ──
        if self.config.USE_TAKE_PROFIT:
            for i in range(3):
                tp_price = entry["tp_prices"][i]
                if tp_price is not None and not entry["tp_hit"][i]:
                    hit = False
                    if is_long and bar_high >= tp_price:
                        hit = True
                    elif not is_long and bar_low <= tp_price:
                        hit = True
                    if hit:
                        entry["tp_hit"][i] = True
                        entry["tp_fill_prices"][i] = tp_price
                        shares = entry["tp_shares"][i]
                        self.algo._log(f"[TP{i+1}] {symbol} price={tp_price:.2f} shares={shares}")
                        return True, f"TP{i+1}"

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

        # ── SpotGamma wall proximity trail tightening ──
        if self.config.SG_ENABLED and self.config.SG_USE_WALL_TARGETS and self.sg:
            wall = None
            if is_long:
                wall = self.sg.get_call_wall(symbol)
            else:
                wall = self.sg.get_put_wall(symbol)
            if wall is not None and wall > 0:
                dist_to_wall = abs(current_price - wall)
                proximity_threshold = wall * (self.config.SG_WALL_PROXIMITY_PCT / 100)
                if dist_to_wall <= proximity_threshold:
                    trail_distance *= self.config.SG_WALL_TRAIL_MULTIPLIER

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
                self.algo._log(f"[EMA CROSS EXIT] {symbol} LONG — EMA9 crossed below EMA20")
                return True
        else:
            # Short exit: EMA9 was below EMA20, now crosses above
            if prev_fast < prev_mid and ema_fast > ema_mid:
                self.algo._log(f"[EMA CROSS EXIT] {symbol} SHORT — EMA9 crossed above EMA20")
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

    def create_record(self, symbol, trade_id, shares, snapshot, config, filter_evals=None, universe_meta=None, sg_snapshot=None):
        """Create trade record at entry time. Call after register_entry()."""
        entry = self.entries[symbol]
        entry_price = entry["price"]
        is_long = entry["is_long"]
        hard_stop = entry["hard_stop"]
        atr = entry["atr"]

        tp_prices = entry.get("tp_prices", [None, None, None])
        tp_shares = entry.get("tp_shares", [0, 0, 0])

        # R value = risk per share (distance to hard stop)
        r = abs(entry_price - hard_stop)

        # Direction-specific config stamps
        if is_long:
            dir_p = {
                'p_orb_minutes': config.LONG_ORB_MINUTES,
                'p_breakout_offset': config.LONG_BREAKOUT_OFFSET,
                'p_hard_stop_mode': config.LONG_HARD_STOP_MODE,
                'p_hard_stop_pct': config.LONG_HARD_STOP_PCT,
                'p_hard_stop_atr_mult': config.LONG_HARD_STOP_ATR_MULT,
                'p_atr_base_mult': config.LONG_ATR_BASE_MULTIPLIER,
                'p_atr_tier1_mult': config.LONG_ATR_TIER1_MULTIPLIER,
                'p_atr_tier2_mult': config.LONG_ATR_TIER2_MULTIPLIER,
                'p_atr_profit_tier1': config.LONG_ATR_PROFIT_TIER1,
                'p_atr_profit_tier2': config.LONG_ATR_PROFIT_TIER2,
                'p_atr_activation_pct': config.LONG_ATR_ACTIVATION_PCT,
                'p_use_take_profit': config.USE_TAKE_PROFIT,
                'p_r_tp1': config.LONG_R_TP1,
                'p_r_tp2': config.LONG_R_TP2,
                'p_r_tp3': config.LONG_R_TP3,
            }
        else:
            dir_p = {
                'p_orb_minutes': config.SHORT_ORB_MINUTES,
                'p_breakout_offset': config.SHORT_BREAKOUT_OFFSET,
                'p_hard_stop_mode': config.SHORT_HARD_STOP_MODE,
                'p_hard_stop_pct': config.SHORT_HARD_STOP_PCT,
                'p_hard_stop_atr_mult': config.SHORT_HARD_STOP_ATR_MULT,
                'p_atr_base_mult': config.SHORT_ATR_BASE_MULTIPLIER,
                'p_atr_tier1_mult': config.SHORT_ATR_TIER1_MULTIPLIER,
                'p_atr_tier2_mult': config.SHORT_ATR_TIER2_MULTIPLIER,
                'p_atr_profit_tier1': config.SHORT_ATR_PROFIT_TIER1,
                'p_atr_profit_tier2': config.SHORT_ATR_PROFIT_TIER2,
                'p_atr_activation_pct': config.SHORT_ATR_ACTIVATION_PCT,
                'p_use_take_profit': config.USE_TAKE_PROFIT,
                'p_r_tp1': config.SHORT_R_TP1,
                'p_r_tp2': config.SHORT_R_TP2,
                'p_r_tp3': config.SHORT_R_TP3,
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
            # Group 6: Universe Selection Context
            'u_source': (universe_meta or {}).get('source', 'FALLBACK'),
            'u_tier': (universe_meta or {}).get('tier', ''),
            'u_max_dd': (universe_meta or {}).get('max_dd', ''),
            'u_scanner_gap_pct': round((universe_meta or {}).get('scanner_gap_pct', 0) * 100, 2) if universe_meta else '',
            'u_scanner_atr': (universe_meta or {}).get('scanner_atr', ''),
            'u_scanner_adv': (universe_meta or {}).get('scanner_adv', ''),
            # Group 6c: Universe Sheet Fields
            'u_gap_pct_sheet': (universe_meta or {}).get('gap_pct_sheet', ''),
            'u_catalyst': (universe_meta or {}).get('catalyst', ''),
            'u_cat_quality': (universe_meta or {}).get('cat_quality', ''),
            'u_var_tier': (universe_meta or {}).get('var_tier', ''),
            'u_final_tier': (universe_meta or {}).get('final_tier', ''),
            'u_max_dd_sheet': (universe_meta or {}).get('max_dd_sheet', ''),
            'u_net_perf': (universe_meta or {}).get('net_perf', ''),
            'u_expectancy': (universe_meta or {}).get('expectancy', ''),
            'u_notes': (universe_meta or {}).get('notes', ''),
            'u_ti_timestamp': (universe_meta or {}).get('ti_timestamp', ''),
            'u_ti_price': (universe_meta or {}).get('ti_price', ''),
            'u_ti_chg_dollar': (universe_meta or {}).get('ti_chg_dollar', ''),
            'u_ti_chg_pct': (universe_meta or {}).get('ti_chg_pct', ''),
            'u_ti_volume': (universe_meta or {}).get('ti_volume', ''),
            'u_ti_rel_vol': (universe_meta or {}).get('ti_rel_vol', ''),
            'u_ti_gap_pct': (universe_meta or {}).get('ti_gap_pct', ''),
            'u_ti_float': (universe_meta or {}).get('ti_float', ''),
            'u_ti_atr': (universe_meta or {}).get('ti_atr', ''),
            'u_ti_avg_vol_5d': (universe_meta or {}).get('ti_avg_vol_5d', ''),
            'u_ti_dist_vwap': (universe_meta or {}).get('ti_dist_vwap', ''),
            # Group 6b: Universe Filter Thresholds
            'u_min_price': config.AUTO_MIN_PRICE if config.USE_AUTO_UNIVERSE else '',
            'u_min_adv': config.AUTO_MIN_ADV if config.USE_AUTO_UNIVERSE else '',
            'u_min_today_volume': config.AUTO_MIN_TODAY_VOLUME if config.USE_AUTO_UNIVERSE else '',
            'u_min_atr': config.AUTO_MIN_ATR if config.USE_AUTO_UNIVERSE else '',
            'u_gap_pct_min': config.AUTO_GAP_PCT if config.USE_AUTO_UNIVERSE else '',
            'u_gap_pct_max': config.AUTO_MAX_GAP_PCT if config.USE_AUTO_UNIVERSE else '',
            'u_max_short_float': config.AUTO_MAX_SHORT_FLOAT if config.USE_AUTO_UNIVERSE else '',
            'u_min_float_shares': config.AUTO_MIN_FLOAT_SHARES if config.USE_AUTO_UNIVERSE else '',
            'u_require_eps': config.AUTO_REQUIRE_EPS if config.USE_AUTO_UNIVERSE else '',
            'u_min_market_cap': config.AUTO_MIN_MARKET_CAP if config.USE_AUTO_UNIVERSE else '',
            'u_no_earnings_today': config.AUTO_NO_EARNINGS_TODAY if config.USE_AUTO_UNIVERSE else '',
            'u_max_symbols': config.AUTO_MAX_SYMBOLS if config.USE_AUTO_UNIVERSE else '',
            'u_max_price': config.AUTO_MAX_PRICE if config.USE_AUTO_UNIVERSE else '',
            # Group 7: Real-Time Entry Bar Data
            'prior_close': round(snapshot.get('prior_close', 0), 2),
            'today_open': round(snapshot.get('today_open', 0), 2),
            'entry_bar_volume': snapshot.get('bar_volume', 0),
            'entry_bar_range': round(snapshot.get('bar_range', 0), 4),
            'entry_spread': round(snapshot.get('spread', 0), 4),
            'entry_spread_pct': round(snapshot.get('spread_pct', 0), 4),
            'p_max_spread_pct': config.MAX_SPREAD_PCT,
            # Group 8: Counterfactual Entry Filter Evaluation
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
            # Group 10: Take Profit Tracking
            'tp1_price': round(tp_prices[0], 2) if tp_prices[0] is not None else '',
            'tp1_hit': False, 'tp1_shares': tp_shares[0] if tp_shares[0] else '',
            'tp1_fill_price': '',
            'tp2_price': round(tp_prices[1], 2) if tp_prices[1] is not None else '',
            'tp2_hit': False, 'tp2_shares': tp_shares[1] if tp_shares[1] else '',
            'tp2_fill_price': '',
            'tp3_price': round(tp_prices[2], 2) if tp_prices[2] is not None else '',
            'tp3_hit': False, 'tp3_shares': tp_shares[2] if tp_shares[2] else '',
            'tp3_fill_price': '',
            # Group 11: SpotGamma Options Data at Entry
            **self._stamp_sg_fields(sg_snapshot, fe, config),
            # Internal tracking (excluded from CSV output)
            '_is_long': is_long,
            '_high_extreme': entry_price,
            '_low_extreme': entry_price,
        }
        self.open_records[symbol] = rec

    @staticmethod
    def _stamp_sg_fields(sg_snapshot, filter_evals, config):
        """Build sg_ fields dict from SpotGamma snapshot for trade record."""
        sg = sg_snapshot or {}
        fe = filter_evals or {}
        return {
            'sg_gamma_regime': sg.get('gamma_regime', ''),
            'sg_call_wall': sg.get('call_wall', ''),
            'sg_put_wall': sg.get('put_wall', ''),
            'sg_hedge_wall': sg.get('hedge_wall', ''),
            'sg_key_gamma_strike': sg.get('key_gamma_strike', ''),
            'sg_key_delta_strike': sg.get('key_delta_strike', ''),
            'sg_cw_dist_pct': sg.get('cw_dist_pct', ''),
            'sg_pw_dist_pct': sg.get('pw_dist_pct', ''),
            'sg_hw_dist_pct': sg.get('hw_dist_pct', ''),
            'sg_options_impact': sg.get('options_impact', ''),
            'sg_impact_tier': sg.get('impact_tier', ''),
            'sg_impl_move_dollar': sg.get('impl_move_dollar', ''),
            'sg_impl_move_pct': sg.get('impl_move_pct', ''),
            'sg_est_move_high': sg.get('est_move_high', ''),
            'sg_est_move_low': sg.get('est_move_low', ''),
            'sg_iv_rank': sg.get('iv_rank', ''),
            'sg_iv_rank_tier': sg.get('iv_rank_tier', ''),
            'sg_inst_conviction': sg.get('inst_conviction', ''),
            'sg_dpi_trend': sg.get('dpi_trend', ''),
            'sg_skew_signal': sg.get('skew_signal', ''),
            'sg_net_gamma': sg.get('net_gamma', ''),
            'sg_gamma_tilt': sg.get('gamma_tilt', ''),
            'sg_opex_proximity': sg.get('opex_proximity', ''),
            # Group 11b: SpotGamma Filter Counterfactuals
            'cf_sg_gamma_regime_pass': fe.get('cf_sg_gamma_regime_pass', ''),
            'cf_sg_conviction_pass': fe.get('cf_sg_conviction_pass', ''),
            'cf_sg_range_validation_pass': fe.get('cf_sg_range_validation_pass', ''),
            'cf_sg_opex_pass': fe.get('cf_sg_opex_pass', ''),
            # Group 11c: SpotGamma Config Flags
            'f_sg_enabled': config.SG_ENABLED,
            'f_sg_gamma_regime': config.SG_USE_GAMMA_REGIME,
            'f_sg_conviction': config.SG_USE_CONVICTION_FILTER,
            'f_sg_range_validation': config.SG_USE_RANGE_VALIDATION,
            'f_sg_wall_targets': config.SG_USE_WALL_TARGETS,
            'f_sg_opex_filter': config.SG_USE_OPEX_FILTER,
        }

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

        # TP counterfactual: always track if TP prices were hit (even if TP disabled)
        if symbol in self.entries:
            entry = self.entries[symbol]
            for i in range(3):
                tp_price = entry.get("tp_prices", [None, None, None])[i]
                if tp_price is not None:
                    if is_long:
                        rec[f'tp{i+1}_hit'] = high_ext >= tp_price
                    else:
                        rec[f'tp{i+1}_hit'] = low_ext <= tp_price
                    if entry.get("tp_fill_prices", [None, None, None])[i] is not None:
                        rec[f'tp{i+1}_fill_price'] = round(entry["tp_fill_prices"][i], 2)

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
