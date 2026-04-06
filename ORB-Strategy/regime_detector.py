from AlgorithmImports import *
import http.client
import ssl


class RegimeDetector:
    """Computes daily market regime from SPY overnight price action.
    Called once at 9:12 AM via scheduled event in main.py.
    Sets directional sizing multipliers for long/short entries."""

    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self._spy_symbol = None
        self.regime_label = "NEUTRAL"
        self.long_mult = 1.0
        self.short_mult = 1.0
        self.overnight_return = 0.0
        self.es_fading = False

    def initialize(self):
        if not self.config.REGIME_AUTO_DETECT:
            return
        try:
            equity = self.algo.add_equity("SPY", Resolution.MINUTE)
            self._spy_symbol = equity.symbol
            self.algo._log("[REGIME] SPY subscribed for overnight regime detection")
        except Exception as e:
            self.algo._log(f"[REGIME] SPY subscription failed: {e}")
            self.config.REGIME_AUTO_DETECT = False

    def compute(self):
        if self._spy_symbol is None:
            self._set_neutral()
            return
        try:
            hist = self.algo.history(self._spy_symbol, 500, Resolution.MINUTE)
            if hist is None or hist.empty or len(hist) < 60:
                self.algo._log("[REGIME] Insufficient history — neutral")
                self._set_neutral()
                return

            closes = hist["close"]

            prev_close = self._find_prev_regular_close(hist)
            if prev_close is None or prev_close <= 0:
                self._set_neutral()
                return

            current_price = float(closes.iloc[-1])
            self.overnight_return = (current_price - prev_close) / prev_close

            # Fading detection: last 45 bars
            recent = hist.tail(45)
            session_high = float(recent["high"].max())
            session_low = float(recent["low"].min())
            if self.overnight_return >= 0:
                self.es_fading = current_price < session_high * 0.997
            else:
                self.es_fading = current_price > session_low * 1.003

            prev_high, prev_low = self._get_prev_session_range(hist)
            above_prev_high = prev_high is not None and current_price > prev_high
            below_prev_low = prev_low is not None and current_price < prev_low

            self._classify(above_prev_high, below_prev_low)

        except Exception as e:
            self.algo._log(f"[REGIME ERROR] {e} — neutral fallback")
            self._set_neutral()

    def _classify(self, above_prev_high, below_prev_low):
        r = self.overnight_return
        fade = self.es_fading

        if r >= 0.002 and not fade and above_prev_high:
            self.regime_label, self.long_mult, self.short_mult = "STRONG_UPTREND", 1.60, 0.40
        elif r >= 0.001 and not fade:
            self.regime_label, self.long_mult, self.short_mult = "UPTREND", 1.30, 0.70
        elif r >= 0.0005 and fade:
            self.regime_label, self.long_mult, self.short_mult = "UPTREND_FADING", 1.00, 1.00
        elif abs(r) < 0.0005:
            self.regime_label, self.long_mult, self.short_mult = "NEUTRAL", 1.00, 1.00
        elif r <= -0.004:
            self.regime_label, self.long_mult, self.short_mult = "EXTREME_SELLOFF", 1.00, 1.00
        elif r <= -0.002 and not fade and below_prev_low:
            self.regime_label, self.long_mult, self.short_mult = "STRONG_DOWNTREND", 1.00, 1.00
        elif r <= -0.001 and not fade:
            self.regime_label, self.long_mult, self.short_mult = "DOWNTREND", 1.00, 1.00
        elif r <= -0.0005 and fade:
            self.regime_label, self.long_mult, self.short_mult = "DOWNTREND_FADING", 1.00, 1.00
        else:
            self.regime_label, self.long_mult, self.short_mult = "NEUTRAL", 1.00, 1.00

        floor = self.config.REGIME_MIN_DIRECTION_MULT
        self.long_mult = max(self.long_mult, floor)
        self.short_mult = max(self.short_mult, floor)

    def _find_prev_regular_close(self, hist):
        """Find most recent 3:59 PM bar close (regular session close)."""
        for ts, row in hist.iloc[::-1].iterrows():
            try:
                # QC MultiIndex: ts = (symbol, datetime)
                dt = ts[1] if isinstance(ts, tuple) else ts
                if dt.hour == 15 and dt.minute == 59:
                    return float(row["close"])
            except Exception:
                continue
        return None

    def _get_prev_session_range(self, hist):
        """Get prior regular session high/low (9:30-3:59 PM)."""
        try:
            today = self.algo.time.date()
            idx = hist.index.get_level_values(1) if hist.index.nlevels > 1 else hist.index
            mask = (idx.date < today) & (idx.time >= time(9, 30)) & (idx.time <= time(15, 59))
            session = hist[mask]
            if session.empty:
                return None, None
            last_date = max(session.index.get_level_values(1).date if session.index.nlevels > 1 else session.index.date)
            idx2 = session.index.get_level_values(1) if session.index.nlevels > 1 else session.index
            day_bars = session[idx2.date == last_date]
            if day_bars.empty:
                return None, None
            return float(day_bars["high"].max()), float(day_bars["low"].min())
        except Exception:
            return None, None

    def _set_neutral(self):
        self.regime_label = "NEUTRAL"
        self.long_mult = 1.0
        self.short_mult = 1.0
        self.overnight_return = 0.0
        self.es_fading = False

    def load_regime_from_supabase(self):
        """Load regime classifier fields from Supabase market_regime table.
        Populates REGIME_COMPOSITE_SCORE, REGIME_BREADTH_PCT, etc.
        Non-fatal — empty fields if table/row doesn't exist."""
        try:
            today = self.algo.time.strftime("%Y-%m-%d")
            host = self.config.SG_SUPABASE_URL.replace("https://", "")
            key = self.config.SG_SUPABASE_KEY
            path = (f"/rest/v1/market_regime?scan_date=eq.{today}"
                    f"&select=regime_label,regime_multiplier,composite_score,"
                    f"mode,breadth_pct,sector_advancers,futures_available,"
                    f"es_overnight_ret,leading_sector,lagging_sector"
                    f"&limit=1")
            hdrs = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, timeout=30, context=ctx)
            conn.request("GET", path, headers=hdrs)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            conn.close()
            if not raw or raw.strip() in ("", "[]"):
                return
            import json
            rows = json.loads(raw)
            if not rows:
                return
            row = rows[0]
            # Populate config fields
            mult = float(row.get("regime_multiplier") or self.config.REGIME_CURRENT)
            self.config.REGIME_CURRENT = mult
            self.regime_label = str(row.get("regime_label") or "NEUTRAL")
            self.config.REGIME_LABEL = self.regime_label
            self.config.REGIME_COMPOSITE_SCORE = float(row.get("composite_score") or 0)
            self.config.REGIME_MODE = str(row.get("mode") or "")
            self.config.REGIME_BREADTH_PCT = float(row.get("breadth_pct") or 0)
            self.config.REGIME_SECTOR_ADVANCERS = int(row.get("sector_advancers") or 0)
            self.config.REGIME_FUTURES_AVAILABLE = bool(row.get("futures_available", False))
            self.config.REGIME_ES_RET = float(row.get("es_overnight_ret") or 0)
            self.config.REGIME_LEADING_SECTOR = str(row.get("leading_sector") or "")
            self.config.REGIME_LAGGING_SECTOR = str(row.get("lagging_sector") or "")
            self.algo._log(f"[REGIME] Supabase: {self.regime_label} mult={mult} score={self.config.REGIME_COMPOSITE_SCORE:.1f}")
        except Exception as e:
            self.algo._log(f"[REGIME] Supabase load failed: {e} — using defaults")
