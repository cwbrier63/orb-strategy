from AlgorithmImports import *
import csv
import io


# Column mapping: SpotGamma CSV header → internal snake_case key
# Numeric fields parsed as float, string fields stored as-is (lowercased)
_NUMERIC_COLS = {
    "Price": "price",
    "Call Wall": "call_wall",
    "Put Wall": "put_wall",
    "Hedge Wall": "hedge_wall",
    "Key Gamma Strike": "key_gamma_strike",
    "Key Delta Strike": "key_delta_strike",
    "CW Dist %": "cw_dist_pct",
    "PW Dist %": "pw_dist_pct",
    "HW Dist %": "hw_dist_pct",
    "Options Impact": "options_impact",
    "Impl Move $": "impl_move_dollar",
    "Impl Move %": "impl_move_pct",
    "Est Move High": "est_move_high",
    "Est Move Low": "est_move_low",
    "5D Move %": "five_day_move_pct",
    "Monthly Move %": "monthly_move_pct",
    "IV Rank": "iv_rank",
    "IV Premium": "iv_premium",
    "Net Gamma": "net_gamma",
    "Gamma Tilt": "gamma_tilt",
}

_STRING_COLS = {
    "Symbol": "symbol",
    "Date": "date",
    "Gamma Regime": "gamma_regime",
    "Impact Tier": "impact_tier",
    "IV Rank Tier": "iv_rank_tier",
    "Inst Conviction": "inst_conviction",
    "DPI Trend": "dpi_trend",
    "Skew Signal": "skew_signal",
    "OPEX Proximity": "opex_proximity",
}

def _parse_row(row):
    """Parse a single CSV row dict into internal format."""
    rec = {}
    for csv_col, key in _NUMERIC_COLS.items():
        raw = row.get(csv_col, "")
        if raw is None or str(raw).strip() == "":
            rec[key] = None
        else:
            try:
                rec[key] = float(raw)
            except (ValueError, TypeError):
                rec[key] = None
    for csv_col, key in _STRING_COLS.items():
        raw = row.get(csv_col, "")
        rec[key] = str(raw).strip().lower() if raw else ""
    return rec


class SpotGammaManager:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        # Current day data: {symbol_str_upper: parsed_dict}
        self.sg_data = {}
        # Historical data for backtesting: {(symbol_str_upper, "YYYY-MM-DD"): parsed_dict}
        self.sg_history = {}
        self.loaded_date = None

    def load_history(self):
        """Load historical SpotGamma data from the History tab (one-time at init for backtesting)."""
        gid = self.config.SG_HISTORY_GID
        if not gid:
            self.algo._log("[SG] No history GID configured — skipping history load")
            return
        url = f"{self.config.SG_SHEET_BASE_URL}?gid={gid}&single=true&output=csv"
        try:
            raw = self.algo.download(url)
            if not raw or len(raw.strip()) == 0:
                self.algo._log("[SG] History tab returned empty data")
                return
            reader = csv.DictReader(io.StringIO(raw))
            count = 0
            for row in reader:
                rec = _parse_row(row)
                sym = rec.get("symbol", "").upper()
                date_str = rec.get("date", "").strip()
                if sym and date_str:
                    self.sg_history[(sym, date_str)] = rec
                    count += 1
            self.algo._log(f"[SG] Loaded {count} historical rows for {len(set(k[1] for k in self.sg_history))} dates")
        except Exception as e:
            self.algo._log(f"[SG HISTORY ERROR] {str(e)}")

    def load_current_day(self):
        """Fetch today's SpotGamma data from the current-day tab."""
        if not self.algo._is_trading_day():
            return
        today_str = self.algo.time.strftime("%Y-%m-%d")
        if self.loaded_date == today_str:
            return  # Already loaded today
        url = f"{self.config.SG_SHEET_BASE_URL}?gid={self.config.SG_CURRENT_GID}&single=true&output=csv"
        try:
            raw = self.algo.download(url)
            if not raw or len(raw.strip()) == 0:
                self.algo._log("[SG] Current-day tab returned empty data")
                return
            reader = csv.DictReader(io.StringIO(raw))
            self.sg_data.clear()
            count = 0
            for row in reader:
                rec = _parse_row(row)
                sym = rec.get("symbol", "").upper()
                if sym:
                    self.sg_data[sym] = rec
                    count += 1
            self.loaded_date = today_str
            self.algo.debug(f"[SG] Loaded {count} symbols for {today_str}")
        except Exception as e:
            self.algo._log(f"[SG LOAD ERROR] {str(e)}")

    def get(self, symbol):
        """Get SpotGamma data for a symbol. Checks current-day first, then history.
        For history, looks back up to 10 calendar days if no exact date match."""
        sym = str(symbol).upper()
        # Remove any QC suffix (e.g. "AAPL 2T" → "AAPL")
        if " " in sym:
            sym = sym.split(" ")[0]
        if sym in self.sg_data:
            return self.sg_data[sym]
        # Fallback to history for backtesting — look back up to 10 days
        from datetime import timedelta
        today = self.algo.time.date()
        for offset in range(11):  # 0 = today, 1 = yesterday, ... 10
            check_date = today - timedelta(days=offset)
            date_str = check_date.strftime("%Y-%m-%d")
            rec = self.sg_history.get((sym, date_str))
            if rec is not None:
                return rec
        return None

    def get_gamma_regime(self, symbol):
        rec = self.get(symbol)
        return rec.get("gamma_regime") if rec else None

    def get_conviction(self, symbol):
        rec = self.get(symbol)
        return rec.get("inst_conviction") if rec else None

    def get_impl_move(self, symbol):
        rec = self.get(symbol)
        if rec:
            return rec.get("impl_move_dollar"), rec.get("impl_move_pct")
        return None, None

    def get_est_move(self, symbol):
        rec = self.get(symbol)
        if rec:
            return rec.get("est_move_high"), rec.get("est_move_low")
        return None, None

    def get_call_wall(self, symbol):
        rec = self.get(symbol)
        return rec.get("call_wall") if rec else None

    def get_put_wall(self, symbol):
        rec = self.get(symbol)
        return rec.get("put_wall") if rec else None

    def get_opex_proximity(self, symbol):
        rec = self.get(symbol)
        return rec.get("opex_proximity") if rec else None

    def reset_daily(self):
        self.sg_data.clear()
        self.loaded_date = None
