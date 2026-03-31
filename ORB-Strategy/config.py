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

    # Minimum ORB range — reject if ORB range < threshold (tiny ranges lack conviction)
    MIN_ORB_RANGE = 0.70           # Skip entries where ORB high-low < $0.70 (optimized: 0.70 best PnL/PF balance)
    MIN_ORB_ATR_RATIO = 4.5        # testing: cuts 22% of trades (56.6% WR) to keep 64.5% WR trades

    # Stall exit — tested bar5 (-$714) and bar15 (-$145). Both hurt net. Trail+hard stop sufficient.
    USE_STALL_EXIT = False
    STALL_EXIT_BARS = 15
    STALL_EXIT_ATR_THRESHOLD = 0.10

    # Entry quality filters — evidence-based from wide-open scanner analysis
    MIN_ENTRY_PRICE = 50.0         # ML validated: $50-$135 is the profitable zone
    MAX_ENTRY_PRICE = 135.0        # tested $10-$250: -$2,472 QC net, 14% DD — reverted
    MIN_ENTRY_BAR_VOLUME = 60_000  # skip if breakout bar volume < 60K (low conviction)

    # Take profit master toggle
    USE_TAKE_PROFIT = False         # True = exit partial shares at R levels; False = trail only

    # EMA cross exit
    EMA_CROSS_EXIT = False          # Exit when EMA9 crosses EMA20 against position

    # VWAP recross exit
    USE_VWAP_RECROSS_EXIT = True    # Keeps losers from bleeding to hard stop — saves ~$69 vs OFF
    VWAP_RECROSS_MIN_BARS = 3       # Consecutive bars price must stay wrong side of VWAP to trigger exit

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
    MAX_DAILY_LOSSES_LONG = 1       # tested 2: identical results, not binding
    MAX_DAILY_LOSSES_SHORT = 1      # tested 2: identical results, not binding

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
    LONG_REQUIRE_VOLUME_RISING = True   # ML: vol_rising=True → 63% WR +0.076R vs False → 53% WR -0.067R
    LONG_REQUIRE_MAX_WICK = True        # +synergy with HC+HO+VR (Sharpe 5.09, DD 1.2%)
    LONG_REQUIRE_ENTRY_WINDOW = False   # zero/negative effect for longs
    LONG_MAX_EMA_STRETCH = 2.0         # max (ema9-ema20)/atr — rejects chasing extended breakouts
    LONG_MAX_RVOL = 4.0                # optimal: 3.0 tested (-$234 QC), 4.0 is the sweet spot
    LONG_MIN_BAR_ATR_RATIO = 1.0       # breakout bar range must be >= 1x ATR — rejects weak/churning bars

    # Short filters (H1 2025 attribution: higher_close, wick, volume all positive)
    SHORT_REQUIRE_EMA_ALIGN = False
    SHORT_REQUIRE_VWAP = True
    SHORT_REQUIRE_HIGHER_CLOSE = True   # +$243 for shorts, blocks 40 losers at 30% WR
    SHORT_REQUIRE_HIGHER_OPEN = True    # +edge for shorts per optimization
    SHORT_REQUIRE_VOLUME_RISING = False # tested run007: -$108 vs longs-only, shorts don't benefit
    SHORT_REQUIRE_MAX_WICK = True       # +$203 for shorts, blocks 68 losers at 39.7% WR
    SHORT_REQUIRE_ENTRY_WINDOW = False  # no effect
    SHORT_MAX_EMA_STRETCH = 2.0        # max (ema20-ema9)/atr — rejects extended short entries

    # Late-entry cutoff — no new entries after this time (prevents stale backfilled ORB breakouts)
    LAST_ENTRY_TIME = time(10, 0)   # 10:00 AM ET — 15 min after ORB lock at 9:45

    # Spread filter (percentage of mid-price)
    MAX_SPREAD_PCT = 0.28           # ML rec: tight spread Q1+Q2 = +0.083 R vs wide Q3+Q4 = +0.003 R

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

    # Auto universe — wide open for data collection, filter AFTER
    USE_AUTO_UNIVERSE = True
    AUTO_MIN_PRICE = 10.0               # price >= $10
    AUTO_MIN_ADV = 500_000              # avg daily volume >= 500K (was 1M)
    AUTO_MIN_TODAY_VOLUME = 50_000      # today's volume >= 50K (was 100K)
    AUTO_MIN_ATR = 0.30                 # ATR14 >= $0.30 (was $1)
    AUTO_GAP_PCT = 0.01                 # gap >= 1% (was 2%)
    AUTO_MAX_GAP_PCT = 0.15             # cap at 15% (was 10%)
    AUTO_MAX_SHORT_FLOAT = 0.30         # short float <= 30% (was 20%)
    AUTO_MIN_FLOAT_SHARES = 500_000     # float >= 500K (was 1M)
    AUTO_REQUIRE_EPS = False            # disabled — was filtering too many growth stocks
    AUTO_MIN_MARKET_CAP = 1_000_000     # market cap >= $1M (was $5M)
    AUTO_NO_EARNINGS_TODAY = True       # keep — earnings days are binary events
    AUTO_MAX_PRICE = 500.0              # price <= $500 (was $200)
    AUTO_MAX_SYMBOLS = 40               # optimal: 20->30->40 each improved, 50 degraded

    # Trend alignment filter
    AUTO_TREND_FILTER = False           # DISABLED — let data show if trend matters

    # ── Auto Universe Scoring ─────────────────────────────────
    AUTO_MIN_COMPOSITE_SCORE = 10       # very low bar (was 30) — let more through
    AUTO_SCORE_GAP_WEIGHT = 0.25
    AUTO_SCORE_ATR_WEIGHT = 0.20
    AUTO_SCORE_VOLUME_WEIGHT = 0.25
    AUTO_SCORE_SG_WEIGHT = 0.15
    AUTO_SCORE_LIQUIDITY_WEIGHT = 0.15

    # Mini-backtester — DISABLED to stop rejecting everything
    AUTO_MINI_BT_ENABLED = False        # skip mini-backtest entirely
    AUTO_MINI_BT_DAYS = 30
    AUTO_MINI_BT_TIMEOUT = 5.0
    AUTO_MINI_BT_MIN_TRADES = 3
    AUTO_TIER1_MIN_WIN_RATE = 0.50
    AUTO_TIER1_MIN_EXPECTANCY = 0.20
    AUTO_TIER2_MIN_WIN_RATE = 0.40
    AUTO_TIER2_MIN_EXPECTANCY = 0.10
    AUTO_TIER3_MIN_WIN_RATE = 0.30
    AUTO_TIER3_MIN_EXPECTANCY = 0.00

    # Gap sustainability check
    AUTO_GAP_MIN_RETENTION = 0.10       # very loose — only kill if gap nearly fully faded

    # ── SpotGamma Options Data (Supabase) ─────────────────────────────────
    SG_ENABLED = True                   # Master toggle — data collection only, filters disabled
    SG_SUPABASE_URL = "https://jqjqacvexefnmgfofxgn.supabase.co"
    SG_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpxanFhY3ZleGVmbm1nZm9meGduIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgwMTU4OTksImV4cCI6MjA4MzU5MTg5OX0.S0wvbwPlBnu4tQUhHw5A-d6TSeHLrCK6fOTUTxJLeqY"
    SG_SUPABASE_TABLE = "sg_levels"

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
