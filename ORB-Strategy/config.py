from AlgorithmImports import *


class Config:
    # Account
    ACCOUNT_SIZE = 25000
    BASE_DAILY_RISK = 500           # 2% of account

    # Regime multipliers
    REGIME_STRONG_UPTREND = 1.00
    REGIME_UPTREND = 0.90
    REGIME_UPTREND_PRESSURE = 0.50
    REGIME_DOWNTREND = 0.50
    REGIME_EXTREME_RISK_OFF = 0.25
    REGIME_CURRENT = 0.50           # UPDATE THIS DAILY based on Briefings.com

    # ORB
    ORB_OPEN_TIME = time(9, 30)     # ET
    ORB_CLOSE_TIME = time(9, 35)    # ET — range locks after this bar closes

    # ATR trail tiers (inverted — tighter as profit grows)
    ATR_BASE_MULTIPLIER = 1.50
    ATR_TIER1_MULTIPLIER = 0.75     # Activate at profit_tier1 ATR
    ATR_TIER2_MULTIPLIER = 0.35     # Activate at profit_tier2 ATR
    ATR_PROFIT_TIER1 = 1.0          # ATRs of profit to activate tier1
    ATR_PROFIT_TIER2 = 2.0          # ATRs of profit to activate tier2

    # EMA periods
    EMA_FAST = 9
    EMA_MID = 20
    EMA_SLOW = 50

    # ATR period
    ATR_PERIOD = 14

    # Universe limits
    MAX_LONGS = 5
    MAX_SHORTS = 5

    # Daily trade limits
    MAX_DAILY_TRADES = 10

    # Execution
    SS_ENABLED = False              # Set True for paper/live — False for backtest
    SS_PAPER_URL = ""               # SignalStack paper webhook URL
    SS_LIVE_URL = ""                # SignalStack live webhook URL
