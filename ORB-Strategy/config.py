from AlgorithmImports import *


class Config:
    def __init__(self, algorithm=None):
        # Account
        self.ACCOUNT_SIZE = 25000
        self.BASE_DAILY_RISK = 500           # 2% of account

        # Regime multipliers
        self.REGIME_STRONG_UPTREND = 1.00
        self.REGIME_UPTREND = 0.90
        self.REGIME_UPTREND_PRESSURE = 0.50
        self.REGIME_DOWNTREND = 0.50
        self.REGIME_EXTREME_RISK_OFF = 0.25
        self.REGIME_CURRENT = 0.50           # UPDATE THIS DAILY based on Briefings.com

        # Optimizable parameters (QC get_parameter with defaults)
        orb_minutes = self._param(algorithm, "orb_minutes", 15)
        self.ORB_OPEN_TIME = time(9, 30)     # ET
        self.ORB_CLOSE_TIME = time(9, 30 + orb_minutes)  # ET — range locks after this
        self.BREAKOUT_OFFSET = self._param(algorithm, "breakout_offset", 0.05)

        # ATR trail tiers (inverted — tighter as profit grows)
        self.ATR_BASE_MULTIPLIER = self._param(algorithm, "atr_base_mult", 2.0)
        self.ATR_TIER1_MULTIPLIER = self._param(algorithm, "atr_tier1_mult", 0.75)
        self.ATR_TIER2_MULTIPLIER = self._param(algorithm, "atr_tier2_mult", 0.35)
        self.ATR_PROFIT_TIER1 = self._param(algorithm, "atr_profit_tier1", 3.0)
        self.ATR_PROFIT_TIER2 = self._param(algorithm, "atr_profit_tier2", 5.0)

        # Gap filter
        self.GAP_FILTER_PCT = self._param(algorithm, "gap_filter_pct", 0.02)

        # EMA periods
        self.EMA_FAST = 9
        self.EMA_MID = 20
        self.EMA_SLOW = 50

        # ATR period
        self.ATR_PERIOD = 14

        # Universe limits
        self.MAX_LONGS = 5
        self.MAX_SHORTS = 5

        # Daily trade limits (per direction)
        max_per_dir = self._param(algorithm, "max_trades_per_direction", 3)
        self.MAX_DAILY_LONGS = max_per_dir
        self.MAX_DAILY_SHORTS = max_per_dir
        self.MAX_DAILY_LOSSES_LONG = 2
        self.MAX_DAILY_LOSSES_SHORT = 2

        # Execution
        self.SS_ENABLED = False              # Set True for paper/live — False for backtest
        self.SS_PAPER_URL = ""               # SignalStack paper webhook URL
        self.SS_LIVE_URL = ""                # SignalStack live webhook URL

    @staticmethod
    def _param(algorithm, name, default):
        if algorithm is None:
            return default
        val = algorithm.get_parameter(name, default)
        return type(default)(val)
