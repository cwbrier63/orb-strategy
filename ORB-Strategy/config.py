from AlgorithmImports import *


class Config:
    # Account
    ACCOUNT_SIZE = 25000
    BASE_DAILY_RISK = 500           # 2% of account
    MAX_TOTAL_ALLOCATED = 20000     # Capital allocation guard — max dollars across all open positions

    # Regime multipliers
    REGIME_STRONG_UPTREND = 1.00
    REGIME_UPTREND = 0.90
    REGIME_UPTREND_PRESSURE = 0.50
    REGIME_DOWNTREND = 0.50
    REGIME_EXTREME_RISK_OFF = 0.25
    REGIME_CURRENT = 0.50           # UPDATE THIS DAILY based on Briefings.com

    # ORB — separate per direction
    ORB_OPEN_TIME = time(9, 30)     # ET

    # Long parameters
    LONG_ORB_MINUTES = 15
    LONG_ORB_CLOSE_TIME = time(9, 45)
    LONG_BREAKOUT_OFFSET = 0.05
    LONG_ATR_BASE_MULTIPLIER = 2.00
    LONG_ATR_TIER1_MULTIPLIER = 0.75
    LONG_ATR_TIER2_MULTIPLIER = 0.35
    LONG_ATR_PROFIT_TIER1 = 3.0
    LONG_ATR_PROFIT_TIER2 = 5.0

    # Short parameters
    SHORT_ORB_MINUTES = 15
    SHORT_ORB_CLOSE_TIME = time(9, 45)
    SHORT_BREAKOUT_OFFSET = 0.05
    SHORT_ATR_BASE_MULTIPLIER = 2.00
    SHORT_ATR_TIER1_MULTIPLIER = 0.75
    SHORT_ATR_TIER2_MULTIPLIER = 0.35
    SHORT_ATR_PROFIT_TIER1 = 3.0
    SHORT_ATR_PROFIT_TIER2 = 5.0

    # Gap filter
    GAP_FILTER_PCT = 0.02

    # EMA periods
    EMA_FAST = 9
    EMA_MID = 20
    EMA_SLOW = 50

    # ATR period
    ATR_PERIOD = 14

    # Universe limits
    MAX_LONGS = 5
    MAX_SHORTS = 5

    # Daily trade limits (per direction)
    MAX_DAILY_LONGS = 3
    MAX_DAILY_SHORTS = 3
    MAX_DAILY_LOSSES_LONG = 2
    MAX_DAILY_LOSSES_SHORT = 2

    # Execution
    SS_ENABLED = False              # Set True for paper/live — False for backtest
    SS_PAPER_URL = ""               # SignalStack paper webhook URL
    SS_LIVE_URL = ""                # SignalStack live webhook URL
