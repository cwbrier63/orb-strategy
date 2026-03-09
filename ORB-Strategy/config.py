from AlgorithmImports import *


class OrbConfig:
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
    LONG_ATR_BASE_MULTIPLIER = 2.50
    LONG_ATR_TIER1_MULTIPLIER = 0.75
    LONG_ATR_TIER2_MULTIPLIER = 0.35
    LONG_ATR_PROFIT_TIER1 = 3.0
    LONG_ATR_PROFIT_TIER2 = 5.0
    LONG_HARD_STOP_PCT = 0.01
    LONG_ATR_ACTIVATION_PCT = 75    # Trail doesn't start until profit >= X% of ATR
    # Long take profit (R-multiples of ORB range, 0 = level disabled)
    LONG_R_TP1 = 0.5
    LONG_R_TP2 = 1.0
    LONG_R_TP3 = 2.0

    # Short parameters
    SHORT_ORB_MINUTES = 15
    SHORT_ORB_CLOSE_TIME = time(9, 45)
    SHORT_BREAKOUT_OFFSET = 0.05
    SHORT_ATR_BASE_MULTIPLIER = 2.50
    SHORT_ATR_TIER1_MULTIPLIER = 0.75
    SHORT_ATR_TIER2_MULTIPLIER = 0.35
    SHORT_ATR_PROFIT_TIER1 = 3.0
    SHORT_ATR_PROFIT_TIER2 = 5.0
    SHORT_HARD_STOP_PCT = 0.01
    SHORT_ATR_ACTIVATION_PCT = 75   # Trail doesn't start until profit >= X% of ATR
    # Short take profit (R-multiples of ORB range, 0 = level disabled)
    SHORT_R_TP1 = 0.5
    SHORT_R_TP2 = 1.0
    SHORT_R_TP3 = 2.0

    # Take profit master toggle
    USE_TAKE_PROFIT = False         # True = exit partial shares at R levels; False = trail only

    # EMA cross exit
    EMA_CROSS_EXIT = False          # Exit when EMA9 crosses EMA20 against position

    # VWAP recross exit
    USE_VWAP_RECROSS_EXIT = True    # Exit when price touches/crosses VWAP against position
    VWAP_RECROSS_MIN_BARS = 1       # Consecutive bars price must stay wrong side of VWAP to trigger exit

    # Direction override
    FORCE_DIRECTION = 0             # 1 = force LONG, -1 = force SHORT, 0 = normal gap tagging

    # Gap filter
    GAP_FILTER_PCT = 0.02
    USE_GAP_DIRECTION_GATE = True   # Reject longs on large gap-down, shorts on large gap-up
    GAP_REJECT_THRESHOLD = 0.03     # Reject if gap magnitude > 3% against forced direction

    # EMA periods
    EMA_FAST = 9
    EMA_MID = 20
    EMA_SLOW = 50

    # ATR period
    ATR_PERIOD = 14

    # Universe limits
    MAX_LONGS = 5
    MAX_SHORTS = 5

    # Per-symbol daily limits (how many times one symbol can re-enter per day)
    MAX_DAILY_LONGS = 3             # max long entries per symbol per day
    MAX_DAILY_SHORTS = 3            # max short entries per symbol per day
    MAX_DAILY_LOSSES_LONG = 2       # max long losses per symbol per day
    MAX_DAILY_LOSSES_SHORT = 2      # max short losses per symbol per day

    # Global daily limits (total entries across all symbols per day)
    MAX_DAILY_TOTAL_LONGS = 6       # max total long entries per day
    MAX_DAILY_TOTAL_SHORTS = 6      # max total short entries per day
    MAX_DAILY_TOTAL_LOSSES = 4      # max total losses (both directions) per day — circuit breaker

    # ── Entry filters — direction-specific ──────────────────────────
    # Long filters (Jun 2025 optimization: EMA hurts, HC+HO+VR+MW synergistic)
    LONG_REQUIRE_EMA_ALIGN = False      # net-negative for longs (Sharpe 0.95→5.09 when OFF)
    LONG_REQUIRE_VWAP = True            # zero effect (all longs already > VWAP) — keep as safety
    LONG_REQUIRE_HIGHER_CLOSE = True    # +synergy with HO+VR+MW (Sharpe 5.09 best combo)
    LONG_REQUIRE_HIGHER_OPEN = True     # +synergy with HC+VR+MW (Sharpe 5.09 best combo)
    LONG_REQUIRE_VOLUME_RISING = True   # +synergy with HC+HO+MW (Sharpe 5.09, PSR 97.6%)
    LONG_REQUIRE_MAX_WICK = True        # +synergy with HC+HO+VR (Sharpe 5.09, DD 1.2%)
    LONG_REQUIRE_ENTRY_WINDOW = False   # zero/negative effect for longs

    # Short filters (H1 2025 attribution: higher_close, wick, volume all positive)
    SHORT_REQUIRE_EMA_ALIGN = False
    SHORT_REQUIRE_VWAP = True
    SHORT_REQUIRE_HIGHER_CLOSE = True   # +$243 for shorts, blocks 40 losers at 30% WR
    SHORT_REQUIRE_HIGHER_OPEN = True    # +edge for shorts per optimization
    SHORT_REQUIRE_VOLUME_RISING = False # net-negative per optimization (0/64 profitable when ON)
    SHORT_REQUIRE_MAX_WICK = True       # +$203 for shorts, blocks 68 losers at 39.7% WR
    SHORT_REQUIRE_ENTRY_WINDOW = False  # no effect

    # Spread filter (percentage of mid-price)
    MAX_SPREAD_PCT = 0.10           # Max bid-ask spread as % of mid-price (0.10 = 0.10%)

    # Shared filter parameters
    MAX_WICK_PCT = 50               # Max wick as % of body size (50 = wick can't exceed body)
    ENTRY_WINDOW_BARS = 1           # Must enter within N bars of breakout detection

    # Universe source — published Google Sheets CSV URL (empty = use FORCE_DIRECTION fallback)
    UNIVERSE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKo9MtuEQI5a7pAxYuhbNoPX0IGtVQk347mBTNLsRWVt9FajGXqy0JYKgznqSb_w/pub?gid=1095632619&single=true&output=csv"

    # Watchlist — published CSV URL of Watchlist tab (broad scanning pool for gap scanner)
    WATCHLIST_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKo9MtuEQI5a7pAxYuhbNoPX0IGtVQk347mBTNLsRWVt9FajGXqy0JYKgznqSb_w/pub?gid=897666895&single=true&output=csv"

    # Auto universe — Trade-Ideas exact replication
    USE_AUTO_UNIVERSE = True
    AUTO_MIN_PRICE = 5.0                # price >= $5
    AUTO_MIN_ADV = 2_000_000            # avg daily volume >= 2M shares
    AUTO_MIN_TODAY_VOLUME = 100_000     # today's volume >= 100K
    AUTO_MIN_ATR = 1.0                  # ATR14 >= $1
    AUTO_GAP_PCT = 0.02                 # gap >= 2% (both directions)
    AUTO_MAX_GAP_PCT = 0.10             # cap at 10% — exclude binary event runaway gaps
    AUTO_MAX_SHORT_FLOAT = 0.20         # short float <= 20%
    AUTO_MIN_FLOAT_SHARES = 1_000_000   # float >= 1M shares
    AUTO_REQUIRE_EPS = True             # must have reported EPS != 0
    AUTO_MIN_MARKET_CAP = 5_000_000     # market cap >= $5M
    AUTO_NO_EARNINGS_TODAY = True       # exclude same-day earnings
    AUTO_MAX_PRICE = 200.0              # price <= $200 — exclude mega-priced stocks
    AUTO_MAX_SYMBOLS = 10               # cap universe per day

    # Execution
    SS_ENABLED = False              # Set True for paper/live — False for backtest
    SS_PAPER_URL = "https://app.signalstack.com/hook/w3rWj74GcoTYh8MF8FoCxR"
    SS_LIVE_URL = ""                # SignalStack live webhook URL
