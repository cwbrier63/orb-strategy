from AlgorithmImports import *
import math


class UniverseScorer:
    """Multi-factor composite scoring + mini-backtester for auto gap scanner."""

    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config

    # ── Phase 1: Composite Scoring ────────────────────────────────

    def score_candidates(self, candidates, sg_mgr=None):
        """Score and rank gap scanner candidates.

        Args:
            candidates: list of (symbol, gap_pct, atr14, adv, price, direction, trend_signals)
            sg_mgr: SpotGammaManager instance (optional)

        Returns:
            Sorted list of dicts with score, tier, max_dd, trend_signals added.
            Only candidates above AUTO_MIN_COMPOSITE_SCORE are returned.
        """
        scored = []
        for sym, gap_pct, atr14, adv, price, direction, trend_signals in candidates:
            gap_score = self._score_gap(abs(gap_pct))
            atr_score = self._score_atr(atr14, price)
            vol_score = self._score_volume(adv)
            sg_score = self._score_sg_conviction(sg_mgr, sym, direction)
            liq_score = self._score_liquidity(adv)

            cfg = self.config
            total = (
                gap_score * cfg.AUTO_SCORE_GAP_WEIGHT
                + atr_score * cfg.AUTO_SCORE_ATR_WEIGHT
                + vol_score * cfg.AUTO_SCORE_VOLUME_WEIGHT
                + sg_score * cfg.AUTO_SCORE_SG_WEIGHT
                + liq_score * cfg.AUTO_SCORE_LIQUIDITY_WEIGHT
            )

            scored.append({
                "symbol": sym,
                "gap_pct": gap_pct,
                "atr": atr14,
                "adv": adv,
                "price": price,
                "direction": direction,
                "score": round(total, 1),
                "trend_signals": trend_signals,
                "detail": f"gap={gap_score:.0f} atr={atr_score:.0f} vol={vol_score:.0f} sg={sg_score:.0f} liq={liq_score:.0f}",
            })

        min_score = self.config.AUTO_MIN_COMPOSITE_SCORE
        scored = [s for s in scored if s["score"] >= min_score]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:self.config.AUTO_MAX_SYMBOLS]

    def _score_gap(self, abs_gap_pct):
        """Bell curve: 3-6% gap scores highest (100). Tiny/extreme gaps penalized.
        Input is fractional (0.03 = 3%)."""
        pct = abs_gap_pct * 100  # convert to percentage points
        if pct < 2.0:
            return max(0, (pct / 2.0) * 50)  # 0-50 for 0-2%
        elif pct <= 3.0:
            return 50 + (pct - 2.0) * 50  # 50-100 for 2-3%
        elif pct <= 6.0:
            return 100  # sweet spot
        elif pct <= 10.0:
            return max(0, 100 - (pct - 6.0) * 25)  # 100→0 for 6-10%
        else:
            return 0

    def _score_atr(self, atr, price):
        """ATR as % of price. Sweet spot 2-5%."""
        if price <= 0:
            return 0
        atr_pct = (atr / price) * 100
        if atr_pct < 1.0:
            return max(0, atr_pct * 50)  # 0-50 for 0-1%
        elif atr_pct <= 2.0:
            return 50 + (atr_pct - 1.0) * 50  # 50-100 for 1-2%
        elif atr_pct <= 5.0:
            return 100  # sweet spot
        elif atr_pct <= 8.0:
            return max(0, 100 - (atr_pct - 5.0) * 33)  # 100→0 for 5-8%
        else:
            return 0

    def _score_volume(self, adv):
        """Relative volume proxy using ADV magnitude.
        In backtest we don't have pre-market volume, so score ADV directly.
        2M (min) = 50 (neutral), 5M = 75, 10M+ = 100."""
        if adv <= 0:
            return 0
        adv_m = adv / 1_000_000
        if adv_m <= 2.0:
            return 50  # minimum threshold (already filtered)
        elif adv_m <= 10.0:
            return 50 + (adv_m - 2.0) * (50 / 8.0)  # 50-100 linear
        else:
            return 100

    def _score_sg_conviction(self, sg_mgr, symbol, direction):
        """SpotGamma conviction alignment. Aligned = 100, misaligned = 0, no data = 50."""
        if sg_mgr is None:
            return 50  # neutral when no SG data
        conviction = sg_mgr.get_conviction(symbol)
        if conviction is None:
            return 50
        conviction = conviction.lower().strip()
        if direction == "LONG":
            if conviction in ("bullish", "strong_bullish"):
                return 100
            elif conviction == "neutral":
                return 50
            else:
                return 0
        else:  # SHORT
            if conviction in ("bearish", "strong_bearish"):
                return 100
            elif conviction == "neutral":
                return 50
            else:
                return 0

    def _score_liquidity(self, adv):
        """Linear scale: ADV 2M = 0, 10M+ = 100."""
        if adv <= 0:
            return 0
        adv_m = adv / 1_000_000
        if adv_m <= 2.0:
            return 0
        elif adv_m >= 10.0:
            return 100
        else:
            return (adv_m - 2.0) * (100 / 8.0)

    # ── Phase 2: Mini-Backtester ──────────────────────────────────

    def run_mini_backtests(self, scored_candidates):
        """Run historical ORB mini-backtest for each scored candidate.
        Pulls 30 days of 1-minute history and simulates ORB breakouts.

        Args:
            scored_candidates: list of dicts from score_candidates()

        Returns:
            Updated list with tier and max_dd assigned based on backtest results.
        """
        symbols = [c["symbol"] for c in scored_candidates]
        if not symbols:
            return scored_candidates

        cfg = self.config
        bt_days = getattr(cfg, "AUTO_MINI_BT_DAYS", 30)

        try:
            all_hist = self.algo.history(symbols, bt_days, Resolution.MINUTE)
        except Exception as e:
            self.algo.debug(f"[SCORER] Mini-BT history fetch failed: {e}")
            # Fallback: assign default tier=2
            for c in scored_candidates:
                c["tier"] = 2
                c["max_dd"] = -0.06
            return scored_candidates

        if all_hist.empty:
            for c in scored_candidates:
                c["tier"] = 2
                c["max_dd"] = -0.06
            return scored_candidates

        for c in scored_candidates:
            sym = c["symbol"]
            try:
                if sym not in all_hist.index.get_level_values(0).unique():
                    c["tier"] = 2
                    c["max_dd"] = -0.06
                    continue
                sym_hist = all_hist.loc[sym]
                bt = self._mini_backtest(sym_hist, c["direction"], cfg)
                tier, max_dd = self._assign_tier(bt, cfg)
                c["tier"] = tier
                c["max_dd"] = max_dd
                c["bt_stats"] = bt
                self.algo.debug(
                    f"[SCORER BT] {sym.value} WR={bt['win_rate']:.0%} "
                    f"exp={bt['expectancy']:.3f} dd={bt['max_dd_pct']:.1%} → T{tier}"
                )
            except Exception as e:
                self.algo.debug(f"[SCORER BT] {sym.value} failed: {e}")
                c["tier"] = 2
                c["max_dd"] = -0.06

        # Remove rejects (tier=0)
        scored_candidates = [c for c in scored_candidates if c.get("tier", 2) > 0]
        return scored_candidates

    def _mini_backtest(self, minute_hist, direction, cfg):
        """Simulate ORB breakouts over historical minute data for one symbol.

        Args:
            minute_hist: DataFrame with minute bars (index = datetime, cols = ohlcv)
            direction: "LONG" or "SHORT"
            cfg: OrbConfig

        Returns:
            dict with win_rate, avg_win, avg_loss, expectancy, max_dd_pct, trades
        """
        orb_minutes = cfg.LONG_ORB_MINUTES if direction == "LONG" else cfg.SHORT_ORB_MINUTES
        hard_stop_mult = cfg.LONG_HARD_STOP_ATR_MULT if direction == "LONG" else cfg.SHORT_HARD_STOP_ATR_MULT
        trail_mult = cfg.LONG_ATR_BASE_MULTIPLIER if direction == "LONG" else cfg.SHORT_ATR_BASE_MULTIPLIER

        # Group by date
        minute_hist = minute_hist.copy()
        minute_hist["date"] = minute_hist.index.date
        dates = sorted(minute_hist["date"].unique())

        wins = []
        losses = []
        equity_curve = [0.0]

        for day in dates:
            day_bars = minute_hist[minute_hist["date"] == day]
            if len(day_bars) < orb_minutes + 10:
                continue

            # Find ORB range from first N minutes
            orb_bars = day_bars.iloc[:orb_minutes]
            orb_high = orb_bars["high"].max()
            orb_low = orb_bars["low"].min()
            orb_range = orb_high - orb_low
            if orb_range <= 0:
                continue

            # Compute ATR from the day's bars (simplified: use orb_range as proxy)
            # More accurate: use prior day's ATR, but this is a quick simulation
            atr = orb_range  # rough proxy

            # Scan post-ORB bars for breakout
            post_orb = day_bars.iloc[orb_minutes:]
            entry_price = None
            pnl_pct = 0.0

            for idx, bar in post_orb.iterrows():
                # Check for breakout
                if entry_price is None:
                    if direction == "LONG" and bar["close"] > orb_high:
                        entry_price = bar["close"]
                        hard_stop = entry_price - atr * hard_stop_mult
                        trail_stop = entry_price - atr * trail_mult
                    elif direction == "SHORT" and bar["close"] < orb_low:
                        entry_price = bar["close"]
                        hard_stop = entry_price + atr * hard_stop_mult
                        trail_stop = entry_price + atr * trail_mult
                    continue

                # Manage open position
                if direction == "LONG":
                    # Check hard stop
                    if bar["low"] <= hard_stop:
                        pnl_pct = (hard_stop - entry_price) / entry_price
                        break
                    # Update trail
                    new_trail = bar["close"] - atr * trail_mult
                    trail_stop = max(trail_stop, new_trail)
                    if bar["low"] <= trail_stop:
                        pnl_pct = (trail_stop - entry_price) / entry_price
                        break
                else:  # SHORT
                    if bar["high"] >= hard_stop:
                        pnl_pct = (entry_price - hard_stop) / entry_price
                        break
                    new_trail = bar["close"] + atr * trail_mult
                    trail_stop = min(trail_stop, new_trail)
                    if bar["high"] >= trail_stop:
                        pnl_pct = (entry_price - trail_stop) / entry_price
                        break

            # EOD close if still in position
            if entry_price is not None and pnl_pct == 0.0:
                last_price = post_orb.iloc[-1]["close"]
                if direction == "LONG":
                    pnl_pct = (last_price - entry_price) / entry_price
                else:
                    pnl_pct = (entry_price - last_price) / entry_price

            if entry_price is not None:
                if pnl_pct > 0:
                    wins.append(pnl_pct)
                else:
                    losses.append(pnl_pct)
                equity_curve.append(equity_curve[-1] + pnl_pct)

        total = len(wins) + len(losses)
        if total == 0:
            return {"win_rate": 0, "avg_win": 0, "avg_loss": 0,
                    "expectancy": -1, "max_dd_pct": -1, "trades": 0}

        win_rate = len(wins) / total
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        # Expectancy = (WR * avg_win) + ((1-WR) * avg_loss)
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        # Max drawdown from equity curve
        peak = 0
        max_dd = 0
        for val in equity_curve:
            peak = max(peak, val)
            dd = val - peak
            max_dd = min(max_dd, dd)

        return {
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "max_dd_pct": max_dd,
            "trades": total,
        }

    def _assign_tier(self, bt, cfg):
        """Assign tier based on mini-backtest results.

        Returns:
            (tier, max_dd) — tier=0 means REJECT.
        """
        wr = bt["win_rate"]
        exp = bt["expectancy"]
        trades = bt["trades"]

        # Need minimum trades to be meaningful
        if trades < 5:
            return 2, -0.06  # default tier if insufficient data

        t1_wr = getattr(cfg, "AUTO_TIER1_MIN_WIN_RATE", 0.50)
        t1_exp = getattr(cfg, "AUTO_TIER1_MIN_EXPECTANCY", 0.30)
        t2_wr = getattr(cfg, "AUTO_TIER2_MIN_WIN_RATE", 0.40)
        t2_exp = getattr(cfg, "AUTO_TIER2_MIN_EXPECTANCY", 0.10)
        t3_wr = getattr(cfg, "AUTO_TIER3_MIN_WIN_RATE", 0.30)
        t3_exp = getattr(cfg, "AUTO_TIER3_MIN_EXPECTANCY", 0.00)

        if wr >= t1_wr and exp >= t1_exp:
            return 1, max(bt["max_dd_pct"], -0.08)
        elif wr >= t2_wr and exp >= t2_exp:
            return 2, max(bt["max_dd_pct"], -0.06)
        elif wr >= t3_wr and exp >= t3_exp:
            return 3, max(bt["max_dd_pct"], -0.04)
        else:
            return 0, 0  # REJECT

    # ── Phase 3: Gap Sustainability ───────────────────────────────

    def check_gap_sustainability(self, auto_candidates, securities, symbol_meta):
        """Check if gaps have held after ORB window closes.
        Downgrades or removes symbols where gap has faded > 60%.

        Args:
            auto_candidates: dict {symbol: {"direction": .., "gap_pct": .., "pre_market_price": .., "prev_close": ..}}
            securities: algo.securities
            symbol_meta: algo.symbol_meta

        Returns:
            list of symbols removed (for logging).
        """
        removed = []
        min_retention = getattr(self.config, "AUTO_GAP_MIN_RETENTION", 0.40)

        for sym, info in list(auto_candidates.items()):
            pre_price = info.get("pre_market_price", 0)
            prev_close = info.get("prev_close", 0)
            if pre_price <= 0 or prev_close <= 0:
                continue

            current_price = securities[sym].price
            if current_price <= 0:
                continue

            gap_move = pre_price - prev_close
            if abs(gap_move) < 0.01:
                continue

            current_move = current_price - prev_close
            retention = current_move / gap_move if gap_move != 0 else 0

            if retention < 0:
                # Gap fully reversed — remove
                removed.append(sym)
                if sym in symbol_meta:
                    symbol_meta.pop(sym, None)
            elif retention < min_retention:
                # Gap faded >60% — downgrade tier
                if sym in symbol_meta:
                    old_tier = symbol_meta[sym].get("tier", 2)
                    new_tier = min(old_tier + 1, 3)
                    if new_tier > 3:
                        removed.append(sym)
                        symbol_meta.pop(sym, None)
                    else:
                        symbol_meta[sym]["tier"] = new_tier

        return removed
