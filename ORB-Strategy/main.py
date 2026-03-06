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

        # Universe — hardcoded for Phase 1, Phase 2 will automate
        self.symbols = []
        tickers = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA",
                    "AMZN", "META", "GOOGL", "TSLA", "AMD"]
        for ticker in tickers:
            symbol = self.add_equity(ticker, Resolution.MINUTE).symbol
            self.symbols.append(symbol)
            self.indicators.register(symbol)

        # Variance max drawdown per symbol — placeholder defaults for Phase 1
        # Replace with actual variance backtest values per symbol
        self.max_dd = {s: -0.08 for s in self.symbols}

        # Daily reset schedule
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.at(9, 25),
            self.daily_reset
        )

    def daily_reset(self):
        self.risk_mgr.reset_daily()
        self.trade_mgr.reset()
        for symbol in self.symbols:
            self.orb.reset(symbol)

    def on_data(self, data):
        for symbol in self.symbols:
            if not data.bars.contains_key(symbol):
                continue

            bar = data.bars[symbol]

            # Build ORB range during 9:30–9:35
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

            # Check for new entries
            if not self.risk_mgr.can_trade():
                continue

            if self.signal_engine.check_long(symbol, bar):
                self.enter_long(symbol, bar.close)
            elif self.signal_engine.check_short(symbol, bar):
                self.enter_short(symbol, bar.close)

    def enter_long(self, symbol, price):
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        self.market_order(symbol, shares)
        self.trade_mgr.register_entry(symbol, price, is_long=True)
        self.risk_mgr.record_trade()
        self.bridge.send(str(symbol), "buy", shares)
        self.log(f"[LONG] {symbol} shares={shares} price={price:.2f}")

    def enter_short(self, symbol, price):
        shares = self.risk_mgr.calculate_shares(symbol, self.max_dd[symbol], price)
        if shares <= 0:
            return

        self.market_order(symbol, -shares)
        self.trade_mgr.register_entry(symbol, price, is_long=False)
        self.risk_mgr.record_trade()
        self.bridge.send(str(symbol), "sell_short", shares)
        self.log(f"[SHORT] {symbol} shares={shares} price={price:.2f}")

    def exit_position(self, symbol, price):
        is_long = self.trade_mgr.is_long(symbol)
        quantity = abs(self.portfolio[symbol].quantity)

        self.liquidate(symbol)
        self.trade_mgr.remove(symbol)

        action = "sell" if is_long else "buy_to_cover"
        self.bridge.send(str(symbol), action, quantity)
        self.log(f"[EXIT] {symbol} action={action} qty={quantity} price={price:.2f}")
