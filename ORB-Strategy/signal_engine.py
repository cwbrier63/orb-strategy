from AlgorithmImports import *


class SignalEngine:
    def __init__(self, algorithm, config, orb_calculator, indicator_manager):
        self.algo = algorithm
        self.config = config
        self.orb = orb_calculator
        self.indicators = indicator_manager

    def check_long(self, symbol, bar):
        if not self.orb.is_locked(symbol):
            return False

        if not self.indicators.is_ready(symbol):
            return False

        orb_high = self.orb.get_high(symbol)
        if orb_high is None:
            return False

        # 1. Price breaks above ORB high on completed 1m bar close
        if bar.close <= orb_high:
            return False

        # 2. Close > VWAP
        if bar.close <= self.indicators.get_vwap(symbol):
            return False

        # 3. EMA9 > EMA20 (momentum confirmation)
        if self.indicators.get_ema_fast(symbol) <= self.indicators.get_ema_mid(symbol):
            return False

        # 4. ATR > 0 (indicator is ready)
        if self.indicators.get_atr(symbol) <= 0:
            return False

        # 7. Current time < 3:30 PM ET (no new entries in last 30 min)
        if self.algo.time.time() >= time(15, 30):
            return False

        return True

    def check_short(self, symbol, bar):
        if not self.orb.is_locked(symbol):
            return False

        if not self.indicators.is_ready(symbol):
            return False

        orb_low = self.orb.get_low(symbol)
        if orb_low is None:
            return False

        # 1. Price breaks below ORB low on completed 1m bar close
        if bar.close >= orb_low:
            return False

        # 2. Close < VWAP
        if bar.close >= self.indicators.get_vwap(symbol):
            return False

        # 3. EMA9 < EMA20
        if self.indicators.get_ema_fast(symbol) >= self.indicators.get_ema_mid(symbol):
            return False

        # 4. ATR > 0 (indicator is ready)
        if self.indicators.get_atr(symbol) <= 0:
            return False

        # 7. Current time < 3:30 PM ET
        if self.algo.time.time() >= time(15, 30):
            return False

        return True
