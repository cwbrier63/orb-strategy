from AlgorithmImports import *


class IndicatorManager:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
        self.vwap = {}
        self.ema_fast = {}
        self.ema_mid = {}
        self.ema_slow = {}
        self.atr = {}

    def register(self, symbol):
        self.vwap[symbol] = self.algo.vwap(symbol)
        self.ema_fast[symbol] = self.algo.ema(symbol, self.config.EMA_FAST)
        self.ema_mid[symbol] = self.algo.ema(symbol, self.config.EMA_MID)
        self.ema_slow[symbol] = self.algo.ema(symbol, self.config.EMA_SLOW)
        self.atr[symbol] = self.algo.atr(symbol, self.config.ATR_PERIOD)
        # Warm up indicators with historical data so they're ready immediately
        warmup = max(self.config.EMA_SLOW, self.config.ATR_PERIOD) + 5
        for ind in [self.ema_fast[symbol], self.ema_mid[symbol],
                    self.ema_slow[symbol], self.atr[symbol]]:
            self.algo.warm_up_indicator(symbol, ind, Resolution.DAILY)

    def is_ready(self, symbol):
        return (
            self.vwap[symbol].is_ready
            and self.ema_fast[symbol].is_ready
            and self.ema_mid[symbol].is_ready
            and self.ema_slow[symbol].is_ready
            and self.atr[symbol].is_ready
        )

    def get_vwap(self, symbol):
        return self.vwap[symbol].current.value

    def get_ema_fast(self, symbol):
        return self.ema_fast[symbol].current.value

    def get_ema_mid(self, symbol):
        return self.ema_mid[symbol].current.value

    def get_ema_slow(self, symbol):
        return self.ema_slow[symbol].current.value

    def get_atr(self, symbol):
        return self.atr[symbol].current.value
