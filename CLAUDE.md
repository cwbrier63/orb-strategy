# CLAUDE.md — ORB Strategy Project Guide

This file is read by Claude Code at the start of every session. It contains everything needed to work on this project correctly without re-explanation.

---

## 1. PROJECT OVERVIEW

**Strategy:** Opening Range Breakout (ORB) — trades breakouts of the first 5-minute candle after market open (9:30–9:35 ET).

**Migration goal:** Replace manual TrendSpider V2-2 JavaScript bot + Excel sizing spreadsheet with a fully automated QuantConnect (QC) Classic Algorithm that routes orders through SignalStack → TradeThePool (TTP) prop account.

**Execution chain:**
```
QC Algorithm → self.notify.web(url) → SignalStack webhook → TradeThePool prop account
```

**Account:** $25,000 TTP prop account. Daily risk budget = $500 base (2% of account), adjusted by regime multiplier.

---

## 2. CRITICAL QC API RULES — READ BEFORE WRITING ANY CODE

QC Python uses **snake_case** throughout. The most common mistake is using PascalCase from C# docs.

### Always use snake_case:
```python
# CORRECT                          # WRONG
bar.close                          bar.Close
bar.open                           bar.Open
bar.high                           bar.High
bar.low                            bar.Low
bar.volume                         bar.Volume
self.log()                         self.Log()
self.debug()                       self.Debug()
self.notify.web()                  self.Notify.Web()
self.market_order()                self.MarketOrder()
self.limit_order()                 self.LimitOrder()
self.stop_market_order()           self.StopMarketOrder()
self.add_equity()                  self.AddEquity()
self.set_start_date()              self.SetStartDate()
self.set_end_date()                self.SetEndDate()
self.set_cash()                    self.SetCash()
self.set_brokerage_model()         self.SetBrokerageModel()
self.portfolio[]                   self.Portfolio[]
self.securities[]                  self.Securities[]
self.time                          self.Time
self.schedule.on()                 self.Schedule.On()
self.date_rules                    self.DateRules
self.time_rules                    self.TimeRules
self.ema()                         self.EMA()
self.atr()                         self.ATR()
self.vwap()                        self.VWAP()
```

### Every file must start with:
```python
from AlgorithmImports import *
```

### Use Classic Algorithm (not Framework):
- Do NOT use `QCAlgorithmFramework`, `AlphaModel`, `PortfolioConstructionModel`, etc.
- Inherit from `QCAlgorithm` directly: `class OrbAlgorithm(QCAlgorithm):`
- Reason: ORB requires tightly coupled entry/exit state (ATR trail, reversal logic, daily counters) that Framework's decoupled architecture handles poorly.

### Resolution:
- Subscribe all symbols at **1-minute** resolution: `Resolution.Minute`
- ORB window is 9:30–9:35 ET → use first completed 1m bar after 9:35

### Consolidators (if needed):
```python
consolidator = TradeBarConsolidator(timedelta(minutes=5))
consolidator.data_consolidated += self.on_five_min_bar
self.subscription_manager.add_consolidator(symbol, consolidator)
```

---

## 3. MODULE MAP

```
C:\trading\orb-strategy\ORB-Strategy\
├── main.py                  # OrbAlgorithm — Initialize(), OnData(), scheduling
├── config.py                # All constants and parameters (no magic numbers elsewhere)
├── orb_calculator.py        # OrbCalculator — ORB high/low/range, R-targets
├── indicators.py            # IndicatorManager — VWAP, EMA 9/20/50, ATR14
├── signal_engine.py         # SignalEngine — breakout detection, entry filters
├── trade_manager.py         # TradeManager — ATR trail tiers, reversals, cross-exit
├── risk_manager.py          # RiskManager — TTP position sizing, daily limits
└── signalstack_bridge.py    # SignalStackBridge — ALL notify.web() calls isolated here
```

**Data flow:**
```
OnData(1m bar)
  → OrbCalculator (build/lock ORB range)
  → IndicatorManager (update VWAP, EMAs, ATR)
  → SignalEngine (check breakout conditions)
  → RiskManager (calculate position size)
  → TradeManager (manage open positions, trail stops)
  → SignalStackBridge (fire webhook if action needed)
```

---

## 4. CONFIG.PY — PARAMETERS

All magic numbers live here. Never hardcode values in other modules.

```python
# config.py
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
```

---

## 5. SIGNALSTACK BRIDGE

**ALL** `self.notify.web()` calls must go through `SignalStackBridge`. No other module calls notify directly.

