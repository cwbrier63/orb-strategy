from AlgorithmImports import *
from config import Config
from orb_calculator import OrbCalculator
from indicators import IndicatorManager
from signal_engine import SignalEngine
from trade_manager import TradeManager
from risk_manager import RiskManager
from signalstack_bridge import SignalStackBridge


class OrbAlgorithm(QCAlgorithm):
    def initialize(self):
        self.config = Config()
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
            "IREN": -0.082,
            "DKNG": -0.071,
            "ZETA": -0.065,
            "TTD":  -0.058,
            "MOS":  -0.045,
            "DOW":  -0.091,
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

        # Daily reset schedule
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(9, 25),
            self.daily_reset
        )

    def _apply_parameters(self):
        """Override config defaults with QC optimization parameters if provided."""
        # Long direction parameters
        p = self.get_parameter("long_orb_minutes")
        if p is not None:
            self.config.LONG_ORB_MINUTES = int(p)
            self.config.LONG_ORB_CLOSE_TIME = time(9, 30 + self.config.LONG_ORB_MINUTES)

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
            self.config.SHORT_ORB_CLOSE_TIME = time(9, 30 + self.config.SHORT_ORB_MINUTES)

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

    def daily_reset(self):
        self.risk_mgr.reset_daily()
        self.trade_mgr.reset()
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
        self.check_daily_pnl()

        if self.daily_halt:
            return

        for symbol in self.symbols:
            if not data.bars.contains_key(symbol):
                continue

            bar = data.bars[symbol]

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
                self.trade_mgr.update_trail(symbol, bar.close, atr)

                if self.trade_mgr.check_stop(symbol, bar.close):
                    self.exit_position(symbol, bar.close)
                continue

            # Tag direction on first bar after ORB lock if not yet tagged
            if not self.gap_qualified.get(symbol, False):
                if not self._tag_direction(symbol):
                    continue

            direction = self.symbol_direction.get(symbol)
            if direction is None:
                continue

            # Only trade the tagged direction for this symbol
            if direction == "LONG":
                if self.risk_mgr.can_trade_long() and self.signal_engine.check_long(symbol, bar):
                    self.enter_long(symbol, bar.close)
            elif direction == "SHORT":
                if self.risk_mgr.can_trade_short() and self.signal_engine.check_short(symbol, bar):
                    self.enter_short(symbol, bar.close)

    def enter_long(self, symbol, price):
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        # Capital allocation guard
        if not self.risk_mgr.check_allocation(shares, price):
            self.log(f"[ALLOC BLOCKED] {symbol} — ${shares * price:.0f} would exceed limit")
            return

        self.market_order(symbol, shares)
        self.trade_mgr.register_entry(symbol, price, is_long=True)
        self.risk_mgr.record_long()
        self.risk_mgr.add_allocation(shares, price)
        self.bridge.send(str(symbol), "buy", shares)
        self.log(f"[LONG] {symbol} shares={shares} price={price:.2f}")

    def enter_short(self, symbol, price):
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        # Capital allocation guard
        if not self.risk_mgr.check_allocation(shares, price):
            self.log(f"[ALLOC BLOCKED] {symbol} — ${shares * price:.0f} would exceed limit")
            return

        self.market_order(symbol, -shares)
        self.trade_mgr.register_entry(symbol, price, is_long=False)
        self.risk_mgr.record_short()
        self.risk_mgr.add_allocation(shares, price)
        self.bridge.send(str(symbol), "sell_short", shares)
        self.log(f"[SHORT] {symbol} shares={shares} price={price:.2f}")

    def exit_position(self, symbol, price):
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

        # Release capital allocation
        self.risk_mgr.remove_allocation(quantity, entry_price)

        self.liquidate(symbol)
        self.trade_mgr.remove(symbol)

        action = "sell" if is_long else "buy_to_cover"
        self.bridge.send(str(symbol), action, quantity)
        self.log(f"[EXIT] {symbol} action={action} qty={quantity} price={price:.2f} pnl={pnl:.2f}")

    def on_end_of_algorithm(self):
        starting_cash = self.config.ACCOUNT_SIZE
        net_profit = self.portfolio.total_portfolio_value - starting_cash

        # Hard disqualifiers
        if self.max_drawdown_dollars > starting_cash * 0.03:
            self.log("SCORE:-999.0000")
            return
        if self.worst_daily_loss > starting_cash * 0.02:
            self.log("SCORE:-999.0000")
            return
        if net_profit < 0:
            self.log("SCORE:-999.0000")
            return

        # Composite score: expectancy × win_rate
        total_trades = self.total_wins + self.total_losses
        if total_trades == 0:
            self.log("SCORE:-999.0000")
            return

        win_rate = self.total_wins / total_trades
        avg_win = self.total_profit / self.total_wins if self.total_wins > 0 else 0
        avg_loss = self.total_loss_amt / self.total_losses if self.total_losses > 0 else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        score = expectancy * win_rate

        self.log(f"SCORE:{score:.4f}")
