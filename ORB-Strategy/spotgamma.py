from AlgorithmImports import *
import json
import http.client
import ssl


# Supabase column mapping: supabase snake_case → internal key
_SB_NUMERIC_COLS = {
    "current_price": "price",
    "call_wall": "call_wall",
    "put_wall": "put_wall",
    "hedge_wall": "hedge_wall",
    "key_gamma_strike": "key_gamma_strike",
    "key_delta_strike": "key_delta_strike",
    "call_wall_pct": "cw_dist_pct",
    "put_wall_pct": "pw_dist_pct",
    "hedge_wall_pct": "hw_dist_pct",
    "options_impact": "options_impact",
    "options_implied_move": "impl_move_dollar",
    "implied_move_pct": "impl_move_pct",
    "est_move_high": "est_move_high",
    "est_move_low": "est_move_low",
    "implied_move_5d_pct": "five_day_move_pct",
    "est_move_monthly_pct": "monthly_move_pct",
    "iv_rank": "iv_rank",
    "iv_premium": "iv_premium",
    "net_gamma": "net_gamma",
    "gamma_tilt": "gamma_tilt",
}

_SB_STRING_COLS = {
    "symbol": "symbol",
    "import_date": "date",
    "gamma_regime": "gamma_regime",
    "options_impact_tier": "impact_tier",
    "iv_rank_tier": "iv_rank_tier",
    "institutional_conviction": "inst_conviction",
    "dpi_trend": "dpi_trend",
    "skew_signal": "skew_signal",
    "opex_proximity": "opex_proximity",
}

_SELECT_COLS = ",".join(list(_SB_NUMERIC_COLS.keys()) + list(_SB_STRING_COLS.keys()))


def _parse_supabase_row(row):
    """Parse a single Supabase JSON row dict into internal format."""
    rec = {}
    for sb_col, key in _SB_NUMERIC_COLS.items():
        raw = row.get(sb_col)
        if raw is None:
            rec[key] = None
        else:
            try:
                rec[key] = float(raw)
            except (ValueError, TypeError):
                rec[key] = None
    for sb_col, key in _SB_STRING_COLS.items():
        raw = row.get(sb_col)
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

    def _supabase_fetch(self, extra_params=""):
        """Fetch rows from Supabase REST API using http.client (QC download blocks non-whitelisted domains)."""
        host = self.config.SG_SUPABASE_URL.replace("https://", "")
        key = self.config.SG_SUPABASE_KEY
        table = self.config.SG_SUPABASE_TABLE
        hdrs = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
        page_size = 1000
        offset = 0
        all_rows = []
        while True:
            path = (f"/rest/v1/{table}?select={_SELECT_COLS}"
                    f"&order=import_date.asc,symbol.asc"
                    f"&offset={offset}&limit={page_size}{extra_params}")
            try:
                ctx = ssl.create_default_context()
                conn = http.client.HTTPSConnection(host, timeout=30, context=ctx)
                conn.request("GET", path, headers=hdrs)
                resp = conn.getresponse()
                raw = resp.read().decode("utf-8")
                conn.close()
            except Exception as e:
                self.algo._log(f"[SG HTTP ERROR] {e}")
                break
            if not raw or raw.strip() in ("", "[]"):
                break
            rows = json.loads(raw)
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < page_size:
                break
            offset += page_size
        return all_rows

    def load_history(self):
        """Load historical SpotGamma data from Supabase (one-time at init)."""
        try:
            rows = self._supabase_fetch()
            count = 0
            for row in rows:
                rec = _parse_supabase_row(row)
                sym = rec.get("symbol", "").upper()
                date_str = rec.get("date", "").strip()
                if sym and date_str:
                    self.sg_history[(sym, date_str)] = rec
                    count += 1
            dates = len(set(k[1] for k in self.sg_history)) if self.sg_history else 0
            self.algo._log(f"[SG] Supabase: loaded {count} rows for {dates} dates")
        except Exception as e:
            self.algo._log(f"[SG ERROR] History load failed: {str(e)}")

    def load_current_day(self):
        """Fetch today's SpotGamma data from Supabase."""
        if not self.algo._is_trading_day():
            return
        today_str = self.algo.time.strftime("%Y-%m-%d")
        if self.loaded_date == today_str:
            return
        try:
            rows = self._supabase_fetch(f"&import_date=eq.{today_str}")
            self.sg_data.clear()
            count = 0
            for row in rows:
                rec = _parse_supabase_row(row)
                sym = rec.get("symbol", "").upper()
                if sym:
                    self.sg_data[sym] = rec
                    count += 1
            self.loaded_date = today_str
            self.algo.debug(f"[SG] Loaded {count} symbols for {today_str}")
        except Exception as e:
            self.algo._log(f"[SG ERROR] Current day load failed: {str(e)}")

    def get(self, symbol):
        """Get SpotGamma data for a symbol. Checks current-day first, then history.
        For history, looks back up to 10 calendar days if no exact date match."""
        sym = str(symbol).upper()
        if " " in sym:
            sym = sym.split(" ")[0]
        if sym in self.sg_data:
            return self.sg_data[sym]
        from datetime import timedelta
        today = self.algo.time.date()
        for offset in range(11):
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
