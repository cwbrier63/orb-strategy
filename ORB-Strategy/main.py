from AlgorithmImports import *
import csv
import io
from config import OrbConfig
from orb_calculator import OrbCalculator
from indicators import IndicatorManager
from signal_engine import SignalEngine
from trade_manager import TradeManager, TRADE_LOG_COLUMNS
from risk_manager import RiskManager
from signalstack_bridge import SignalStackBridge
from spotgamma import SpotGammaManager


class OrbAlgorithm(QCAlgorithm):
    def initialize(self):
        # Log buffer MUST be initialized first — before anything calls self._log()
        self._log_buffer = []

        self.config = OrbConfig()
        self._apply_parameters()

        self.set_start_date(2026, 2, 22)
        self.set_end_date(2026, 3, 10)
        self.set_cash(self.config.ACCOUNT_SIZE)

        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        # Modules
        self.orb = OrbCalculator(self, self.config)
        self.indicators = IndicatorManager(self, self.config)
        self.sg_mgr = SpotGammaManager(self, self.config) if self.config.SG_ENABLED else None
        self.signal_engine = SignalEngine(self, self.config, self.orb, self.indicators, spotgamma_mgr=self.sg_mgr)
        self.trade_mgr = TradeManager(self, self.config, spotgamma_mgr=self.sg_mgr)
        self.risk_mgr = RiskManager(self, self.config)
        self.bridge = SignalStackBridge(self, self.config)

        # Universe — loaded from auto scanner, Google Sheets CSV, or fallback
        self.symbols = []
        self.max_dd = {}
        # symbol_meta: {symbol: {"direction": "LONG"/"SHORT", "tier": 1/2/3, "max_dd": -0.08}}
        self.symbol_meta = {}
        # Auto universe tracking: {symbol: {"direction": .., "gap_pct": .., "atr": ..}}
        self.auto_universe_candidates = {}
        # Watchlist symbols for gap scanner scanning pool
        self.watchlist_symbols = []

        # Universe mode: sheet first, auto scanner fallback, then hardcoded fallback
        # Always load watchlist for auto scanner (needed if sheet has no entries for today)
        if self.config.USE_AUTO_UNIVERSE:
            self._load_watchlist()
        if not self.config.USE_AUTO_UNIVERSE and not self.config.UNIVERSE_SHEET_URL:
            self._load_fallback_universe()
        # Track whether sheet provided symbols today (set by load_universe_from_sheet)
        self._sheet_loaded_today = False

        # Per-symbol direction tag: "LONG", "SHORT", or None (no gap)
        self.symbol_direction = {}
        self.prior_close = {}
        self.gap_qualified = {}

        # Daily P&L tracking
        self.day_start_equity = self.config.ACCOUNT_SIZE
        self.daily_halt = False
        self.daily_warning_fired = False
        self.max_drawdown_dollars = 0
        self.worst_daily_loss = 0

        # Trade tracking for optimization scoring
        self.total_wins = 0
        self.total_losses = 0
        self.total_profit = 0.0
        self.total_loss_amt = 0.0

        # Trade log — accumulates CSV rows, written to ObjectStore at EOA
        self.trade_log_rows = []
        self.trade_id = 0

        # Spread/allocation rejection dedup (one log per symbol per day)
        self._spread_rejected_today = set()
        self._alloc_rejected_today = set()

        # Order fill tracking — correct entry prices using actual fills
        self._entry_order_ids = {}    # order_id -> symbol
        self._actual_entry_fills = {} # symbol -> fill_price

        # Daily rejection buffer for ObjectStore CSV
        self._all_reject_rows = []

        # (log buffer initialized at top of initialize())

        # Daily reset schedule
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(9, 25),
            self.daily_reset
        )

        # Universe load: sheet at 9:15, auto scanner at 9:20 (fallback if sheet empty)
        if self.config.UNIVERSE_SHEET_URL:
            self.schedule.on(
                self.date_rules.every_day(),
                self.time_rules.at(9, 15),
                self.load_universe_from_sheet
            )

        if self.config.USE_AUTO_UNIVERSE:
            self.schedule.on(
                self.date_rules.every_day(),
                self.time_rules.at(9, 20),
                self.run_gap_scanner
            )

        # SpotGamma data loading
        if self.sg_mgr:
            self.sg_mgr.load_history()
            self.schedule.on(
                self.date_rules.every_day(),
                self.time_rules.at(9, 20),
                self.sg_mgr.load_current_day
            )

        # EOD close — flatten all positions at 3:55 PM ET
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(15, 55),
            self.eod_close
        )

    def _log(self, msg):
        """Buffer log message to ObjectStore instead of QC log to avoid daily quota.
        Timestamp is prepended automatically. Use self._log() ONLY for fatal errors."""
        ts = self.time.strftime("%Y-%m-%d %H:%M:%S")
        self._log_buffer.append(f"{ts} {msg}")

    def _apply_parameters(self):
        """Override config defaults with QC optimization parameters if provided.
        Every numeric/boolean config parameter is optimizable via get_parameter().
        Parameter names use snake_case matching the config attribute names (lowercased).
        """
        def _float(name, attr):
            p = self.get_parameter(name)
            if p is not None:
                setattr(self.config, attr, float(p))

        def _int(name, attr):
            p = self.get_parameter(name)
            if p is not None:
                setattr(self.config, attr, int(p))

        def _bool(name, attr):
            p = self.get_parameter(name)
            if p is not None:
                setattr(self.config, attr, str(p).lower() in ("true", "1", "yes"))

        # ── Account ──
        _int("account_size", "ACCOUNT_SIZE")
        _float("base_daily_risk", "BASE_DAILY_RISK")
        _float("max_total_allocated", "MAX_TOTAL_ALLOCATED")

        # ── Regime ──
        _float("regime_current", "REGIME_CURRENT")

        # ── Long direction parameters ──
        p = self.get_parameter("long_orb_minutes")
        if p is not None:
            self.config.LONG_ORB_MINUTES = int(p)
            base = datetime(2000, 1, 1, 9, 30)
            self.config.LONG_ORB_CLOSE_TIME = (base + timedelta(minutes=self.config.LONG_ORB_MINUTES)).time()

        _float("long_breakout_offset", "LONG_BREAKOUT_OFFSET")
        _float("long_atr_base_mult", "LONG_ATR_BASE_MULTIPLIER")
        _float("long_atr_tier1_mult", "LONG_ATR_TIER1_MULTIPLIER")
        _float("long_atr_tier2_mult", "LONG_ATR_TIER2_MULTIPLIER")
        _float("long_atr_profit_tier1", "LONG_ATR_PROFIT_TIER1")
        _float("long_atr_profit_tier2", "LONG_ATR_PROFIT_TIER2")
        _float("long_hard_stop_pct", "LONG_HARD_STOP_PCT")
        _float("long_atr_activation_pct", "LONG_ATR_ACTIVATION_PCT")
        _float("long_r_tp1", "LONG_R_TP1")
        _float("long_r_tp2", "LONG_R_TP2")
        _float("long_r_tp3", "LONG_R_TP3")

        # ── Short direction parameters ──
        p = self.get_parameter("short_orb_minutes")
        if p is not None:
            self.config.SHORT_ORB_MINUTES = int(p)
            base = datetime(2000, 1, 1, 9, 30)
            self.config.SHORT_ORB_CLOSE_TIME = (base + timedelta(minutes=self.config.SHORT_ORB_MINUTES)).time()

        _float("short_breakout_offset", "SHORT_BREAKOUT_OFFSET")
        _float("short_atr_base_mult", "SHORT_ATR_BASE_MULTIPLIER")
        _float("short_atr_tier1_mult", "SHORT_ATR_TIER1_MULTIPLIER")
        _float("short_atr_tier2_mult", "SHORT_ATR_TIER2_MULTIPLIER")
        _float("short_atr_profit_tier1", "SHORT_ATR_PROFIT_TIER1")
        _float("short_atr_profit_tier2", "SHORT_ATR_PROFIT_TIER2")
        _float("short_hard_stop_pct", "SHORT_HARD_STOP_PCT")
        _float("short_atr_activation_pct", "SHORT_ATR_ACTIVATION_PCT")
        _float("short_r_tp1", "SHORT_R_TP1")
        _float("short_r_tp2", "SHORT_R_TP2")
        _float("short_r_tp3", "SHORT_R_TP3")

        # ── Exit toggles ──
        _bool("use_take_profit", "USE_TAKE_PROFIT")
        _bool("ema_cross_exit", "EMA_CROSS_EXIT")
        _bool("use_vwap_recross_exit", "USE_VWAP_RECROSS_EXIT")
        _int("vwap_recross_min_bars", "VWAP_RECROSS_MIN_BARS")

        # ── Gap filter ──
        _float("gap_filter_pct", "GAP_FILTER_PCT")
        _bool("use_gap_direction_gate", "USE_GAP_DIRECTION_GATE")
        _float("gap_reject_threshold", "GAP_REJECT_THRESHOLD")

        # ── EMA periods ──
        _int("ema_fast", "EMA_FAST")
        _int("ema_mid", "EMA_MID")
        _int("ema_slow", "EMA_SLOW")

        # ── ATR period ──
        _int("atr_period", "ATR_PERIOD")

        # ── Universe limits ──
        _int("max_longs", "MAX_LONGS")
        _int("max_shorts", "MAX_SHORTS")

        # ── Daily trade limits (per-symbol) ──
        _int("max_daily_longs", "MAX_DAILY_LONGS")
        _int("max_daily_shorts", "MAX_DAILY_SHORTS")
        _int("max_daily_losses_long", "MAX_DAILY_LOSSES_LONG")
        _int("max_daily_losses_short", "MAX_DAILY_LOSSES_SHORT")

        # ── Daily trade limits (global) ──
        _int("max_daily_total_longs", "MAX_DAILY_TOTAL_LONGS")
        _int("max_daily_total_shorts", "MAX_DAILY_TOTAL_SHORTS")
        _int("max_daily_total_losses", "MAX_DAILY_TOTAL_LOSSES")

        # ── Long entry filters ──
        _bool("long_require_ema_align", "LONG_REQUIRE_EMA_ALIGN")
        _bool("long_require_vwap", "LONG_REQUIRE_VWAP")
        _bool("long_require_higher_close", "LONG_REQUIRE_HIGHER_CLOSE")
        _bool("long_require_higher_open", "LONG_REQUIRE_HIGHER_OPEN")
        _bool("long_require_volume_rising", "LONG_REQUIRE_VOLUME_RISING")
        _bool("long_require_max_wick", "LONG_REQUIRE_MAX_WICK")
        _bool("long_require_entry_window", "LONG_REQUIRE_ENTRY_WINDOW")

        # ── Short entry filters ──
        _bool("short_require_ema_align", "SHORT_REQUIRE_EMA_ALIGN")
        _bool("short_require_vwap", "SHORT_REQUIRE_VWAP")
        _bool("short_require_higher_close", "SHORT_REQUIRE_HIGHER_CLOSE")
        _bool("short_require_higher_open", "SHORT_REQUIRE_HIGHER_OPEN")
        _bool("short_require_volume_rising", "SHORT_REQUIRE_VOLUME_RISING")
        _bool("short_require_max_wick", "SHORT_REQUIRE_MAX_WICK")
        _bool("short_require_entry_window", "SHORT_REQUIRE_ENTRY_WINDOW")

        # ── Spread & wick filter parameters ──
        _float("max_spread_pct", "MAX_SPREAD_PCT")
        _float("max_wick_pct", "MAX_WICK_PCT")
        _int("entry_window_bars", "ENTRY_WINDOW_BARS")

        # ── SpotGamma parameters ──
        _bool("sg_enabled", "SG_ENABLED")
        _bool("sg_use_gamma_regime", "SG_USE_GAMMA_REGIME")
        _float("sg_gamma_negative_size_mult", "SG_GAMMA_NEGATIVE_SIZE_MULT")
        _bool("sg_use_wall_targets", "SG_USE_WALL_TARGETS")
        _float("sg_wall_proximity_pct", "SG_WALL_PROXIMITY_PCT")
        _float("sg_wall_trail_multiplier", "SG_WALL_TRAIL_MULTIPLIER")
        _bool("sg_use_range_validation", "SG_USE_RANGE_VALIDATION")
        _float("sg_max_orb_to_implied_pct", "SG_MAX_ORB_TO_IMPLIED_PCT")
        _bool("sg_use_conviction_filter", "SG_USE_CONVICTION_FILTER")
        _bool("sg_block_long_on_bearish", "SG_BLOCK_LONG_ON_BEARISH")
        _bool("sg_block_short_on_bullish", "SG_BLOCK_SHORT_ON_BULLISH")
        _bool("sg_block_on_neutral", "SG_BLOCK_ON_NEUTRAL")
        _bool("sg_use_opex_filter", "SG_USE_OPEX_FILTER")
        _bool("sg_opex_block_near", "SG_OPEX_BLOCK_NEAR")
        _bool("sg_opex_block_distant", "SG_OPEX_BLOCK_DISTANT")

        # ── Direction override ──
        _int("force_direction", "FORCE_DIRECTION")

        # ── Auto universe scanner thresholds ──
        _float("auto_min_price", "AUTO_MIN_PRICE")
        _float("auto_max_price", "AUTO_MAX_PRICE")
        _float("auto_min_adv", "AUTO_MIN_ADV")
        _float("auto_min_today_volume", "AUTO_MIN_TODAY_VOLUME")
        _float("auto_min_atr", "AUTO_MIN_ATR")
        _float("auto_gap_pct", "AUTO_GAP_PCT")
        _float("auto_max_gap_pct", "AUTO_MAX_GAP_PCT")
        _float("auto_max_short_float", "AUTO_MAX_SHORT_FLOAT")
        _float("auto_min_float_shares", "AUTO_MIN_FLOAT_SHARES")
        _bool("auto_require_eps", "AUTO_REQUIRE_EPS")
        _float("auto_min_market_cap", "AUTO_MIN_MARKET_CAP")
        _bool("auto_no_earnings_today", "AUTO_NO_EARNINGS_TODAY")
        _int("auto_max_symbols", "AUTO_MAX_SYMBOLS")

        # ── Linked parameters (set both long+short at once for optimization) ──
        p = self.get_parameter("atr_base_mult")
        if p is not None:
            self.config.LONG_ATR_BASE_MULTIPLIER = float(p)
            self.config.SHORT_ATR_BASE_MULTIPLIER = float(p)

        p = self.get_parameter("atr_tier1_mult")
        if p is not None:
            self.config.LONG_ATR_TIER1_MULTIPLIER = float(p)
            self.config.SHORT_ATR_TIER1_MULTIPLIER = float(p)

        p = self.get_parameter("atr_tier2_mult")
        if p is not None:
            self.config.LONG_ATR_TIER2_MULTIPLIER = float(p)
            self.config.SHORT_ATR_TIER2_MULTIPLIER = float(p)

        p = self.get_parameter("atr_profit_tier1")
        if p is not None:
            self.config.LONG_ATR_PROFIT_TIER1 = float(p)
            self.config.SHORT_ATR_PROFIT_TIER1 = float(p)

        p = self.get_parameter("atr_profit_tier2")
        if p is not None:
            self.config.LONG_ATR_PROFIT_TIER2 = float(p)
            self.config.SHORT_ATR_PROFIT_TIER2 = float(p)

        p = self.get_parameter("hard_stop_pct")
        if p is not None:
            self.config.LONG_HARD_STOP_PCT = float(p)
            self.config.SHORT_HARD_STOP_PCT = float(p)

        p = self.get_parameter("atr_activation_pct")
        if p is not None:
            self.config.LONG_ATR_ACTIVATION_PCT = float(p)
            self.config.SHORT_ATR_ACTIVATION_PCT = float(p)

        p = self.get_parameter("r_tp1")
        if p is not None:
            self.config.LONG_R_TP1 = float(p)
            self.config.SHORT_R_TP1 = float(p)

        p = self.get_parameter("r_tp2")
        if p is not None:
            self.config.LONG_R_TP2 = float(p)
            self.config.SHORT_R_TP2 = float(p)

        p = self.get_parameter("r_tp3")
        if p is not None:
            self.config.LONG_R_TP3 = float(p)
            self.config.SHORT_R_TP3 = float(p)

        p = self.get_parameter("orb_minutes")
        if p is not None:
            self.config.LONG_ORB_MINUTES = int(p)
            self.config.SHORT_ORB_MINUTES = int(p)
            base = datetime(2000, 1, 1, 9, 30)
            close_time = (base + timedelta(minutes=int(p))).time()
            self.config.LONG_ORB_CLOSE_TIME = close_time
            self.config.SHORT_ORB_CLOSE_TIME = close_time

        p = self.get_parameter("breakout_offset")
        if p is not None:
            self.config.LONG_BREAKOUT_OFFSET = float(p)
            self.config.SHORT_BREAKOUT_OFFSET = float(p)

        # ── Backward-compat shortcut ──
        p = self.get_parameter("max_trades_per_direction")
        if p is not None:
            self.config.MAX_DAILY_LONGS = int(p)
            self.config.MAX_DAILY_SHORTS = int(p)

        # ── Live override: clear a symbol from QC internal state ──
        p = self.get_parameter("clear_symbol")
        if p is not None and p != "":
            self._log(f"[CLEAR_SYMBOL] Wiping QC state for {p}")
            clear_sym = self.add_equity(p, Resolution.MINUTE).symbol
            if self.portfolio[clear_sym].invested:
                self.liquidate(clear_sym)

    def _load_fallback_universe(self):
        """Hardcoded fallback universe when no Google Sheets URL is configured."""
        fallback = {"TSLA": -0.08}
        for ticker, dd in fallback.items():
            symbol = self.add_equity(ticker, Resolution.MINUTE).symbol
            self.symbols.append(symbol)
            self.indicators.register(symbol)
            self.max_dd[symbol] = dd
        self._log(f"[UNIVERSE] Fallback loaded: {list(fallback.keys())}")

    def load_universe_from_sheet(self):
        """Fetch published Google Sheets CSV and load today's universe."""
        try:
            today_str = self.time.strftime("%Y-%m-%d")
            raw = self.download(self.config.UNIVERSE_SHEET_URL)
            if not raw:
                self._log("[UNIVERSE] Empty response from sheet URL")
                return

            reader = csv.DictReader(io.StringIO(raw))
            today_symbols = {}  # ticker -> {direction, tier, max_dd}

            for row in reader:
                if row.get("Date", "").strip() != today_str:
                    continue
                ticker = row.get("Symbol", "").strip().upper()
                direction = row.get("Direction", "").strip().upper()
                if not ticker or direction not in ("LONG", "SHORT"):
                    continue

                # Tier: use Final Tier if present, else Var Tier, else "T1"
                tier_raw = (row.get("Final Tier") or row.get("Var Tier") or "T1").strip().upper().lstrip("T")
                tier = int(tier_raw) if tier_raw.isdigit() else 1

                # Max DD from sheet (e.g. "-6.60%") or tier default
                tier_dd_map = {1: -0.08, 2: -0.06, 3: -0.04}
                max_dd_str = row.get("Max DD %", "").strip().rstrip("%")
                try:
                    max_dd = float(max_dd_str) / 100 if max_dd_str else tier_dd_map.get(tier, -0.08)
                except ValueError:
                    max_dd = tier_dd_map.get(tier, -0.08)

                today_symbols[ticker] = {
                    "direction": direction,
                    "tier": tier,
                    "max_dd": max_dd,
                    "source": "SHEET",
                    # Sheet fields
                    "gap_pct_sheet": row.get("Gap %", "").strip(),
                    "catalyst": row.get("Catalyst", "").strip(),
                    "cat_quality": row.get("Cat Quality", "").strip(),
                    "var_tier": row.get("Var Tier", "").strip(),
                    "final_tier": row.get("Final Tier", "").strip(),
                    "max_dd_sheet": row.get("Max DD %", "").strip(),
                    "net_perf": row.get("Net Perf %", "").strip(),
                    "expectancy": row.get("Expectancy", "").strip(),
                    "notes": row.get("Notes", "").strip(),
                    # Trade-Ideas fields
                    "ti_timestamp": row.get("TI Timestamp", "").strip(),
                    "ti_price": row.get("TI Price", "").strip(),
                    "ti_chg_dollar": row.get("TI Chg $", "").strip(),
                    "ti_chg_pct": row.get("TI Chg %", "").strip(),
                    "ti_volume": row.get("TI Volume", "").strip(),
                    "ti_rel_vol": row.get("TI Rel Vol", "").strip(),
                    "ti_gap_pct": row.get("TI Gap %", "").strip(),
                    "ti_float": row.get("TI Float", "").strip(),
                    "ti_atr": row.get("TI ATR", "").strip(),
                    "ti_avg_vol_5d": row.get("TI Avg Vol 5D", "").strip(),
                    "ti_dist_vwap": row.get("TI Dist VWAP", "").strip(),
                }

            if not today_symbols:
                self._log(f"[UNIVERSE] No sheet symbols for {today_str} — auto scanner will run")
                self._sheet_loaded_today = False
                return
            self._sheet_loaded_today = True

            # Remove stale symbols no longer in today's list
            new_symbol_objects = set()
            for ticker, meta in today_symbols.items():
                symbol = self.add_equity(ticker, Resolution.MINUTE).symbol
                new_symbol_objects.add(symbol)
                if symbol not in self.symbols:
                    self.symbols.append(symbol)
                    self.indicators.register(symbol)
                self.max_dd[symbol] = meta["max_dd"]
                self.symbol_meta[symbol] = meta
                self._log(f"[UNIVERSE LOADED] {ticker} {meta['direction']} T{meta['tier']} maxdd={meta['max_dd']}")

            # Remove symbols from previous day that aren't in today's list
            stale = [s for s in self.symbols if s not in new_symbol_objects]
            for s in stale:
                self.symbols.remove(s)
                self.max_dd.pop(s, None)
                self.symbol_meta.pop(s, None)
                self._log(f"[UNIVERSE REMOVED] {s}")

            self._log(f"[UNIVERSE] Loaded {len(today_symbols)} symbols for {today_str}")

        except Exception as e:
            self._log(f"[UNIVERSE ERROR] {str(e)}")

    def _load_watchlist(self):
        """Load watchlist from Google Sheets and subscribe at Minute + extended hours
        for real pre-market gap scanning."""
        tickers = []

        try:
            if self.config.WATCHLIST_SHEET_URL:
                raw = self.download(self.config.WATCHLIST_SHEET_URL)
                if raw:
                    reader = csv.DictReader(io.StringIO(raw))
                    for row in reader:
                        ticker = row.get("Symbol", "").strip().upper()
                        if ticker:
                            tickers.append(ticker)
                    self._log(f"[WATCHLIST] Loaded {len(tickers)} symbols from sheet")
                else:
                    self._log("[WATCHLIST] Empty response — using fallback")
            else:
                self._log("[WATCHLIST] No URL set — using fallback")
        except Exception as e:
            self._log(f"[WATCHLIST ERROR] {str(e)} — using fallback")

        # Fallback if sheet unavailable
        if not tickers:
            tickers = [
                "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO",
                "JPM","V","UNH","XOM","LLY","MA","HD","PG","COST","ABBV",
                "PLTR","COIN","HOOD","RIVN","SOFI","UPST","AFRM","DKNG",
                "AMD","INTC","QCOM","MU","SMCI","MRVL","AMAT","LRCX",
                "CRWD","PANW","OKTA","ZS","DDOG","NET","SNOW","S",
                "ENPH","SEDG","FSLR","PLUG","BE","IREN","MARA","HUT",
                "MRNA","BNTX","BIIB","REGN","VRTX","ILMN",
                "GS","MS","BAC","WFC","C","AXP","COF",
                "OXY","DVN","MRO","COP","EOG","SLB","HAL",
                "LI","XPEV","NIO","LCID",
                "GME","AMC","RBLX","U","SNAP","PINS",
                "WMT","TGT","EBAY","W","CHWY","ETSY",
                "CVS","HCA","THC","CNC","ELV","HUM",
                "AAOI","RCAT","WKEY","QUBT","QBTS","IONQ",
            ]
            self._log(f"[WATCHLIST] Fallback loaded {len(tickers)} symbols")

        # Deduplicate
        seen = set()
        unique_tickers = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                unique_tickers.append(t)

        # Subscribe all at Minute + extended market hours for real pre-market data
        for ticker in unique_tickers:
            try:
                sym = self.add_equity(
                    ticker, Resolution.MINUTE,
                    extended_market_hours=True
                ).symbol
                self.watchlist_symbols.append(sym)
            except:
                self._log(f"[WATCHLIST SKIP] {ticker}")

        self._log(f"[WATCHLIST] Subscribed {len(self.watchlist_symbols)} symbols at Minute + extended hours")

    def run_gap_scanner(self):
        """Daily gap scanner — runs at 9:20 AM ET.
        Uses REAL pre-market prices from Minute + extended hours subscriptions
        to compute true gaps vs yesterday's close.
        Skipped when Google Sheets provided symbols for today."""
        try:
            # Skip weekends
            if self.time.weekday() >= 5:
                return

            # Sheet-first priority: if curated list loaded, skip auto scanner
            if self._sheet_loaded_today:
                self._log("[GAP_SCANNER] Sheet provided symbols for today — skipping auto scan")
                return

            cfg = self.config
            date_str = self.time.strftime("%Y-%m-%d")

            # Remove previous day's auto-selected trading symbols
            stale = [s for s in list(self.symbols) if s in self.auto_universe_candidates]
            for s in stale:
                self.symbols.remove(s)
                self.max_dd.pop(s, None)
                self.symbol_meta.pop(s, None)
            self.auto_universe_candidates.clear()

            self.debug(f"[GAP_SCANNER] {date_str} scanning {len(self.watchlist_symbols)} watchlist symbols")

            if not self.watchlist_symbols:
                self._log("[GAP_SCANNER] No watchlist symbols — skipping")
                return

            # Get daily history for ATR/ADV calculations
            all_hist = self.history(self.watchlist_symbols, 22, Resolution.DAILY)
            if all_hist.empty:
                self._log("[GAP_SCANNER] No history data available")
                return

            # Build prev_close lookup from daily history
            prev_closes = {}
            try:
                for sym in all_hist.index.get_level_values(0).unique():
                    hist = all_hist.loc[sym]
                    if len(hist) >= 2:
                        prev_closes[sym] = hist["close"].iloc[-1]  # yesterday's close
            except:
                self._log("[GAP_SCANNER] Could not build prev_close lookup")
                return

            # Scan using REAL pre-market prices
            candidates = []
            diag = {"scanned": 0, "no_price": 0, "price_fail": 0, "gap_fail": 0,
                    "atr_fail": 0, "adv_fail": 0, "errors": 0}

            for sym in self.watchlist_symbols:
                try:
                    diag["scanned"] += 1

                    # Real pre-market price from Minute + extended hours subscription
                    pre_market_price = self.securities[sym].price
                    if pre_market_price <= 0:
                        diag["no_price"] += 1
                        continue

                    prev_close = prev_closes.get(sym, 0)
                    if prev_close <= 0:
                        diag["no_price"] += 1
                        continue

                    # Price filters
                    if pre_market_price < cfg.AUTO_MIN_PRICE or pre_market_price > cfg.AUTO_MAX_PRICE:
                        diag["price_fail"] += 1
                        continue

                    # TRUE gap: pre-market price vs yesterday's close
                    gap_pct = (pre_market_price - prev_close) / prev_close
                    abs_gap = abs(gap_pct)
                    if abs_gap < cfg.AUTO_GAP_PCT or abs_gap > cfg.AUTO_MAX_GAP_PCT:
                        diag["gap_fail"] += 1
                        continue

                    # ATR14 from daily history
                    hist = all_hist.loc[sym]
                    highs = hist["high"].values
                    lows = hist["low"].values
                    closes = hist["close"].values
                    trs = []
                    for i in range(1, len(highs)):
                        tr = max(
                            highs[i] - lows[i],
                            abs(highs[i] - closes[i - 1]),
                            abs(lows[i] - closes[i - 1])
                        )
                        trs.append(tr)
                    atr14 = sum(trs[-14:]) / 14
                    if atr14 < cfg.AUTO_MIN_ATR:
                        diag["atr_fail"] += 1
                        continue

                    # ADV (average daily volume over ~21 days)
                    adv = hist["volume"].mean()
                    if adv < cfg.AUTO_MIN_ADV:
                        diag["adv_fail"] += 1
                        continue

                    direction = "LONG" if gap_pct > 0 else "SHORT"
                    candidates.append((sym, gap_pct, atr14, int(adv), pre_market_price, direction))
                except:
                    diag["errors"] += 1
                    continue

            self.debug(f"[GAP_SCANNER DIAG] {diag} candidates={len(candidates)}")

            if not candidates:
                self._log("[GAP_SCANNER] No candidates today")
                return

            # Sort by abs gap, take top N
            candidates.sort(key=lambda x: abs(x[1]), reverse=True)
            final = candidates[:cfg.AUTO_MAX_SYMBOLS]

            # Add winners to active trading list (already subscribed at Minute)
            for sym, gap_pct, atr14, adv, price, direction in final:
                if sym not in self.symbols:
                    self.symbols.append(sym)
                    self.indicators.register(sym)

                self.max_dd[sym] = -0.06
                self.auto_universe_candidates[sym] = {
                    "direction": direction,
                    "gap_pct": round(gap_pct * 100, 2),
                    "atr": atr14,
                    "adv": adv,
                }
                self.symbol_meta[sym] = {
                    "direction": direction,
                    "tier": 2,
                    "max_dd": -0.06,
                }
                self.debug(
                    f"[GAP_SCANNER] {sym.value} {direction} "
                    f"gap={gap_pct * 100:.1f}% atr={atr14:.2f} "
                    f"adv={adv:,.0f} price={price:.2f}"
                )

            # Audit trail to ObjectStore
            try:
                rows = [
                    f"{date_str},{sym.value},{gap_pct * 100:.2f},{atr14:.2f},{adv},{direction}"
                    for sym, gap_pct, atr14, adv, price, direction in final
                ]
                csv_str = "date,symbol,gap_pct,atr,adv,direction\n" + "\n".join(rows)
                self.object_store.save(f"auto_universe_{date_str}.csv", csv_str)
            except:
                pass

            # Append daily diagnostics to cumulative log
            try:
                diag_key = "gap_scanner_diag.csv"
                existing = ""
                if self.object_store.contains_key(diag_key):
                    existing = self.object_store.read(diag_key)
                if not existing:
                    existing = "date,watchlist,scanned,no_price,price_fail,gap_fail,atr_fail,adv_fail,errors,candidates,selected\n"
                line = (f"{date_str},{len(self.watchlist_symbols)},{diag['scanned']},"
                        f"{diag['no_price']},{diag['price_fail']},{diag['gap_fail']},"
                        f"{diag['atr_fail']},{diag['adv_fail']},{diag['errors']},"
                        f"{len(candidates)},{len(final)}")
                self.object_store.save(diag_key, existing + line + "\n")
            except:
                pass

            self._log(f"[GAP_SCANNER] Selected {len(final)} symbols")

        except Exception as e:
            self._log(f"[GAP_SCANNER ERROR] {str(e)}")

    def eod_close(self):
        if self.time.weekday() >= 5:
            return
        for symbol in self.symbols:
            if self.portfolio[symbol].invested:
                price = self.securities[symbol].price
                self.exit_position(symbol, price, "EOD")
        self._log("[EOD CLOSE] All positions flattened")

    def daily_reset(self):
        if self.time.weekday() >= 5:
            return

        # Flush previous day's signal rejections to ObjectStore buffer
        day_rejects = self.signal_engine.get_and_clear_reject_buffer()
        self._all_reject_rows.extend(day_rejects)

        self.risk_mgr.reset_daily()
        self.trade_mgr.reset()
        self.signal_engine.reset_daily()
        if self.sg_mgr:
            self.sg_mgr.reset_daily()
        self.daily_halt = False
        self.daily_warning_fired = False
        self._sheet_loaded_today = False
        self._spread_rejected_today.clear()
        self._alloc_rejected_today.clear()
        self._actual_entry_fills.clear()
        self._entry_order_ids.clear()
        self.day_start_equity = self.portfolio.total_portfolio_value
        for symbol in self.symbols:
            self.orb.reset(symbol)
            self.symbol_direction[symbol] = None
            self.gap_qualified[symbol] = False

            # Get prior daily close and tag direction based on gap
            hist = self.history(symbol, 2, Resolution.DAILY)
            if hist.empty or len(hist) < 1:
                continue
            self.prior_close[symbol] = hist["close"].iloc[-1]

    def _tag_direction(self, symbol):
        """Tag symbol as LONG or SHORT based on symbol_meta, FORCE_DIRECTION, or gap."""
        # Priority 1: symbol_meta from Google Sheets (overrides FORCE_DIRECTION)
        meta = self.symbol_meta.get(symbol)
        if meta:
            self.symbol_direction[symbol] = meta["direction"]
            self.gap_qualified[symbol] = True
            self.debug(f"[SHEET_DIRECTION] {symbol} tagged {meta['direction']} (T{meta['tier']})")
            return True

        # Priority 2: FORCE_DIRECTION config
        if self.config.FORCE_DIRECTION == 1:
            self.symbol_direction[symbol] = "LONG"
            self.gap_qualified[symbol] = True
            self.debug(f"[FORCE_DIRECTION] {symbol} forced to LONG")
            return True
        elif self.config.FORCE_DIRECTION == -1:
            self.symbol_direction[symbol] = "SHORT"
            self.gap_qualified[symbol] = True
            self.debug(f"[FORCE_DIRECTION] {symbol} forced to SHORT")
            return True

        prior = self.prior_close.get(symbol)
        if prior is None or prior == 0:
            return False

        today_open = self.securities[symbol].open
        if today_open == 0:
            return False

        gap_pct = (today_open - prior) / prior

        if abs(gap_pct) < self.config.GAP_FILTER_PCT:
            return False

        if gap_pct > 0:
            self.symbol_direction[symbol] = "LONG"
        else:
            self.symbol_direction[symbol] = "SHORT"

        self.gap_qualified[symbol] = True
        return True

    def check_daily_pnl(self):
        current_equity = self.portfolio.total_portfolio_value
        daily_loss = self.day_start_equity - current_equity
        starting_cash = self.config.ACCOUNT_SIZE

        if daily_loss > self.worst_daily_loss:
            self.worst_daily_loss = daily_loss

        peak = max(self.day_start_equity, current_equity)
        dd = peak - current_equity
        if dd > self.max_drawdown_dollars:
            self.max_drawdown_dollars = dd

        if not self.daily_warning_fired and daily_loss >= starting_cash * 0.018:
            self._log(f"[DAILY WARNING] Loss ${daily_loss:.2f} approaching 2% limit")
            self.daily_warning_fired = True

        if not self.daily_halt and daily_loss >= starting_cash * 0.02:
            self._log(f"[DAILY HALT] Loss ${daily_loss:.2f} hit 2% limit — liquidating all")
            self.liquidate()
            self.daily_halt = True

    def on_data(self, data):
        try:
            # ── BUG FIX: Skip extended hours bars entirely ──
            bar_time = self.time.time()
            if bar_time < time(9, 30) or bar_time >= time(16, 0):
                return

            self.check_daily_pnl()

            if self.daily_halt:
                return

            for symbol in self.symbols:
                if not data.bars.contains_key(symbol):
                    continue

                bar = data.bars[symbol]

                # Track previous bar for higher/lower close filter
                self.signal_engine.update_prev_bar(symbol, bar)

                # Build ORB range during opening period
                self.orb.update(symbol, bar)

                # Skip if ORB not locked or indicators not ready
                if not self.orb.is_locked(symbol):
                    continue
                if not self.indicators.is_ready(symbol):
                    continue

                atr = self.indicators.get_atr(symbol)
                is_invested = self.portfolio[symbol].invested

                # Manage open positions
                if is_invested:
                    # Unified bar processing: Step 1-5 in strict order
                    vwap_current = self.indicators.get_vwap(symbol)
                    stopped, reason = self.trade_mgr.process_bar(
                        symbol, bar.close, bar.high, bar.low, atr, vwap_current
                    )
                    if stopped:
                        if reason.startswith("TP"):
                            # Partial take profit — sell portion, keep position open
                            tp_idx = int(reason[2]) - 1
                            tp_shares = self.trade_mgr.entries[symbol]["tp_shares"][tp_idx]
                            tp_price = self.trade_mgr.entries[symbol]["tp_prices"][tp_idx]
                            if tp_shares > 0:
                                self.partial_exit(symbol, bar.close, tp_shares, reason, tp_price)
                        else:
                            self.exit_position(symbol, bar.close, reason)
                        continue

                    # Step 5 continued: EMA cross exit
                    ema_fast = self.indicators.get_ema_fast(symbol)
                    ema_mid = self.indicators.get_ema_mid(symbol)
                    if self.trade_mgr.check_ema_cross_exit(symbol, ema_fast, ema_mid):
                        self.exit_position(symbol, bar.close, "EMA_CROSS")
                    continue

                # Tag direction on first bar after ORB lock if not yet tagged
                if not self.gap_qualified.get(symbol, False):
                    if not self._tag_direction(symbol):
                        continue
                    # Store gap_pct on signal engine for gap direction gate
                    prior = self.prior_close.get(symbol, 0)
                    today_open = self.securities[symbol].open
                    gap_pct = (today_open - prior) / prior if prior > 0 else 0
                    self.signal_engine.set_gap_pct(symbol, gap_pct)

                direction = self.symbol_direction.get(symbol)
                if direction is None:
                    continue

                # Spread check — reject if bid-ask spread > MAX_SPREAD_PCT of mid-price
                security = self.securities[symbol]
                bid = security.bid_price
                ask = security.ask_price
                spread = ask - bid if bid > 0 and ask > 0 else 0
                mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
                spread_pct = (spread / mid * 100) if mid > 0 else 999
                if spread_pct > self.config.MAX_SPREAD_PCT:
                    sym_key = str(symbol)
                    if sym_key not in self._spread_rejected_today:
                        self._spread_rejected_today.add(sym_key)
                        self._log(f"[SPREAD REJECT] {symbol} spread={spread_pct:.3f}% (${spread:.3f}) bid={bid:.2f} ask={ask:.2f} max={self.config.MAX_SPREAD_PCT}%")
                    continue

                # Only trade the tagged direction for this symbol (per-symbol daily limits)
                if direction == "LONG":
                    if not self.risk_mgr.can_trade_long(symbol):
                        sym_key = str(symbol)
                        if sym_key not in self._alloc_rejected_today:
                            self._alloc_rejected_today.add(sym_key)
                            self._log(f"[LIMIT] {symbol} LONG — sym={self.risk_mgr.get_symbol_long_count(symbol)}/{self.config.MAX_DAILY_LONGS} total={self.risk_mgr.total_long_entries()}/{self.config.MAX_DAILY_TOTAL_LONGS} losses={self.risk_mgr.total_losses()}/{self.config.MAX_DAILY_TOTAL_LOSSES} open={self.risk_mgr.open_long_count()}/{self.config.MAX_LONGS}")
                    elif self.signal_engine.check_long(symbol, bar):
                        self.enter_long(symbol, bar, is_long=True)
                elif direction == "SHORT":
                    if not self.risk_mgr.can_trade_short(symbol):
                        sym_key = str(symbol)
                        if sym_key not in self._alloc_rejected_today:
                            self._alloc_rejected_today.add(sym_key)
                            self._log(f"[LIMIT] {symbol} SHORT — sym={self.risk_mgr.get_symbol_short_count(symbol)}/{self.config.MAX_DAILY_SHORTS} total={self.risk_mgr.total_short_entries()}/{self.config.MAX_DAILY_TOTAL_SHORTS} losses={self.risk_mgr.total_losses()}/{self.config.MAX_DAILY_TOTAL_LOSSES} open={self.risk_mgr.open_short_count()}/{self.config.MAX_SHORTS}")
                    elif self.signal_engine.check_short(symbol, bar):
                        self.enter_short(symbol, bar, is_long=False)
        except Exception as e:
            self.log(f"[ON_DATA ERROR] {str(e)}")

    def _build_entry_snapshot(self, symbol, bar):
        """Capture indicator values, config state, and bar data at entry time."""
        prior = self.prior_close.get(symbol, 0)
        today_open = self.securities[symbol].open
        gap_pct = (today_open - prior) / prior if prior > 0 else 0
        security = self.securities[symbol]
        bid = security.bid_price
        ask = security.ask_price
        spread = ask - bid if bid > 0 and ask > 0 else 0
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
        spread_pct = (spread / mid * 100) if mid > 0 else 0
        return {
            "vwap": self.indicators.get_vwap(symbol),
            "ema9": self.indicators.get_ema_fast(symbol),
            "ema20": self.indicators.get_ema_mid(symbol),
            "ema50": self.indicators.get_ema_slow(symbol),
            "orb_high": self.orb.get_high(symbol),
            "orb_low": self.orb.get_low(symbol),
            "orb_range": self.orb.get_range(symbol),
            "gap_pct": gap_pct,
            "prior_close": prior,
            "today_open": today_open,
            "bar_volume": int(bar.volume),
            "bar_range": bar.high - bar.low,
            "spread": spread,
            "spread_pct": spread_pct,
        }

    def _build_sg_snapshot(self, symbol):
        """Capture SpotGamma data at entry time for trade log stamping."""
        if not self.sg_mgr:
            return {}
        rec = self.sg_mgr.get(symbol)
        return rec if rec else {}

    def _build_universe_meta(self, symbol):
        """Build universe selection context for trade log stamping."""
        meta = self.symbol_meta.get(symbol, {})
        auto = self.auto_universe_candidates.get(symbol, {})

        # Determine source
        if self.config.USE_AUTO_UNIVERSE and auto:
            source = "AUTO"
        elif self.config.UNIVERSE_SHEET_URL and meta:
            source = "SHEET"
        else:
            source = "FALLBACK"

        return {
            "source": source,
            "tier": meta.get("tier", ""),
            "max_dd": meta.get("max_dd", self.max_dd.get(symbol, "")),
            "scanner_gap_pct": auto.get("gap_pct", 0) / 100 if auto.get("gap_pct") else 0,
            "scanner_atr": auto.get("atr", ""),
            "scanner_adv": auto.get("adv", ""),
        }

    def enter_long(self, symbol, bar, is_long=True):
        price = bar.close
        tier = self.symbol_meta.get(symbol, {}).get("tier")
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price, tier=tier)
        if shares <= 0:
            return

        # SpotGamma gamma regime size reduction (negative gamma = chaotic, reduce size)
        if (self.config.SG_ENABLED and self.config.SG_USE_GAMMA_REGIME
                and self.config.SG_GAMMA_NEGATIVE_ACTION == "reduce" and self.sg_mgr):
            regime = self.sg_mgr.get_gamma_regime(symbol)
            if regime == "negative":
                import math
                shares = max(1, math.floor(shares * self.config.SG_GAMMA_NEGATIVE_SIZE_MULT))
                self._log(f"[SG SIZE REDUCE] {symbol} LONG negative gamma → shares={shares}")

        # Capital allocation guard
        if not self.risk_mgr.check_allocation(shares, price):
            self._log(f"[ALLOC BLOCKED] {symbol} — ${shares * price:.0f} would exceed limit")
            return

        atr = self.indicators.get_atr(symbol)
        orb_range = self.orb.get_range(symbol)
        snapshot = self._build_entry_snapshot(symbol, bar)
        sg_snapshot = self._build_sg_snapshot(symbol)
        filter_evals = self.signal_engine.evaluate_filters_at_entry(symbol, bar, is_long=True)
        universe_meta = self._build_universe_meta(symbol)
        ticket = self.market_order(symbol, shares)
        self._entry_order_ids[ticket.order_id] = symbol
        self.trade_mgr.register_entry(symbol, price, is_long=True, atr=atr, orb_range=orb_range, total_shares=shares)
        self.trade_id += 1
        self.trade_mgr.create_record(symbol, self.trade_id, shares, snapshot, self.config, filter_evals, universe_meta, sg_snapshot)
        self.risk_mgr.record_long(symbol)
        self.risk_mgr.add_allocation(shares, price)
        self.bridge.send(str(symbol), "buy", shares)
        self._log(f"[LONG] {symbol} shares={shares} price={price:.2f}")

    def enter_short(self, symbol, bar, is_long=False):
        price = bar.close
        tier = self.symbol_meta.get(symbol, {}).get("tier")
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price, tier=tier)
        if shares <= 0:
            return

        # SpotGamma gamma regime size reduction (negative gamma = chaotic, reduce size)
        if (self.config.SG_ENABLED and self.config.SG_USE_GAMMA_REGIME
                and self.config.SG_GAMMA_NEGATIVE_ACTION == "reduce" and self.sg_mgr):
            regime = self.sg_mgr.get_gamma_regime(symbol)
            if regime == "negative":
                import math
                shares = max(1, math.floor(shares * self.config.SG_GAMMA_NEGATIVE_SIZE_MULT))
                self._log(f"[SG SIZE REDUCE] {symbol} SHORT negative gamma → shares={shares}")

        # Capital allocation guard
        if not self.risk_mgr.check_allocation(shares, price):
            self._log(f"[ALLOC BLOCKED] {symbol} — ${shares * price:.0f} would exceed limit")
            return

        atr = self.indicators.get_atr(symbol)
        orb_range = self.orb.get_range(symbol)
        snapshot = self._build_entry_snapshot(symbol, bar)
        sg_snapshot = self._build_sg_snapshot(symbol)
        filter_evals = self.signal_engine.evaluate_filters_at_entry(symbol, bar, is_long=False)
        universe_meta = self._build_universe_meta(symbol)
        ticket = self.market_order(symbol, -shares)
        self._entry_order_ids[ticket.order_id] = symbol
        self.trade_mgr.register_entry(symbol, price, is_long=False, atr=atr, orb_range=orb_range, total_shares=shares)
        self.trade_id += 1
        self.trade_mgr.create_record(symbol, self.trade_id, shares, snapshot, self.config, filter_evals, universe_meta, sg_snapshot)
        self.risk_mgr.record_short(symbol)
        self.risk_mgr.add_allocation(shares, price)
        self.bridge.send(str(symbol), "sell_short", shares)
        self._log(f"[SHORT] {symbol} shares={shares} price={price:.2f}")

    def partial_exit(self, symbol, price, tp_shares, reason, tp_price):
        """Execute a partial take-profit exit — sell portion, keep position open."""
        if not self.portfolio[symbol].invested:
            self._log(f"[PARTIAL SKIP] {symbol} — not invested")
            return

        is_long = self.trade_mgr.is_long(symbol)
        entry_price = self.trade_mgr.entries[symbol]["price"]

        # Clamp tp_shares to remaining position size
        remaining = abs(self.portfolio[symbol].quantity)
        shares_to_exit = min(tp_shares, remaining)
        if shares_to_exit <= 0:
            return

        # Execute partial order
        if is_long:
            self.market_order(symbol, -shares_to_exit)
            action = "sell"
        else:
            self.market_order(symbol, shares_to_exit)
            action = "buy_to_cover"

        # Mark TP level as hit in trade_mgr
        tp_idx = int(reason[2]) - 1
        self.trade_mgr.entries[symbol]["tp_hit"][tp_idx] = True
        self.trade_mgr.entries[symbol]["tp_fill_prices"][tp_idx] = price

        # Release capital for the partial shares
        self.risk_mgr.remove_allocation(shares_to_exit, entry_price)

        # Send to SignalStack
        self.bridge.send(str(symbol), action, shares_to_exit)

        # Calculate partial P&L for logging
        if is_long:
            partial_pnl = (price - entry_price) * shares_to_exit
        else:
            partial_pnl = (entry_price - price) * shares_to_exit

        self._log(f"[PARTIAL EXIT] {symbol} reason={reason} shares={shares_to_exit} "
                 f"price={price:.2f} tp_target={tp_price:.2f} pnl={partial_pnl:.2f} "
                 f"remaining={remaining - shares_to_exit}")

    def exit_position(self, symbol, price, reason=""):
        # Portfolio invested guard — don't liquidate already-closed positions
        if not self.portfolio[symbol].invested:
            self._log(f"[EXIT SKIP] {symbol} — not invested, clearing internal state only")
            self.trade_mgr.remove(symbol)
            return

        if symbol not in self.trade_mgr.entries:
            self._log(f"[EXIT SKIP] {symbol} — no trade_mgr entry, liquidating directly")
            self.liquidate(symbol)
            return

        is_long = self.trade_mgr.is_long(symbol)
        # Use actual fill price for entry if available, else bar.close estimate
        entry_price = self._actual_entry_fills.get(symbol, self.trade_mgr.entries[symbol]["price"])
        quantity = abs(self.portfolio[symbol].quantity)

        # Compute PnL using best available entry price (actual fill or bar.close)
        if is_long:
            pnl = (price - entry_price) * quantity
        else:
            pnl = (entry_price - price) * quantity

        # Track wins/losses for optimization scoring
        if pnl > 0:
            self.total_wins += 1
            self.total_profit += pnl
        else:
            self.total_losses += 1
            self.total_loss_amt += abs(pnl)

        # Track losses per direction (per-symbol)
        if pnl < 0:
            self.risk_mgr.record_loss(symbol, is_long=is_long)

        # Finalize trade record with computed PnL
        record = self.trade_mgr.finalize_record(symbol, price, self.time, pnl, quantity, reason)
        if record:
            row = TradeManager.format_record_row(record)
            self.trade_log_rows.append(row)

        # Release capital allocation and close position tracking
        self.risk_mgr.remove_allocation(quantity, entry_price)
        self.risk_mgr.close_position(symbol)

        self.liquidate(symbol)
        self.trade_mgr.remove(symbol)

        action = "sell" if is_long else "buy_to_cover"
        self.bridge.send(str(symbol), action, quantity)
        self._log(f"[EXIT] {symbol} reason={reason} action={action} qty={quantity} price={price:.2f} pnl={pnl:.2f}")

    def on_order_event(self, order_event):
        """Capture actual entry fill prices to correct entry price and hard stop."""
        if order_event.status != OrderStatus.FILLED:
            return

        oid = order_event.order_id
        symbol = order_event.symbol
        fill_price = float(order_event.fill_price)

        # Entry fill — update entry price in trade manager
        if oid in self._entry_order_ids:
            self._actual_entry_fills[symbol] = fill_price
            # Update trade_mgr entry with actual fill price
            if symbol in self.trade_mgr.entries:
                entry = self.trade_mgr.entries[symbol]
                entry["price"] = fill_price
                # Recalculate hard stop from actual fill
                if entry["is_long"]:
                    entry["hard_stop"] = fill_price * (1 - self.config.LONG_HARD_STOP_PCT)
                else:
                    entry["hard_stop"] = fill_price * (1 + self.config.SHORT_HARD_STOP_PCT)
                # Update open record too
                if symbol in self.trade_mgr.open_records:
                    rec = self.trade_mgr.open_records[symbol]
                    rec["entry_price"] = round(fill_price, 2)
                    rec["hard_stop"] = round(entry["hard_stop"], 2)
            del self._entry_order_ids[oid]

    def on_end_of_algorithm(self):
        try:
            starting_cash = self.config.ACCOUNT_SIZE

            # Hard disqualifiers — log warnings only (optimizer uses QC built-in metrics)
            if self.max_drawdown_dollars > starting_cash * 0.03:
                self._log(f"[EOA WARNING] Max drawdown ${self.max_drawdown_dollars:.2f} exceeded 3% of account")
            if self.worst_daily_loss > starting_cash * 0.02:
                self._log(f"[EOA WARNING] Worst daily loss ${self.worst_daily_loss:.2f} exceeded 2% of account")

            # Flush final day's rejections
            day_rejects = self.signal_engine.get_and_clear_reject_buffer()
            self._all_reject_rows.extend(day_rejects)

            # Filter rejection summary — compact single-line format for QC log
            rejects = self.signal_engine.get_reject_counts()
            candidates = self.signal_engine.get_breakout_candidates()
            self._log(
                f"[FILTER_SUMMARY] candidates={candidates} entries={len(self.trade_log_rows)} "
                f"spread_rejects={len(self._spread_rejected_today)} "
                f"| GAP_DIR={rejects.get('GAP_DIRECTION', 0)} EMA={rejects.get('EMA_ALIGN', 0)} "
                f"VWAP={rejects.get('VWAP', 0)} HC={rejects.get('HIGHER_CLOSE', 0)} "
                f"HO={rejects.get('HIGHER_OPEN', 0)} VR={rejects.get('VOLUME_RISING', 0)} "
                f"WICK={rejects.get('WICK', 0)} EW={rejects.get('ENTRY_WINDOW', 0)} "
                f"TIME={rejects.get('TIME_CUTOFF', 0)} ATR0={rejects.get('ATR_ZERO', 0)} "
                f"SG_GAMMA={rejects.get('SG_GAMMA_REGIME', 0)} SG_CONV={rejects.get('SG_CONVICTION', 0)} "
                f"SG_RANGE={rejects.get('SG_RANGE_VALIDATION', 0)} SG_OPEX={rejects.get('SG_OPEX', 0)}"
            )

            # Write trade log CSV to ObjectStore
            self._write_trade_log()

            # Write rejection detail CSV to ObjectStore
            self._write_reject_log()

            # Write runtime log to ObjectStore
            self._write_runtime_log()

            # Minimal QC terminal output (stays within daily quota)
            total_pnl = self.total_profit - self.total_loss_amt
            qc_pnl = self.portfolio.total_profit
            self._log(f"[SUMMARY] W:{self.total_wins} L:{self.total_losses} PnL:${total_pnl:.2f} QC_PnL:${qc_pnl:.2f}")
            self.log(
                f"[DONE] {len(self.trade_log_rows)} trades | W:{self.total_wins} L:{self.total_losses} "
                f"PnL:${total_pnl:.2f} QC:${qc_pnl:.2f} | DD:{self.max_drawdown_dollars:.2f} | "
                f"Files: trade_log.csv, reject_log.csv, runtime_log.txt in ObjectStore"
            )
        except Exception as e:
            self.log(f"[EOA ERROR] {str(e)}")

    def _write_trade_log(self):
        if not self.trade_log_rows:
            self._log("[TRADE_LOG] No trades to write")
            return

        header = ','.join(TRADE_LOG_COLUMNS)
        csv_content = header + '\n' + '\n'.join(self.trade_log_rows)

        timestamp = self.time.strftime("%Y%m%d_%H%M%S")
        key_versioned = f"trade_log_{timestamp}.csv"
        key_latest = "trade_log.csv"
        self.object_store.save(key_versioned, csv_content)
        self.object_store.save(key_latest, csv_content)
        self._log(f"[TRADE_LOG] {len(self.trade_log_rows)} trades → ObjectStore ({key_versioned})")

        # Compact summary
        total_pnl = self.total_profit - self.total_loss_amt
        self._log(f"[SUMMARY] W:{self.total_wins} L:{self.total_losses} PnL:${total_pnl:.2f}")

    def _write_reject_log(self):
        """Write signal rejection detail CSV to ObjectStore for offline analysis."""
        if not self._all_reject_rows:
            return

        header = "time,symbol,direction,reason,close,open,ema9,ema20,gap_pct"
        rows = [header]
        for r in self._all_reject_rows:
            rows.append(
                f"{r['time']},{r['symbol']},{r['direction']},{r['reason']},"
                f"{r['close']:.2f},{r['open']:.2f},{r['ema9']:.2f},{r['ema20']:.2f},"
                f"{r['gap_pct']*100:.2f}%"
            )
        csv_content = '\n'.join(rows)

        timestamp = self.time.strftime("%Y%m%d_%H%M%S")
        self.object_store.save(f"reject_log_{timestamp}.csv", csv_content)
        self.object_store.save("reject_log.csv", csv_content)
        self._log(f"[REJECT_LOG] {len(self._all_reject_rows)} rejections → ObjectStore")

    def _write_runtime_log(self):
        """Write full runtime log to ObjectStore as a text file."""
        if not self._log_buffer:
            return

        log_content = '\n'.join(self._log_buffer)

        timestamp = self.time.strftime("%Y%m%d_%H%M%S")
        self.object_store.save(f"runtime_log_{timestamp}.txt", log_content)
        self.object_store.save("runtime_log.txt", log_content)
