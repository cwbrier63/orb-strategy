from AlgorithmImports import *


def apply_parameters(algo):
    """Override config defaults with QC optimization parameters if provided.
    Every numeric/boolean config parameter is optimizable via get_parameter().
    Parameter names use snake_case matching the config attribute names (lowercased).
    """
    config = algo.config

    def _float(name, attr):
        p = algo.get_parameter(name)
        if p is not None:
            setattr(config, attr, float(p))

    def _int(name, attr):
        p = algo.get_parameter(name)
        if p is not None:
            setattr(config, attr, int(p))

    def _bool(name, attr):
        p = algo.get_parameter(name)
        if p is not None:
            setattr(config, attr, str(p).lower() in ("true", "1", "yes"))

    # ── Account ──
    _int("account_size", "ACCOUNT_SIZE")
    _float("base_daily_risk", "BASE_DAILY_RISK")
    _float("max_total_allocated", "MAX_TOTAL_ALLOCATED")

    # ── Regime ──
    _float("regime_current", "REGIME_CURRENT")
    _float("regime_min_direction_mult", "REGIME_MIN_DIRECTION_MULT")
    _bool("regime_auto_detect", "REGIME_AUTO_DETECT")

    # ── Strategy mode ──
    p = algo.get_parameter("strategy_mode")
    if p is not None:
        config.STRATEGY_MODE = str(p)

    # ── ORF parameters ──
    _float("orf_max_regime", "ORF_MAX_REGIME")
    _float("orf_max_orb_range_atr", "ORF_MAX_ORB_RANGE_ATR")
    _float("orf_hard_stop_atr_mult", "ORF_HARD_STOP_ATR_MULT")
    _float("orf_min_entry_volume", "ORF_MIN_ENTRY_VOLUME")

    # ── Long direction parameters ──
    p = algo.get_parameter("long_orb_minutes")
    if p is not None:
        config.LONG_ORB_MINUTES = int(p)
        base = datetime(2000, 1, 1, 9, 30)
        config.LONG_ORB_CLOSE_TIME = (base + timedelta(minutes=config.LONG_ORB_MINUTES)).time()

    _float("long_breakout_offset", "LONG_BREAKOUT_OFFSET")
    _float("long_atr_base_mult", "LONG_ATR_BASE_MULTIPLIER")
    _float("long_atr_tier1_mult", "LONG_ATR_TIER1_MULTIPLIER")
    _float("long_atr_tier2_mult", "LONG_ATR_TIER2_MULTIPLIER")
    _float("long_atr_profit_tier1", "LONG_ATR_PROFIT_TIER1")
    _float("long_atr_profit_tier2", "LONG_ATR_PROFIT_TIER2")
    p = algo.get_parameter("long_hard_stop_mode")
    if p is not None:
        config.LONG_HARD_STOP_MODE = str(p)
    _float("long_hard_stop_pct", "LONG_HARD_STOP_PCT")
    _float("long_hard_stop_atr_mult", "LONG_HARD_STOP_ATR_MULT")
    _float("long_atr_activation_pct", "LONG_ATR_ACTIVATION_PCT")
    _float("long_r_tp1", "LONG_R_TP1")
    _float("long_r_tp2", "LONG_R_TP2")
    _float("long_r_tp3", "LONG_R_TP3")

    # ── Short direction parameters ──
    p = algo.get_parameter("short_orb_minutes")
    if p is not None:
        config.SHORT_ORB_MINUTES = int(p)
        base = datetime(2000, 1, 1, 9, 30)
        config.SHORT_ORB_CLOSE_TIME = (base + timedelta(minutes=config.SHORT_ORB_MINUTES)).time()

    _float("short_breakout_offset", "SHORT_BREAKOUT_OFFSET")
    _float("short_atr_base_mult", "SHORT_ATR_BASE_MULTIPLIER")
    _float("short_atr_tier1_mult", "SHORT_ATR_TIER1_MULTIPLIER")
    _float("short_atr_tier2_mult", "SHORT_ATR_TIER2_MULTIPLIER")
    _float("short_atr_profit_tier1", "SHORT_ATR_PROFIT_TIER1")
    _float("short_atr_profit_tier2", "SHORT_ATR_PROFIT_TIER2")
    p = algo.get_parameter("short_hard_stop_mode")
    if p is not None:
        config.SHORT_HARD_STOP_MODE = str(p)
    _float("short_hard_stop_pct", "SHORT_HARD_STOP_PCT")
    _float("short_hard_stop_atr_mult", "SHORT_HARD_STOP_ATR_MULT")
    _float("short_atr_activation_pct", "SHORT_ATR_ACTIVATION_PCT")
    _float("short_r_tp1", "SHORT_R_TP1")
    _float("short_r_tp2", "SHORT_R_TP2")
    _float("short_r_tp3", "SHORT_R_TP3")

    # ── Exit toggles ──
    _bool("use_take_profit", "USE_TAKE_PROFIT")
    _bool("ema_cross_exit", "EMA_CROSS_EXIT")
    _bool("use_vwap_recross_exit", "USE_VWAP_RECROSS_EXIT")
    _int("vwap_recross_min_bars", "VWAP_RECROSS_MIN_BARS")

    # ── Gap filter ──
    _float("gap_filter_pct", "GAP_FILTER_PCT")
    _bool("use_gap_direction_gate", "USE_GAP_DIRECTION_GATE")
    _float("gap_reject_threshold", "GAP_REJECT_THRESHOLD")

    # ── EMA periods ──
    _int("ema_fast", "EMA_FAST")
    _int("ema_mid", "EMA_MID")
    _int("ema_slow", "EMA_SLOW")

    # ── ATR period ──
    _int("atr_period", "ATR_PERIOD")

    # ── Universe limits ──
    _int("max_longs", "MAX_LONGS")
    _int("max_shorts", "MAX_SHORTS")

    # ── Daily trade limits (per-symbol) ──
    _int("max_daily_longs", "MAX_DAILY_LONGS")
    _int("max_daily_shorts", "MAX_DAILY_SHORTS")
    _int("max_daily_losses_long", "MAX_DAILY_LOSSES_LONG")
    _int("max_daily_losses_short", "MAX_DAILY_LOSSES_SHORT")

    # ── Daily trade limits (global) ──
    _int("max_daily_total_longs", "MAX_DAILY_TOTAL_LONGS")
    _int("max_daily_total_shorts", "MAX_DAILY_TOTAL_SHORTS")
    _int("max_daily_total_losses", "MAX_DAILY_TOTAL_LOSSES")

    # ── Long entry filters ──
    _bool("long_require_ema_align", "LONG_REQUIRE_EMA_ALIGN")
    _bool("long_require_vwap", "LONG_REQUIRE_VWAP")
    _bool("long_require_higher_close", "LONG_REQUIRE_HIGHER_CLOSE")
    _bool("long_require_higher_open", "LONG_REQUIRE_HIGHER_OPEN")
    _bool("long_require_volume_rising", "LONG_REQUIRE_VOLUME_RISING")
    _bool("long_require_max_wick", "LONG_REQUIRE_MAX_WICK")
    _bool("long_require_entry_window", "LONG_REQUIRE_ENTRY_WINDOW")
    _float("long_max_ema_stretch", "LONG_MAX_EMA_STRETCH")

    # ── Short entry filters ──
    _bool("short_require_ema_align", "SHORT_REQUIRE_EMA_ALIGN")
    _bool("short_require_vwap", "SHORT_REQUIRE_VWAP")
    _bool("short_require_higher_close", "SHORT_REQUIRE_HIGHER_CLOSE")
    _bool("short_require_higher_open", "SHORT_REQUIRE_HIGHER_OPEN")
    _bool("short_require_volume_rising", "SHORT_REQUIRE_VOLUME_RISING")
    _bool("short_require_max_wick", "SHORT_REQUIRE_MAX_WICK")
    _bool("short_require_entry_window", "SHORT_REQUIRE_ENTRY_WINDOW")
    _float("short_max_ema_stretch", "SHORT_MAX_EMA_STRETCH")

    # ── Spread & wick filter parameters ──
    _float("max_spread_pct", "MAX_SPREAD_PCT")
    _float("max_wick_pct", "MAX_WICK_PCT")
    _int("entry_window_bars", "ENTRY_WINDOW_BARS")

    # ── SpotGamma parameters ──
    _bool("sg_enabled", "SG_ENABLED")
    _bool("sg_use_gamma_regime", "SG_USE_GAMMA_REGIME")
    _float("sg_gamma_negative_size_mult", "SG_GAMMA_NEGATIVE_SIZE_MULT")
    _bool("sg_use_wall_targets", "SG_USE_WALL_TARGETS")
    _float("sg_wall_proximity_pct", "SG_WALL_PROXIMITY_PCT")
    _float("sg_wall_trail_multiplier", "SG_WALL_TRAIL_MULTIPLIER")
    _bool("sg_use_range_validation", "SG_USE_RANGE_VALIDATION")
    _float("sg_max_orb_to_implied_pct", "SG_MAX_ORB_TO_IMPLIED_PCT")
    _bool("sg_use_conviction_filter", "SG_USE_CONVICTION_FILTER")
    _bool("sg_block_long_on_bearish", "SG_BLOCK_LONG_ON_BEARISH")
    _bool("sg_block_short_on_bullish", "SG_BLOCK_SHORT_ON_BULLISH")
    _bool("sg_block_on_neutral", "SG_BLOCK_ON_NEUTRAL")
    _bool("sg_use_opex_filter", "SG_USE_OPEX_FILTER")
    _bool("sg_opex_block_near", "SG_OPEX_BLOCK_NEAR")
    _bool("sg_opex_block_distant", "SG_OPEX_BLOCK_DISTANT")

    # ── Direction override ──
    _int("force_direction", "FORCE_DIRECTION")

    # ── Auto universe scanner thresholds ──
    _float("auto_min_price", "AUTO_MIN_PRICE")
    _float("auto_max_price", "AUTO_MAX_PRICE")
    _float("auto_min_adv", "AUTO_MIN_ADV")
    _float("auto_min_today_volume", "AUTO_MIN_TODAY_VOLUME")
    _float("auto_min_atr", "AUTO_MIN_ATR")
    _float("auto_gap_pct", "AUTO_GAP_PCT")
    _float("auto_max_gap_pct", "AUTO_MAX_GAP_PCT")
    _float("auto_max_short_float", "AUTO_MAX_SHORT_FLOAT")
    _float("auto_min_float_shares", "AUTO_MIN_FLOAT_SHARES")
    _bool("auto_require_eps", "AUTO_REQUIRE_EPS")
    _float("auto_min_market_cap", "AUTO_MIN_MARKET_CAP")
    _bool("auto_no_earnings_today", "AUTO_NO_EARNINGS_TODAY")
    _int("auto_max_symbols", "AUTO_MAX_SYMBOLS")

    # ── Auto universe scoring ──
    _float("auto_min_composite_score", "AUTO_MIN_COMPOSITE_SCORE")
    _float("auto_score_gap_weight", "AUTO_SCORE_GAP_WEIGHT")
    _float("auto_score_atr_weight", "AUTO_SCORE_ATR_WEIGHT")
    _float("auto_score_volume_weight", "AUTO_SCORE_VOLUME_WEIGHT")
    _float("auto_score_sg_weight", "AUTO_SCORE_SG_WEIGHT")
    _float("auto_score_liquidity_weight", "AUTO_SCORE_LIQUIDITY_WEIGHT")

    # ── Mini-backtest tier thresholds ──
    _int("auto_mini_bt_days", "AUTO_MINI_BT_DAYS")
    _float("auto_tier1_min_win_rate", "AUTO_TIER1_MIN_WIN_RATE")
    _float("auto_tier1_min_expectancy", "AUTO_TIER1_MIN_EXPECTANCY")
    _float("auto_tier2_min_win_rate", "AUTO_TIER2_MIN_WIN_RATE")
    _float("auto_tier2_min_expectancy", "AUTO_TIER2_MIN_EXPECTANCY")
    _float("auto_tier3_min_win_rate", "AUTO_TIER3_MIN_WIN_RATE")
    _float("auto_tier3_min_expectancy", "AUTO_TIER3_MIN_EXPECTANCY")

    # ── Gap sustainability ──
    _float("auto_gap_min_retention", "AUTO_GAP_MIN_RETENTION")

    # ── Linked parameters (set both long+short at once for optimization) ──
    _linked = {
        "atr_base_mult": ("LONG_ATR_BASE_MULTIPLIER", "SHORT_ATR_BASE_MULTIPLIER"),
        "atr_tier1_mult": ("LONG_ATR_TIER1_MULTIPLIER", "SHORT_ATR_TIER1_MULTIPLIER"),
        "atr_tier2_mult": ("LONG_ATR_TIER2_MULTIPLIER", "SHORT_ATR_TIER2_MULTIPLIER"),
        "atr_profit_tier1": ("LONG_ATR_PROFIT_TIER1", "SHORT_ATR_PROFIT_TIER1"),
        "atr_profit_tier2": ("LONG_ATR_PROFIT_TIER2", "SHORT_ATR_PROFIT_TIER2"),
        "hard_stop_pct": ("LONG_HARD_STOP_PCT", "SHORT_HARD_STOP_PCT"),
        "hard_stop_atr_mult": ("LONG_HARD_STOP_ATR_MULT", "SHORT_HARD_STOP_ATR_MULT"),
        "atr_activation_pct": ("LONG_ATR_ACTIVATION_PCT", "SHORT_ATR_ACTIVATION_PCT"),
        "r_tp1": ("LONG_R_TP1", "SHORT_R_TP1"),
        "r_tp2": ("LONG_R_TP2", "SHORT_R_TP2"),
        "r_tp3": ("LONG_R_TP3", "SHORT_R_TP3"),
    }
    for param_name, (long_attr, short_attr) in _linked.items():
        p = algo.get_parameter(param_name)
        if p is not None:
            val = float(p)
            setattr(config, long_attr, val)
            setattr(config, short_attr, val)
            algo.log(f"[PARAM OVERRIDE] {param_name}={val} → {long_attr}, {short_attr}")

    p = algo.get_parameter("orb_minutes")
    if p is not None:
        config.LONG_ORB_MINUTES = int(p)
        config.SHORT_ORB_MINUTES = int(p)
        base = datetime(2000, 1, 1, 9, 30)
        close_time = (base + timedelta(minutes=int(p))).time()
        config.LONG_ORB_CLOSE_TIME = close_time
        config.SHORT_ORB_CLOSE_TIME = close_time
        algo.log(f"[PARAM OVERRIDE] orb_minutes={p}")

    p = algo.get_parameter("breakout_offset")
    if p is not None:
        config.LONG_BREAKOUT_OFFSET = float(p)
        config.SHORT_BREAKOUT_OFFSET = float(p)
        algo.log(f"[PARAM OVERRIDE] breakout_offset={p}")

    # ── Backward-compat shortcut ──
    p = algo.get_parameter("max_trades_per_direction")
    if p is not None:
        config.MAX_DAILY_LONGS = int(p)
        config.MAX_DAILY_SHORTS = int(p)
        algo.log(f"[PARAM OVERRIDE] max_trades_per_direction={p}")

    # ── Live override: clear a symbol from QC internal state ──
    p = algo.get_parameter("clear_symbol")
    if p is not None and p != "":
        algo._log(f"[CLEAR_SYMBOL] Wiping QC state for {p}")
        clear_sym = algo.add_equity(p, Resolution.MINUTE).symbol
        if algo.portfolio[clear_sym].invested:
            algo.liquidate(clear_sym)