### Payload format (stocks):
```python
{"symbol": "AAPL", "action": "buy", "quantity": 100}
```

### Valid actions:
- `buy` — enter long
- `sell` — exit long
- `sell_short` — enter short
- `buy_to_cover` — exit short
- `close` — close all positions in symbol (emergency)

### Bridge pattern:
```python
# signalstack_bridge.py
from AlgorithmImports import *
import json

class SignalStackBridge:
    def __init__(self, algorithm, config):
        self.algo = algorithm
        self.config = config
    
    def send(self, symbol: str, action: str, quantity: int):
        if not self.config.SS_ENABLED:
            self.algo.log(f"[SS_DISABLED] {action} {quantity} {symbol}")
            return
        
        payload = json.dumps({
            "symbol": symbol,
            "action": action,
            "quantity": quantity
        })
        
        url = self.config.SS_LIVE_URL  # swap to SS_PAPER_URL for paper
        self.algo.notify.web(url, payload)
        self.algo.log(f"[SS_SENT] {action} {quantity} {symbol}")
```

---

## 6. THREE-STAGE EXECUTION CONFIG

| Stage | SS_ENABLED | URL used | Destination |
|-------|-----------|----------|-------------|
| BACKTEST | False | none | QC results only |
| PAPER | True | SS_PAPER_URL | TTP paper account |
| LIVE | True | SS_LIVE_URL | TTP funded account |

**Only one line changes between paper and live** — the URL in `signalstack_bridge.py`. No logic changes.

To switch stages, update `config.py`:
```python
SS_ENABLED = True          # was False for backtest
# Then in bridge, use SS_PAPER_URL or SS_LIVE_URL
```

---

## 7. POSITION SIZING (TTP FORMULA)

This replicates the Excel TTP_ORB_Combined spreadsheet exactly.

```python
# risk_manager.py
def calculate_shares(self, symbol, max_dd_pct, price):
    """
    Replicates TTP spreadsheet formula.
    max_dd_pct: from variance backtest (e.g. -0.08 for -8% max drawdown)
    """
    adj_risk = self.config.BASE_DAILY_RISK * self.config.REGIME_CURRENT
    max_position_dollars = adj_risk / abs(max_dd_pct)
    shares = math.floor(max_position_dollars / price)
    return max(shares, 0)
```

**Example (March 6 2026):**
- Base daily risk: $500
- Regime multiplier: 0.50 (Uptrend Under Pressure)
- Adj risk: $250
- Symbol max DD: -8% → Max pos: $250 / 0.08 = $3,125
- Price $25.00 → Shares: floor(3125/25) = 125

---

## 8. VARIANCE SCORING TIERS

Used to filter and rank symbols. Currently manual (TrendSpider CSV → Claude analysis). Phase 2 will automate this inside QC universe selection.

| Tier | Net Perf | Win Rate | Max DD | Expectancy | R/R | Min Positions |
|------|----------|----------|--------|------------|-----|---------------|
| 1 | >10% | ≥52% | >-6% | ≥0.4 | ≥1.5 | ≥30 |
| 2 | >4% | ≥49% | >-10% | ≥0.2 | ≥1.2 | ≥30 |
| 3 | ≥0% | any | >-20% | ≥0.1 | ≥1.0 | ≥30 |
| DISQUALIFIED | — | — | — | — | — | Earnings gap today |
| REJECT | <0% or Expectancy<0 or MaxDD<-20% or R/R<1.0 |

Trade priority within each session: Tier 1 first, then Tier 2, then Tier 3.

---

## 9. ATR TRAIL LOGIC (INVERTED TIERS + RATCHET)

Trail gets **tighter** as profit increases. Stop never loosens (ratchet).

```python
def update_trail(self, symbol, current_price, entry_price, atr, is_long):
    profit_in_atrs = abs(current_price - entry_price) / atr
    
    if profit_in_atrs >= self.config.ATR_PROFIT_TIER2:
        multiplier = self.config.ATR_TIER2_MULTIPLIER   # 0.35x
    elif profit_in_atrs >= self.config.ATR_PROFIT_TIER1:
        multiplier = self.config.ATR_TIER1_MULTIPLIER   # 0.75x
    else:
        multiplier = self.config.ATR_BASE_MULTIPLIER    # 1.50x
    
    trail_distance = atr * multiplier
    
    if is_long:
        new_stop = current_price - trail_distance
        # Ratchet: stop only moves up, never down
        self.stops[symbol] = max(new_stop, self.stops.get(symbol, 0))
    else:
        new_stop = current_price + trail_distance
        # Ratchet: stop only moves down, never up
        self.stops[symbol] = min(new_stop, self.stops.get(symbol, float('inf')))
```

