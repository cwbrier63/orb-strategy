"""
universe_loader.py — QC module: reads orb_universe from Supabase.

Two-phase approach:
  1. subscribe_all() at init — pre-subscribe ALL unique symbols with indicator warmup
  2. load() at 9:15 daily — tag direction/tier/meta for today's symbols only
"""

from AlgorithmImports import *
import http.client
import ssl
import json

_SELECT = ",".join([
    "symbol", "orb_tier", "composite_score", "atr_14", "adv_20d",
    "float_m", "short_float_pct", "squeeze_score", "pcr_signal",
    "catalyst_direction", "catalyst_confidence", "catalyst_type",
    "has_catalyst", "premarket_gap_pct", "price",
])

_TIER_DD = {1: -0.08, 2: -0.06, 3: -0.04}


class SupabaseUniverseLoader:

    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self._host = config.SG_SUPABASE_URL.replace("https://", "")
        self._key = config.SG_SUPABASE_KEY
        self._subscribed = {}  # ticker -> Symbol object

    def subscribe_all(self):
        """Called at init. Fetch ALL unique symbols across all scan_dates,
        subscribe at Minute resolution, and register indicators for warmup."""
        try:
            # Get distinct symbols from orb_universe
            path = "/rest/v1/orb_universe?select=symbol&limit=10000"
            rows = self._http_get(path)
            if not rows:
                self.algo._log("[SCANNER] No symbols in orb_universe — skipping subscribe")
                return

            unique = set(r.get("symbol", "").upper() for r in rows if r.get("symbol"))
            self.algo._log(f"[SCANNER] Pre-subscribing {len(unique)} unique symbols")

            count = 0
            for ticker in unique:
                try:
                    sym = self.algo.add_equity(ticker, Resolution.MINUTE).symbol
                    self._subscribed[ticker] = sym
                    self.algo.indicators.register(sym)
                    count += 1
                except:
                    pass  # some tickers may not exist in QC

            self.algo._log(f"[SCANNER] Subscribed {count}/{len(unique)} symbols with indicator warmup")
        except Exception as e:
            self.algo._log(f"[SCANNER SUBSCRIBE ERROR] {e}")

    def load(self, date_str: str = None):
        """Called at 9:15 daily. Tag today's symbols with direction/tier/meta.
        Does NOT subscribe — symbols already subscribed at init."""
        if date_str is None:
            date_str = self.algo.time.strftime("%Y-%m-%d")

        try:
            path = (f"/rest/v1/orb_universe?select={_SELECT}"
                    f"&scan_date=eq.{date_str}&include_flag=eq.true"
                    f"&order=composite_score.desc&limit=400")
            rows = self._http_get(path)
            if not rows:
                self.algo._log(f"[SCANNER] No universe for {date_str}")
                return

            new_symbols = set()
            count = 0
            for row in rows:
                ticker = row.get("symbol", "").strip().upper()
                if not ticker:
                    continue

                # Get pre-subscribed Symbol object
                symbol = self._subscribed.get(ticker)
                if symbol is None:
                    try:
                        symbol = self.algo.add_equity(ticker, Resolution.MINUTE).symbol
                        self._subscribed[ticker] = symbol
                        self.algo.indicators.register(symbol)
                    except:
                        continue

                tier = int(row.get("orb_tier", 3) or 3)
                max_dd = _TIER_DD.get(tier, -0.06)
                gap_pct = float(row.get("premarket_gap_pct", 0) or 0)

                # Direction: catalyst > gap sign
                cat_dir = (row.get("catalyst_direction") or "").lower()
                confidence = float(row.get("catalyst_confidence", 0) or 0)
                if cat_dir in ("long", "short") and confidence >= 0.7:
                    direction = cat_dir.upper()
                elif gap_pct > 0:
                    direction = "SHORT"
                elif gap_pct < 0:
                    direction = "LONG"
                else:
                    direction = "SHORT"

                new_symbols.add(symbol)
                if symbol not in self.algo.symbols:
                    self.algo.symbols.append(symbol)

                self.algo.max_dd[symbol] = max_dd
                self.algo.symbol_meta[symbol] = {
                    "direction": direction, "tier": tier, "max_dd": max_dd,
                    "source": "SUPABASE_SCANNER",
                    "composite_score": int(row.get("composite_score", 0) or 0),
                }

                hist = self.algo.history(symbol, 2, Resolution.DAILY)
                if not hist.empty and len(hist) >= 1:
                    self.algo.prior_close[symbol] = hist["close"].iloc[-1]

                self.algo.gap_qualified[symbol] = True
                self.algo.symbol_direction[symbol] = direction
                if hasattr(self.algo, 'signal_engine') and gap_pct != 0:
                    self.algo.signal_engine.set_gap_pct(symbol, gap_pct)
                count += 1

            # Remove stale symbols
            stale = [s for s in self.algo.symbols if s not in new_symbols]
            for s in stale:
                self.algo.symbols.remove(s)
                self.algo.max_dd.pop(s, None)
                self.algo.symbol_meta.pop(s, None)

            self.algo._sheet_loaded_today = True
            self.algo._log(f"[SCANNER] Loaded {count} symbols for {date_str}")

        except Exception as e:
            self.algo._log(f"[SCANNER ERROR] {e}")

    def _http_get(self, path: str) -> list:
        hdrs = {"apikey": self._key, "Authorization": f"Bearer {self._key}", "Accept": "application/json"}
        try:
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(self._host, timeout=60, context=ctx)
            conn.request("GET", path, headers=hdrs)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            conn.close()
            if not raw or raw.strip() in ("", "[]"):
                return []
            return json.loads(raw)
        except Exception as e:
            self.algo._log(f"[SCANNER HTTP] {e}")
            return []
