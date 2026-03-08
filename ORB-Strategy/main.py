from AlgorithmImports import *
from config import OrbConfig
from orb_calculator import OrbCalculator
from indicators import IndicatorManager
from signal_engine import SignalEngine
from trade_manager import TradeManager, TRADE_LOG_COLUMNS
from risk_manager import RiskManager
from signalstack_bridge import SignalStackBridge


class OrbAlgorithm(QCAlgorithm):
    def initialize(self):
        self.config = OrbConfig()
        self._apply_parameters()

        self.set_start_date(2025, 1, 1)
        self.set_end_date(2025, 6, 30)
        self.set_cash(self.config.ACCOUNT_SIZE)

        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        # Modules
        self.orb = OrbCalculator(self, self.config)
        self.indicators = IndicatorManager(self, self.config)
        self.signal_engine = SignalEngine(self, self.config, self.orb, self.indicators)
        self.trade_mgr = TradeManager(self, self.config)
        self.risk_mgr = RiskManager(self, self.config)
        self.bridge = SignalStackBridge(self, self.config)

        # Tagged universe — symbols flagged LONG or SHORT based on gap direction
        # Direction is determined at open each day in daily_reset()
        universe = {
            "TSLA": -0.08,
        }

        self.symbols = []
        self.max_dd = {}
        for ticker, dd in universe.items():
            symbol = self.add_equity(ticker, Resolution.MINUTE).symbol
            self.symbols.append(symbol)
            self.indicators.register(symbol)
            self.max_dd[symbol] = dd

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

        # Log CSV header for log extraction
        self.log(f"[TRADE_LOG_HEADER] {','.join(TRADE_LOG_COLUMNS)}")

        # Daily reset schedule
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(9, 25),
            self.daily_reset
        )

        # EOD close — flatten all positions at 3:55 PM ET
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(15, 55),
            self.eod_close
        )

    def _apply_parameters(self):
        """Override config defaults with QC optimization parameters if provided."""
        # Long direction parameters
        p = self.get_parameter("long_orb_minutes")
        if p is not None:
            self.config.LONG_ORB_MINUTES = int(p)
            base = datetime(2000, 1, 1, 9, 30)
            self.config.LONG_ORB_CLOSE_TIME = (base + timedelta(minutes=self.config.LONG_ORB_MINUTES)).time()

        p = self.get_parameter("long_atr_base_mult")
        if p is not None:
            self.config.LONG_ATR_BASE_MULTIPLIER = float(p)

        p = self.get_parameter("long_atr_tier1_mult")
        if p is not None:
            self.config.LONG_ATR_TIER1_MULTIPLIER = float(p)

        p = self.get_parameter("long_atr_tier2_mult")
        if p is not None:
            self.config.LONG_ATR_TIER2_MULTIPLIER = float(p)

        p = self.get_parameter("long_atr_profit_tier1")
        if p is not None:
            self.config.LONG_ATR_PROFIT_TIER1 = float(p)

        p = self.get_parameter("long_atr_profit_tier2")
        if p is not None:
            self.config.LONG_ATR_PROFIT_TIER2 = float(p)

        p = self.get_parameter("long_breakout_offset")
        if p is not None:
            self.config.LONG_BREAKOUT_OFFSET = float(p)

        # Short direction parameters
        p = self.get_parameter("short_orb_minutes")
        if p is not None:
            self.config.SHORT_ORB_MINUTES = int(p)
            base = datetime(2000, 1, 1, 9, 30)
            self.config.SHORT_ORB_CLOSE_TIME = (base + timedelta(minutes=self.config.SHORT_ORB_MINUTES)).time()

        p = self.get_parameter("short_atr_base_mult")
        if p is not None:
            self.config.SHORT_ATR_BASE_MULTIPLIER = float(p)

        p = self.get_parameter("short_atr_tier1_mult")
        if p is not None:
            self.config.SHORT_ATR_TIER1_MULTIPLIER = float(p)

        p = self.get_parameter("short_atr_tier2_mult")
        if p is not None:
            self.config.SHORT_ATR_TIER2_MULTIPLIER = float(p)

        p = self.get_parameter("short_atr_profit_tier1")
        if p is not None:
            self.config.SHORT_ATR_PROFIT_TIER1 = float(p)

        p = self.get_parameter("short_atr_profit_tier2")
        if p is not None:
            self.config.SHORT_ATR_PROFIT_TIER2 = float(p)

        p = self.get_parameter("short_breakout_offset")
        if p is not None:
            self.config.SHORT_BREAKOUT_OFFSET = float(p)

        # Hard stop parameters
        p = self.get_parameter("long_hard_stop_pct")
        if p is not None:
            self.config.LONG_HARD_STOP_PCT = float(p)

        p = self.get_parameter("short_hard_stop_pct")
        if p is not None:
            self.config.SHORT_HARD_STOP_PCT = float(p)

        # Shared parameters
        p = self.get_parameter("gap_filter_pct")
        if p is not None:
            self.config.GAP_FILTER_PCT = float(p)

        p = self.get_parameter("max_trades_per_direction")
        if p is not None:
            self.config.MAX_DAILY_LONGS = int(p)
            self.config.MAX_DAILY_SHORTS = int(p)

        # Live override: clear a symbol from QC internal state
        p = self.get_parameter("clear_symbol")
        if p is not None and p != "":
            self.log(f"[CLEAR_SYMBOL] Wiping QC state for {p}")
            clear_sym = self.add_equity(p, Resolution.MINUTE).symbol
            if self.portfolio[clear_sym].invested:
                self.liquidate(clear_sym)

    def eod_close(self):
        for symbol in self.symbols:
            if self.portfolio[symbol].invested:
                price = self.securities[symbol].price
                self.exit_position(symbol, price, "EOD")
        self.log("[EOD CLOSE] All positions flattened")

    def daily_reset(self):
        self.risk_mgr.reset_daily()
        self.trade_mgr.reset()
        self.signal_engine.reset_daily()
        self.daily_halt = False
        self.daily_warning_fired = False
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
        """Tag symbol as LONG or SHORT based on gap direction at open."""
        if self.config.FORCE_DIRECTION == 1:
            self.symbol_direction[symbol] = "LONG"
            self.gap_qualified[symbol] = True
            self.log(f"[FORCE_DIRECTION] {symbol} forced to LONG")
            return True
        elif self.config.FORCE_DIRECTION == -1:
            self.symbol_direction[symbol] = "SHORT"
            self.gap_qualified[symbol] = True
            self.log(f"[FORCE_DIRECTION] {symbol} forced to SHORT")
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
            self.log(f"[DAILY WARNING] Loss ${daily_loss:.2f} approaching 2% limit")
            self.daily_warning_fired = True

        if not self.daily_halt and daily_loss >= starting_cash * 0.02:
            self.log(f"[DAILY HALT] Loss ${daily_loss:.2f} hit 2% limit — liquidating all")
            self.liquidate()
            self.daily_halt = True

    def on_data(self, data):
        try:
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

                # Only trade the tagged direction for this symbol
                if direction == "LONG":
                    if self.risk_mgr.can_trade_long() and self.signal_engine.check_long(symbol, bar):
                        self.enter_long(symbol, bar, is_long=True)
                elif direction == "SHORT":
                    if self.risk_mgr.can_trade_short() and self.signal_engine.check_short(symbol, bar):
                        self.enter_short(symbol, bar, is_long=False)
        except Exception as e:
            self.log(f"[ON_DATA ERROR] {str(e)}")

    def _build_entry_snapshot(self, symbol):
        """Capture indicator values and config state at entry time."""
        prior = self.prior_close.get(symbol, 0)
        today_open = self.securities[symbol].open
        gap_pct = (today_open - prior) / prior if prior > 0 else 0
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
        }

    def enter_long(self, symbol, bar, is_long=True):
        price = bar.close
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        # Capital allocation guard
        if not self.risk_mgr.check_allocation(shares, price):
            self.log(f"[ALLOC BLOCKED] {symbol} — ${shares * price:.0f} would exceed limit")
            return

        atr = self.indicators.get_atr(symbol)
        orb_range = self.orb.get_range(symbol)
        snapshot = self._build_entry_snapshot(symbol)
        filter_evals = self.signal_engine.evaluate_filters_at_entry(symbol, bar, is_long=True)
        self.market_order(symbol, shares)
        self.trade_mgr.register_entry(symbol, price, is_long=True, atr=atr, orb_range=orb_range)
        self.trade_id += 1
        self.trade_mgr.create_record(symbol, self.trade_id, shares, snapshot, self.config, filter_evals)
        self.risk_mgr.record_long()
        self.risk_mgr.add_allocation(shares, price)
        self.bridge.send(str(symbol), "buy", shares)
        self.log(f"[LONG] {symbol} shares={shares} price={price:.2f}")

    def enter_short(self, symbol, bar, is_long=False):
        price = bar.close
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        # Capital allocation guard
        if not self.risk_mgr.check_allocation(shares, price):
            self.log(f"[ALLOC BLOCKED] {symbol} — ${shares * price:.0f} would exceed limit")
            return

        atr = self.indicators.get_atr(symbol)
        orb_range = self.orb.get_range(symbol)
        snapshot = self._build_entry_snapshot(symbol)
        filter_evals = self.signal_engine.evaluate_filters_at_entry(symbol, bar, is_long=False)
        self.market_order(symbol, -shares)
        self.trade_mgr.register_entry(symbol, price, is_long=False, atr=atr, orb_range=orb_range)
        self.trade_id += 1
        self.trade_mgr.create_record(symbol, self.trade_id, shares, snapshot, self.config, filter_evals)
        self.risk_mgr.record_short()
        self.risk_mgr.add_allocation(shares, price)
        self.bridge.send(str(symbol), "sell_short", shares)
        self.log(f"[SHORT] {symbol} shares={shares} price={price:.2f}")

    def exit_position(self, symbol, price, reason=""):
        # Portfolio invested guard — don't liquidate already-closed positions
        if not self.portfolio[symbol].invested:
            self.log(f"[EXIT SKIP] {symbol} — not invested, clearing internal state only")
            self.trade_mgr.remove(symbol)
            return

        is_long = self.trade_mgr.is_long(symbol)
        entry_price = self.trade_mgr.entries[symbol]["price"]
        quantity = abs(self.portfolio[symbol].quantity)

        # Track wins/losses for optimization scoring
        if is_long:
            pnl = (price - entry_price) * quantity
        else:
            pnl = (entry_price - price) * quantity

        if pnl > 0:
            self.total_wins += 1
            self.total_profit += pnl
        else:
            self.total_losses += 1
            self.total_loss_amt += abs(pnl)

        # Track losses per direction
        if is_long and price < entry_price:
            self.risk_mgr.record_loss(is_long=True)
        elif not is_long and price > entry_price:
            self.risk_mgr.record_loss(is_long=False)

        # Finalize trade record and log it
        record = self.trade_mgr.finalize_record(symbol, price, self.time, pnl, quantity, reason)
        if record:
            row = TradeManager.format_record_row(record)
            self.log(f"[TRADE_LOG] {row}")
            self.trade_log_rows.append(row)

        # Release capital allocation
        self.risk_mgr.remove_allocation(quantity, entry_price)

        self.liquidate(symbol)
        self.trade_mgr.remove(symbol)

        action = "sell" if is_long else "buy_to_cover"
        self.bridge.send(str(symbol), action, quantity)
        self.log(f"[EXIT] {symbol} reason={reason} action={action} qty={quantity} price={price:.2f} pnl={pnl:.2f}")

    def on_end_of_algorithm(self):
        try:
            starting_cash = self.config.ACCOUNT_SIZE

            # Hard disqualifiers — log warnings only (optimizer uses QC built-in metrics)
            if self.max_drawdown_dollars > starting_cash * 0.03:
                self.log(f"[EOA WARNING] Max drawdown ${self.max_drawdown_dollars:.2f} exceeded 3% of account")
            if self.worst_daily_loss > starting_cash * 0.02:
                self.log(f"[EOA WARNING] Worst daily loss ${self.worst_daily_loss:.2f} exceeded 2% of account")

            # Filter rejection summary (trade-level counts: one per symbol/reason/day)
            rejects = self.signal_engine.get_reject_counts()
            candidates = self.signal_engine.get_breakout_candidates()
            self.log(f"[FILTER_SUMMARY] BREAKOUT_CANDIDATES={candidates}")
            self.log(f"[FILTER_SUMMARY] TOTAL_ENTRIES={len(self.trade_log_rows)}")
            self.log(f"[FILTER_SUMMARY] GAP_DIRECTION_REJECTS={rejects.get('GAP_DIRECTION', 0)}")
            self.log(f"[FILTER_SUMMARY] EMA_ALIGN_REJECTS={rejects.get('EMA_ALIGN', 0)}")
            self.log(f"[FILTER_SUMMARY] VWAP_REJECTS={rejects.get('VWAP', 0)}")
            self.log(f"[FILTER_SUMMARY] HIGHER_CLOSE_REJECTS={rejects.get('HIGHER_CLOSE', 0)}")
            self.log(f"[FILTER_SUMMARY] HIGHER_OPEN_REJECTS={rejects.get('HIGHER_OPEN', 0)}")
            self.log(f"[FILTER_SUMMARY] VOLUME_RISING_REJECTS={rejects.get('VOLUME_RISING', 0)}")
            self.log(f"[FILTER_SUMMARY] MAX_WICK_REJECTS={rejects.get('WICK', 0)}")
            self.log(f"[FILTER_SUMMARY] ENTRY_WINDOW_REJECTS={rejects.get('ENTRY_WINDOW', 0)}")
            self.log(f"[FILTER_SUMMARY] TIME_CUTOFF_REJECTS={rejects.get('TIME_CUTOFF', 0)}")
            self.log(f"[FILTER_SUMMARY] ATR_ZERO_REJECTS={rejects.get('ATR_ZERO', 0)}")

            # Write trade log CSV to ObjectStore
            self._write_trade_log()
        except Exception as e:
            self.log(f"[EOA ERROR] {str(e)}")

    def _write_trade_log(self):
        if not self.trade_log_rows:
            self.log("[TRADE_LOG] No trades to write")
            return

        header = ','.join(TRADE_LOG_COLUMNS)
        csv_content = header + '\n' + '\n'.join(self.trade_log_rows)

        timestamp = self.time.strftime("%Y%m%d_%H%M%S")
        key_versioned = f"trade_log_{timestamp}.csv"
        key_latest = "trade_log.csv"
        self.object_store.save(key_versioned, csv_content)
        self.object_store.save(key_latest, csv_content)
        self.log(f"[TRADE_LOG] Wrote {len(self.trade_log_rows)} trades to ObjectStore: {key_versioned} + {key_latest}")

        # Log summary
        self.log(f"[TRADE_LOG SUMMARY] {len(self.trade_log_rows)} trades | W:{self.total_wins} L:{self.total_losses}")