---

## 10. ENTRY FILTERS (from TrendSpider V2-2)

All conditions must be true to trigger a long entry:
1. Price breaks above ORB high on completed 1m bar close
2. Close > VWAP
3. EMA9 > EMA20 (momentum confirmation)
4. ATR > 0 (indicator is ready)
5. Not already in a position for this symbol
6. Daily trade count < MAX_DAILY_TRADES
7. Current time < 3:30 PM ET (no new entries in last 30 min)

All conditions for short entry (mirror image):
1. Price breaks below ORB low on completed 1m bar close
2. Close < VWAP
3. EMA9 < EMA20
4. ATR > 0
5. Not already in position
6. Daily trade count < MAX_DAILY_TRADES
7. Current time < 3:30 PM ET

---

## 11. REGIME FRAMEWORK

Updated manually each morning based on Briefings.com Wake-Up Call.

| Market Condition | Multiplier | Adj Daily Risk ($500 base) |
|-----------------|------------|---------------------------|
| Strong Uptrend | 1.00 | $500 |
| Uptrend | 0.90 | $450 |
| Uptrend Under Pressure | 0.50 | $250 |
| Downtrend | 0.50 | $250 |
| Extreme Risk-Off | 0.25 | $125 |

Update `REGIME_CURRENT` in `config.py` each morning before market open.

---

## 12. CLOUD BACKTEST COMMAND

Always use cloud backtesting (no Docker required):

```powershell
cd C:\trading\orb-strategy
lean cloud backtest "ORB-Strategy" --push --open
```

- `--push` syncs local files to QC cloud first
- `--open` opens results in browser when complete
- Typical runtime: 1–3 minutes for 1-year backtest

---

## 13. PHASE 1 BUILD ORDER (MINIMUM VIABLE MIGRATION)

Build in this sequence. Each step must backtest cleanly before moving to next.

**Week 1:**
1. `config.py` — all parameters, SS_ENABLED=False
2. `indicators.py` — VWAP, EMA 9/20/50, ATR14 wired up
3. `orb_calculator.py` — single 5m ORB period, lock range at 9:35
4. `signal_engine.py` — long entries only first, all 7 filters
5. `signalstack_bridge.py` — log-only mode (SS_ENABLED=False)

**Week 2:**
6. `trade_manager.py` — base ATR trail (1.5x) first, add tiers after
7. `risk_manager.py` — TTP sizing formula
8. `main.py` — wire all modules together
9. First cloud backtest — fix errors, verify logic matches TrendSpider results
10. Add short entries to signal_engine.py
11. Add ATR tier1/tier2 to trade_manager.py

**Keep manual for Phase 1:**
- Trade-Ideas gap scanner (morning scan)
- Briefings.com regime assessment
- TrendSpider variance scoring (still run CSV → Claude analysis)

**Phase 2 (after paper trading validation):**
- Automate universe selection inside QC (replace Trade-Ideas + TrendSpider)
- Automate regime detection (SPY premium, VIX, oil signals)

---

## 14. SIGNALSTACK TESTING PROTOCOL

Before going live, test the webhook manually:

```powershell
# Test paper URL (replace URL with your actual SignalStack paper webhook)
Invoke-WebRequest -Uri "YOUR_SS_PAPER_URL" -Method POST `
  -ContentType "application/json" `
  -Body '{"symbol":"SPY","action":"buy","quantity":1}'
```

Confirm the order appears in TTP paper account before enabling SS_ENABLED=True.

---

## 15. KEY REFERENCE

**QC credentials:** `~/.lean/credentials` (set by `lean login`)  
**QC user ID:** 282320  
**Workspace:** `C:\trading\orb-strategy\`  
**Project folder:** `C:\trading\orb-strategy\ORB-Strategy\`  
**Run backtest:** `lean cloud backtest "ORB-Strategy" --push --open`  
**QC docs:** https://www.quantconnect.com/docs/v2/writing-algorithms  
**LEAN CLI docs:** https://www.lean.io/docs/v2/lean-cli  

**Resolution improvement over TrendSpider:**
- TrendSpider (5m bars): breakout at 9:35:30 fires at 9:40 close (~4.5 min late)
- QC (1m bars): breakout at 9:35:30 fires at 9:36 close (~30 sec late)
- ~9x latency improvement

---

*Last updated: March 6, 2026*