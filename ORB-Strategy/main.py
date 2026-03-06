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
        self.config = Config(self)

        self.set_start_date(2025, 1, 1)
        self.set_end_date(2025, 12, 31)
        self.set_cash(self.config.ACCOUNT_SIZE)

        self.set_brokerage_model(BrokerageName.INTERACTIVE_BROKERS_BROKERAGE, AccountType.MARGIN)

        # Modules
        self.orb = OrbCalculator(self, self.config)
        self.indicators = IndicatorManager(self, self.config)
        self.signal_engine = SignalEngine(self, self.config, self.orb, self.indicators)
        self.trade_mgr = TradeManager(self, self.config)
        self.risk_mgr = RiskManager(self, self.config)
        self.bridge = SignalStackBridge(self, self.config)

        # Universe — March 6 variance backtest symbols and max drawdowns
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

        # Gap filter: cache prior close per symbol each morning
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

    def daily_reset(self):
        self.risk_mgr.reset_daily()
        self.trade_mgr.reset()
        self.daily_halt = False
        self.daily_warning_fired = False
        self.day_start_equity = self.portfolio.total_portfolio_value
        for symbol in self.symbols:
            self.orb.reset(symbol)
            self.gap_qualified[symbol] = False

            # Get prior daily close for gap filter
            hist = self.history(symbol, 2, Resolution.DAILY)
            if hist.empty or len(hist) < 1:
                continue
            self.prior_close[symbol] = hist["close"].iloc[-1]

    def check_daily_pnl(self):
        current_equity = self.portfolio.total_portfolio_value
        daily_loss = self.day_start_equity - current_equity
        starting_cash = self.config.ACCOUNT_SIZE

        # Track worst daily loss across entire backtest
        if daily_loss > self.worst_daily_loss:
            self.worst_daily_loss = daily_loss

        # Track max drawdown from peak
        peak = max(self.day_start_equity, current_equity)
        dd = peak - current_equity
        if dd > self.max_drawdown_dollars:
            self.max_drawdown_dollars = dd

        # Early warning at 1.8% of starting cash
        if not self.daily_warning_fired and daily_loss >= starting_cash * 0.018:
            self.log(f"[DAILY WARNING] Loss ${daily_loss:.2f} approaching 2% limit")
            self.daily_warning_fired = True

        # Hard halt at 2% of starting cash — liquidate everything
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

            # Gap filter: today's open must be ≥ gap_filter_pct away from prior close
            if not self.gap_qualified.get(symbol, False):
                prior = self.prior_close.get(symbol)
                if prior is None or prior == 0:
                    continue
                today_open = self.securities[symbol].open
                if today_open == 0:
                    continue
                gap_pct = abs(today_open - prior) / prior
                if gap_pct < self.config.GAP_FILTER_PCT:
                    continue
                self.gap_qualified[symbol] = True

            # Check for new entries (per-direction limits)
            if self.risk_mgr.can_trade_long() and self.signal_engine.check_long(symbol, bar):
                self.enter_long(symbol, bar.close)
            elif self.risk_mgr.can_trade_short() and self.signal_engine.check_short(symbol, bar):
                self.enter_short(symbol, bar.close)

    def enter_long(self, symbol, price):
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        self.market_order(symbol, shares)
        self.trade_mgr.register_entry(symbol, price, is_long=True)
        self.risk_mgr.record_long()
        self.bridge.send(str(symbol), "buy", shares)
        self.log(f"[LONG] {symbol} shares={shares} price={price:.2f}")

    def enter_short(self, symbol, price):
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        self.market_order(symbol, -shares)
        self.trade_mgr.register_entry(symbol, price, is_long=False)
        self.risk_mgr.record_short()
        self.bridge.send(str(symbol), "sell_short", shares)
        self.log(f"[SHORT] {symbol} shares={shares} price={price:.2f}")

    def exit_position(self, symbol, price):
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
