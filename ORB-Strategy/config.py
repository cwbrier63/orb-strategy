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
    LONG_ATR_BASE_MULTIPLIER = 2.00      # was 3.50 — tighter trail captures medium moves
    LONG_ATR_TIER1_MULTIPLIER = 0.75     # was 1.00 — lock in more at tier1
    LONG_ATR_TIER2_MULTIPLIER = 0.35
    LONG_ATR_PROFIT_TIER1 = 1.5          # was 3.0 — tier1 kicks in sooner
    LONG_ATR_PROFIT_TIER2 = 3.0          # was 5.0 — tier2 reachable on strong moves
    LONG_HARD_STOP_MODE = "atr"    # "pct" = percentage of price, "atr" = ATR multiplier
    LONG_HARD_STOP_PCT = 0.01
    LONG_HARD_STOP_ATR_MULT = 3.0  # optimized: 3x ATR best balance of hard stop vs VWAP recross
    LONG_ATR_ACTIVATION_PCT = 50   # was 75 — trail activates earlier
    # Long take profit (R-multiples of ORB range, 0 = level disabled)
    LONG_R_TP1 = 0.5
    LONG_R_TP2 = 1.0
    LONG_R_TP3 = 2.0

    # Short parameters
    SHORT_ORB_MINUTES = 15
    SHORT_ORB_CLOSE_TIME = time(9, 45)
    SHORT_BREAKOUT_OFFSET = 0.05
    SHORT_ATR_BASE_MULTIPLIER = 2.00      # was 3.50 — tighter trail captures medium moves
    SHORT_ATR_TIER1_MULTIPLIER = 0.75     # was 1.00 — lock in more at tier1
    SHORT_ATR_TIER2_MULTIPLIER = 0.35
    SHORT_ATR_PROFIT_TIER1 = 1.5          # was 3.0 — tier1 kicks in sooner
    SHORT_ATR_PROFIT_TIER2 = 3.0          # was 5.0 — tier2 reachable on strong moves
    SHORT_HARD_STOP_MODE = "atr"   # "pct" = percentage of price, "atr" = ATR multiplier
    SHORT_HARD_STOP_PCT = 0.01
    SHORT_HARD_STOP_ATR_MULT = 3.0 # optimized: 3x ATR best balance of hard stop vs VWAP recross
    SHORT_ATR_ACTIVATION_PCT = 50  # was 75 — trail activates earlier
    # Short take profit (R-multiples of ORB range, 0 = level disabled)
    SHORT_R_TP1 = 0.5
    SHORT_R_TP2 = 1.0
    SHORT_R_TP3 = 2.0

    # Breakeven stop — move hard stop to entry price once R-target is reached
    USE_BREAKEVEN_STOP = False      # TEST A: disabled to isolate hard stop issue
    BREAKEVEN_R_TRIGGER = 0.5      # Move hard stop to breakeven at this R-multiple

    # Minimum breakout strength — reject if close is < X% beyond ORB level
    MIN_BREAKOUT_PCT = 0.001       # 0.1% minimum move beyond ORB level

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
    MAX_DAILY_LONGS = 1             # max long entries per symbol per day
    MAX_DAILY_SHORTS = 1            # max short entries per symbol per day
    MAX_DAILY_LOSSES_LONG = 1       # max long losses per symbol per day
    MAX_DAILY_LOSSES_SHORT = 1      # max short losses per symbol per day

    # Global daily limits (total entries across all symbols per day)
    MAX_DAILY_TOTAL_LONGS = 3       # symmetric with shorts — regime sizing handles risk
    MAX_DAILY_TOTAL_SHORTS = 3      # symmetric with longs
    MAX_DAILY_TOTAL_LOSSES = 3      # max total losses (both directions) per day — circuit breaker

    # ── Entry filters — direction-specific ──────────────────────────
    # Long filters (Jun 2025 optimization: EMA hurts, HC+HO+VR+MW synergistic)
    LONG_REQUIRE_EMA_ALIGN = False      # net-negative for longs (Sharpe 0.95→5.09 when OFF)
    LONG_REQUIRE_VWAP = True            # zero effect (all longs already > VWAP) — keep as safety
    LONG_REQUIRE_HIGHER_CLOSE = True    # +synergy with HO+VR+MW (Sharpe 5.09 best combo)
    LONG_REQUIRE_HIGHER_OPEN = True     # +synergy with HC+VR+MW (Sharpe 5.09 best combo)
    LONG_REQUIRE_VOLUME_RISING = False  # disabled — net-negative per short optimization, symmetric with shorts
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

    # Late-entry cutoff — no new entries after this time (prevents stale backfilled ORB breakouts)
    LAST_ENTRY_TIME = time(10, 0)   # 10:00 AM ET — 15 min after ORB lock at 9:45

    # Spread filter (percentage of mid-price)
    MAX_SPREAD_PCT = 0.40           # Widened from 0.24 — was blocking 80%+ of entries

    # Shared filter parameters
    MAX_WICK_PCT = 50               # Max wick as % of body size (50 = wick can't exceed body)
    ENTRY_WINDOW_BARS = 1           # Must enter within N bars of breakout detection

    # Universe source — published Google Sheets CSV URL (empty = use FORCE_DIRECTION fallback)
    UNIVERSE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKo9MtuEQI5a7pAxYuhbNoPX0IGtVQk347mBTNLsRWVt9FajGXqy0JYKgznqSb_w/pub?gid=1095632619&single=true&output=csv"
    WATCHLIST_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKo9MtuEQI5a7pAxYuhbNoPX0IGtVQk347mBTNLsRWVt9FajGXqy0JYKgznqSb_w/pub?gid=897666895&single=true&output=csv"

    # Coarse universe — dynamic daily filtering from all US equities (replaces static watchlist)
    USE_COARSE_UNIVERSE = False         # Disabled — using expanded fallback list in _load_watchlist()
    COARSE_MIN_DOLLAR_VOLUME = 10_000_000  # $10M daily dollar volume minimum
    COARSE_MAX_SYMBOLS = 200            # Start smaller to avoid timeout

    # Auto universe — Trade-Ideas exact replication
    USE_AUTO_UNIVERSE = True
    AUTO_MIN_PRICE = 10.0               # price >= $10 — eliminates penny-range stocks with outsized share counts
    AUTO_MIN_ADV = 1_000_000            # avg daily volume >= 1M shares (Trade-Ideas match)
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

    # Trend alignment filter — block trades against prevailing 20-day trend
    AUTO_TREND_FILTER = True            # enable/disable
    AUTO_TREND_RETURN_THRESHOLD = 0.05  # 5% — 20-day return must exceed this to count as trending

    # ── Auto Universe Scoring ─────────────────────────────────
    AUTO_MIN_COMPOSITE_SCORE = 30       # reject candidates scoring below this
    AUTO_SCORE_GAP_WEIGHT = 0.25        # gap quality weight (0-100 raw * weight)
    AUTO_SCORE_ATR_WEIGHT = 0.20        # ATR quality weight
    AUTO_SCORE_VOLUME_WEIGHT = 0.25     # volume/RVol weight
    AUTO_SCORE_SG_WEIGHT = 0.15         # SpotGamma conviction alignment weight
    AUTO_SCORE_LIQUIDITY_WEIGHT = 0.15  # ADV liquidity bonus weight

    # Mini-backtester params
    AUTO_MINI_BT_DAYS = 30              # days of 1-min history for mini-backtest
    AUTO_MINI_BT_TIMEOUT = 5.0          # per-symbol timeout (seconds)
    AUTO_TIER1_MIN_WIN_RATE = 0.50
    AUTO_TIER1_MIN_EXPECTANCY = 0.30
    AUTO_TIER2_MIN_WIN_RATE = 0.40
    AUTO_TIER2_MIN_EXPECTANCY = 0.10
    AUTO_TIER3_MIN_WIN_RATE = 0.30
    AUTO_TIER3_MIN_EXPECTANCY = 0.00

    # Gap sustainability check
    AUTO_GAP_MIN_RETENTION = 0.40       # downgrade if gap retained < 40%

    # ── SpotGamma Options Data ─────────────────────────────────
    SG_ENABLED = True                   # Master toggle — data collection only, filters disabled
    SG_SHEET_BASE_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ99XE1umgCIwhmEHK4H925kQMJylsUXjG011AZt1vMKVZ2exZcLqMjnst60kz_Hu3BUYsWlxS6TOAx/pub"
    SG_CURRENT_GID = "780844695"
    SG_HISTORY_GID = "1508647299"        # sg_levels tab — historical SpotGamma data

    # Filter 1: Gamma Regime — NEGATIVE gamma = chaotic/trending = 43% hard stop rate
    # Data: positive gamma had 13% hard stops, negative had 43%. Block/reduce on negative.
    SG_USE_GAMMA_REGIME = False
    SG_GAMMA_NEGATIVE_ACTION = "block" # "block" = skip entry; "reduce" = shrink size
    SG_GAMMA_NEGATIVE_SIZE_MULT = 0.50  # Size multiplier when negative gamma + reduce mode

    # Filter 2: Wall Targets (tighten trail when price approaches call/put wall)
    SG_USE_WALL_TARGETS = False
    SG_WALL_PROXIMITY_PCT = 0.50        # Tighten trail when within X% of wall
    SG_WALL_TRAIL_MULTIPLIER = 0.50     # Trail multiplier when near wall

    # Filter 3: Range Validation (skip if ORB range already consumed implied move)
    SG_USE_RANGE_VALIDATION = False
    SG_MAX_ORB_TO_IMPLIED_PCT = 80.0    # Skip if ORB range > X% of implied move $

    # Filter 4: Conviction (block entries against institutional positioning)
    SG_USE_CONVICTION_FILTER = False
    SG_BLOCK_LONG_ON_BEARISH = True     # Block longs when conviction=bearish
    SG_BLOCK_SHORT_ON_BULLISH = True    # Block shorts when conviction=bullish/strong_bullish
    SG_BLOCK_ON_NEUTRAL = False         # Block both directions when conviction=neutral

    # Filter 5: OPEX Proximity — "near" opex = 33% hard stops, 8% R1 hit rate
    # "imminent" = best (63% R1, 11% hard stops), "distant" = OK
    SG_USE_OPEX_FILTER = False
    SG_OPEX_BLOCK_NEAR = True           # Block entries when opex_proximity = "near"
    SG_OPEX_BLOCK_DISTANT = False       # Block entries when opex_proximity = "distant"

    # Execution
    SS_ENABLED = False             # Set True for paper/live — False for backtest
    SS_PAPER_URL = "https://app.signalstack.com/hook/w3rWj74GcoTYh8MF8FoCxR"
    SS_LIVE_URL = ""                # SignalStack live webhook URL
    SS_CONFIRM_FIRST = True         # Call SS synchronously, block QC order if broker rejects
    SS_TIMEOUT_SECONDS = 5          # HTTP timeout for synchronous SS call
    SS_RETRY_EXITS = False          # Retry failed exit webhooks once before giving up
