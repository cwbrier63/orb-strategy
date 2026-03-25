"""
ORB Strategy — Backtest Analysis Script

Usage:
  python analysis/analyze_backtest.py                          # fetch latest backtest orders via QC API
  python analysis/analyze_backtest.py --backtest-id XXXXXX     # specific backtest
  python analysis/analyze_backtest.py --local                  # use existing analysis/paired_trades.csv

Fetches orders from QC API, pairs entries/exits, and runs full analysis.
Exit reasons now appear in order tags (TRAIL_STOP, HARD_STOP, EOD, etc.)
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time as time_mod
from collections import defaultdict
from datetime import datetime

# ── QC API Config ──────────────────────────────────────────────
QC_UID = '282320'
QC_TOKEN = 'ff825a2a8d827663d3264ad3ec74f3ee632d15d134d61d615c78853284a3627e'
QC_PROJECT_ID = 28746396
QC_ORG_ID = 'fab4f11564561fd6cb084951325a73b0'

ANALYSIS_DIR = os.path.join(os.path.dirname(__file__))


def qc_auth():
    ts = str(int(time_mod.time()))
    hash_val = hashlib.sha256((QC_TOKEN + ':' + ts).encode()).hexdigest()
    return (QC_UID, hash_val), {'Timestamp': ts}


def get_latest_backtest_id():
    """Get the most recent backtest ID from QC API."""
    import requests
    auth, headers = qc_auth()
    r = requests.get(
        f'https://www.quantconnect.com/api/v2/backtests/read',
        params={'projectId': QC_PROJECT_ID},
        auth=auth, headers=headers
    )
    data = r.json()
    if data.get('success') and data.get('backtests'):
        # Return most recent
        bt = sorted(data['backtests'], key=lambda x: x.get('created', ''), reverse=True)
        return bt[0]['backtestId']
    return None


def fetch_orders(backtest_id):
    """Fetch all orders from a backtest in batches of 100."""
    import requests
    all_orders = []
    batch = 0
    while True:
        auth, headers = qc_auth()
        start = batch * 100
        r = requests.post(
            'https://www.quantconnect.com/api/v2/backtests/orders/read',
            json={'projectId': QC_PROJECT_ID, 'backtestId': backtest_id,
                  'start': start, 'end': start + 100},
            auth=auth, headers=headers
        )
        data = r.json()
        if not data.get('success'):
            print(f'API error at batch {batch}: {data.get("errors")}')
            break
        orders = data.get('orders', [])
        if not orders:
            break
        all_orders.extend(orders)
        batch += 1
        if len(orders) < 100:
            break
    return all_orders


def pair_trades(orders):
    """Pair entry/exit orders into trades."""
    trades = []
    open_positions = {}

    for o in sorted(orders, key=lambda x: x['id']):
        sym = o['symbol']['value']
        qty = o['quantity']
        price = o['price']
        t = o['time']
        tag = o.get('tag', '')

        if sym not in open_positions:
            open_positions[sym] = {
                'symbol': sym, 'entry_time': t, 'entry_price': price,
                'entry_qty': qty, 'direction': 'LONG' if qty > 0 else 'SHORT',
            }
        else:
            entry = open_positions.pop(sym)
            is_long = entry['direction'] == 'LONG'
            pnl_per_share = (price - entry['entry_price']) if is_long else (entry['entry_price'] - price)
            abs_qty = abs(entry['entry_qty'])

            try:
                et = datetime.fromisoformat(entry['entry_time'].replace('Z', ''))
                xt = datetime.fromisoformat(t.replace('Z', ''))
                duration_min = (xt - et).total_seconds() / 60
                entry_date = et.strftime('%Y-%m-%d')
                entry_hour = et.hour
                entry_dow = et.strftime('%A')
                month = et.strftime('%Y-%m')
            except Exception:
                duration_min = entry_date = entry_hour = entry_dow = month = 0

            trades.append({
                'symbol': sym,
                'direction': entry['direction'],
                'entry_time': entry['entry_time'],
                'exit_time': t,
                'entry_price': entry['entry_price'],
                'exit_price': price,
                'quantity': abs_qty,
                'gross_pnl': pnl_per_share * abs_qty,
                'pnl_pct': (pnl_per_share / entry['entry_price']) * 100 if entry['entry_price'] else 0,
                'duration_min': duration_min,
                'exit_reason': tag or 'unknown',
                'entry_date': entry_date,
                'entry_hour': entry_hour,
                'entry_dow': entry_dow,
                'month': month,
            })
    return trades


def save_trades_csv(trades, path):
    if not trades:
        return
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=trades[0].keys())
        writer.writeheader()
        writer.writerows(trades)
    print(f'Saved {len(trades)} trades to {path}')


def load_trades_csv(path):
    trades = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k in ['entry_price', 'exit_price', 'quantity', 'gross_pnl', 'pnl_pct', 'duration_min']:
                if k in row:
                    row[k] = float(row[k])
            if 'entry_hour' in row:
                row['entry_hour'] = int(float(row['entry_hour']))
            # Handle old format: exit_tag → exit_reason
            if 'exit_tag' in row and 'exit_reason' not in row:
                row['exit_reason'] = row.pop('exit_tag') or 'unknown'
            trades.append(row)
    return trades


# ── Analysis Functions ─────────────────────────────────────────

def print_header(title):
    print(f'\n{"=" * 50}')
    print(f'  {title}')
    print(f'{"=" * 50}')


def overall_summary(trades):
    print_header('OVERALL PERFORMANCE')
    wins = [t for t in trades if t['gross_pnl'] > 0]
    losses = [t for t in trades if t['gross_pnl'] <= 0]
    total = sum(t['gross_pnl'] for t in trades)
    gross_win = sum(t['gross_pnl'] for t in wins)
    gross_loss = abs(sum(t['gross_pnl'] for t in losses))
    avg_w = gross_win / len(wins) if wins else 0
    avg_l = -gross_loss / len(losses) if losses else 0
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')

    print(f'Trades:        {len(trades)}')
    print(f'Winners:       {len(wins)} ({len(wins)/len(trades)*100:.1f}%)')
    print(f'Losers:        {len(losses)} ({len(losses)/len(trades)*100:.1f}%)')
    print(f'Net PnL:       ${total:,.2f}')
    print(f'Gross Profit:  ${gross_win:,.2f}')
    print(f'Gross Loss:    ${gross_loss:,.2f}')
    print(f'Profit Factor: {pf:.2f}')
    if avg_l != 0:
        print(f'Avg Win:       ${avg_w:,.2f} | Avg Loss: ${avg_l:,.2f} | P/L Ratio: {abs(avg_w/avg_l):.2f}')
    print(f'Avg Duration:  {sum(t["duration_min"] for t in trades)/len(trades):.0f} min')


def direction_analysis(trades):
    print_header('BY DIRECTION')
    for d in ['LONG', 'SHORT']:
        dt = [t for t in trades if t['direction'] == d]
        if not dt:
            continue
        dw = [t for t in dt if t['gross_pnl'] > 0]
        dl = [t for t in dt if t['gross_pnl'] <= 0]
        dp = sum(t['gross_pnl'] for t in dt)
        aw = sum(t['gross_pnl'] for t in dw) / len(dw) if dw else 0
        al = sum(t['gross_pnl'] for t in dl) / len(dl) if dl else 0
        print(f'{d:5s}: {len(dt):3d} trades | WR: {len(dw)/len(dt)*100:.1f}% | PnL: ${dp:>8,.2f} | AvgW: ${aw:.2f} | AvgL: ${al:.2f}')


def exit_reason_analysis(trades):
    print_header('BY EXIT REASON')
    reasons = defaultdict(list)
    for t in trades:
        reasons[t.get('exit_reason', 'unknown')].append(t)
    for reason in sorted(reasons, key=lambda x: sum(t['gross_pnl'] for t in reasons[x])):
        tt = reasons[reason]
        tw = [t for t in tt if t['gross_pnl'] > 0]
        tp = sum(t['gross_pnl'] for t in tt)
        avg = tp / len(tt)
        print(f'{reason:20s}: {len(tt):3d} trades | WR: {len(tw)/len(tt)*100:.0f}% | PnL: ${tp:>8,.2f} | Avg: ${avg:>6,.2f}')


def monthly_analysis(trades):
    print_header('BY MONTH')
    months = sorted(set(t['month'] for t in trades if t['month']))
    cum = 0
    for m in months:
        mt = [t for t in trades if t['month'] == m]
        mw = [t for t in mt if t['gross_pnl'] > 0]
        mp = sum(t['gross_pnl'] for t in mt)
        cum += mp
        bar = '+' * max(0, int(mp / 50)) if mp > 0 else '-' * max(0, int(abs(mp) / 50))
        print(f'{m}: {len(mt):3d} trades | WR: {len(mw)/len(mt)*100:.0f}% | PnL: ${mp:>8,.2f} | Cum: ${cum:>9,.2f} {bar}')


def day_of_week_analysis(trades):
    print_header('BY DAY OF WEEK')
    for dow in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
        dt = [t for t in trades if t['entry_dow'] == dow]
        if not dt:
            continue
        dw = [t for t in dt if t['gross_pnl'] > 0]
        dp = sum(t['gross_pnl'] for t in dt)
        print(f'{dow:10s}: {len(dt):3d} trades | WR: {len(dw)/len(dt)*100:.0f}% | PnL: ${dp:>8,.2f}')


def symbol_analysis(trades):
    print_header('SYMBOL PERFORMANCE (Top 10 / Bottom 10)')
    sym_data = defaultdict(lambda: {'pnl': 0, 'trades': 0, 'wins': 0})
    for t in trades:
        sym_data[t['symbol']]['pnl'] += t['gross_pnl']
        sym_data[t['symbol']]['trades'] += 1
        if t['gross_pnl'] > 0:
            sym_data[t['symbol']]['wins'] += 1

    ranked = sorted(sym_data.items(), key=lambda x: x[1]['pnl'], reverse=True)
    print('BEST:')
    for sym, d in ranked[:10]:
        wr = d['wins'] / d['trades'] * 100
        print(f'  {sym:6s}: {d["trades"]:3d} trades | WR: {wr:.0f}% | PnL: ${d["pnl"]:>8,.2f}')
    print('WORST:')
    for sym, d in ranked[-10:]:
        wr = d['wins'] / d['trades'] * 100
        print(f'  {sym:6s}: {d["trades"]:3d} trades | WR: {wr:.0f}% | PnL: ${d["pnl"]:>8,.2f}')


def duration_analysis(trades):
    print_header('BY TRADE DURATION')
    for label, lo, hi in [('< 2 min', 0, 2), ('2-5 min', 2, 5), ('5-15 min', 5, 15),
                           ('15-60 min', 15, 60), ('60-180 min', 60, 180), ('180+ min', 180, 9999)]:
        dt = [t for t in trades if lo <= t['duration_min'] < hi]
        if not dt:
            continue
        dw = [t for t in dt if t['gross_pnl'] > 0]
        dp = sum(t['gross_pnl'] for t in dt)
        print(f'{label:12s}: {len(dt):3d} trades | WR: {len(dw)/len(dt)*100:.0f}% | PnL: ${dp:>8,.2f}')


def entry_hour_analysis(trades):
    print_header('BY ENTRY HOUR (UTC / ET-4)')
    for h in range(9, 21):
        dt = [t for t in trades if t['entry_hour'] == h]
        if not dt:
            continue
        dw = [t for t in dt if t['gross_pnl'] > 0]
        dp = sum(t['gross_pnl'] for t in dt)
        et_h = h - 4 if h >= 4 else h + 20  # rough UTC→ET
        print(f'{h:02d}:00 UTC ({et_h:02d}:00 ET): {len(dt):3d} trades | WR: {len(dw)/len(dt)*100:.0f}% | PnL: ${dp:>8,.2f}')


def pnl_distribution(trades):
    print_header('PNL DISTRIBUTION')
    buckets = [('< -$100', -99999, -100), ('-$100 to -$50', -100, -50), ('-$50 to -$20', -50, -20),
               ('-$20 to -$5', -20, -5), ('-$5 to $0', -5, 0), ('$0 to $5', 0, 5),
               ('$5 to $20', 5, 20), ('$20 to $50', 20, 50), ('$50 to $100', 50, 100), ('> $100', 100, 99999)]
    for label, lo, hi in buckets:
        dt = [t for t in trades if lo <= t['gross_pnl'] < hi]
        if not dt:
            continue
        dp = sum(t['gross_pnl'] for t in dt)
        print(f'{label:15s}: {len(dt):3d} trades | PnL: ${dp:>8,.2f}')


def equity_curve(trades):
    print_header('EQUITY CURVE')
    sorted_trades = sorted(trades, key=lambda x: x['entry_time'])
    equity = 25000
    peak = equity
    max_dd = 0
    max_dd_date = ''

    for t in sorted_trades:
        equity += t['gross_pnl']
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak
        if dd < max_dd:
            max_dd = dd
            max_dd_date = t.get('entry_date', '')

    print(f'Final Equity:    ${equity:,.2f}')
    print(f'Peak Equity:     ${peak:,.2f}')
    print(f'Max Drawdown:    {max_dd*100:.2f}% on {max_dd_date}')

    # Streaks
    streak = 0
    max_win_streak = max_loss_streak = 0
    for t in sorted_trades:
        if t['gross_pnl'] > 0:
            streak = max(streak, 0) + 1
            max_win_streak = max(max_win_streak, streak)
        else:
            streak = min(streak, 0) - 1
            max_loss_streak = max(max_loss_streak, abs(streak))
    print(f'Max Win Streak:  {max_win_streak}')
    print(f'Max Loss Streak: {max_loss_streak}')

    # Monthly equity curve
    print('\nMonthly Equity:')
    monthly_eq = 25000
    for m in sorted(set(t['month'] for t in sorted_trades if t['month'])):
        mt = [t for t in sorted_trades if t['month'] == m]
        mp = sum(t['gross_pnl'] for t in mt)
        monthly_eq += mp
        print(f'  {m}: ${monthly_eq:>10,.2f}')


def save_summary(trades, path):
    """Save analysis summary to text file."""
    import io
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()

    overall_summary(trades)
    direction_analysis(trades)
    exit_reason_analysis(trades)
    monthly_analysis(trades)
    day_of_week_analysis(trades)
    symbol_analysis(trades)
    duration_analysis(trades)
    entry_hour_analysis(trades)
    pnl_distribution(trades)
    equity_curve(trades)

    sys.stdout = old_stdout
    text = buffer.getvalue()
    with open(path, 'w') as f:
        f.write(text)
    print(f'\nSaved full analysis to {path}')


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='ORB Strategy Backtest Analysis')
    parser.add_argument('--backtest-id', help='Specific backtest ID to analyze')
    parser.add_argument('--local', action='store_true', help='Use existing analysis/paired_trades.csv')
    args = parser.parse_args()

    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    csv_path = os.path.join(ANALYSIS_DIR, 'paired_trades.csv')
    summary_path = os.path.join(ANALYSIS_DIR, 'analysis_summary.txt')

    if args.local:
        print(f'Loading local trades from {csv_path}')
        trades = load_trades_csv(csv_path)
    else:
        import requests  # only import if needed

        bt_id = args.backtest_id
        if not bt_id:
            # Get latest backtest
            auth, headers = qc_auth()
            r = requests.post(
                'https://www.quantconnect.com/api/v2/backtests/read',
                json={'projectId': QC_PROJECT_ID},
                auth=auth, headers=headers
            )
            data = r.json()
            if data.get('success') and data.get('backtests'):
                bt = sorted(data['backtests'], key=lambda x: x.get('created', ''), reverse=True)
                bt_id = bt[0]['backtestId']
                print(f'Using latest backtest: {bt[0].get("name", bt_id)}')
            else:
                print(f'Could not find backtests: {data.get("errors", "unknown error")}')
                sys.exit(1)

        print(f'Fetching orders for backtest {bt_id}...')
        orders = fetch_orders(bt_id)
        print(f'Fetched {len(orders)} orders')

        if not orders:
            print('No orders found.')
            sys.exit(1)

        trades = pair_trades(orders)
        save_trades_csv(trades, csv_path)

    if not trades:
        print('No trades to analyze.')
        sys.exit(1)

    print(f'\nAnalyzing {len(trades)} trades...')

    # Print all analysis
    overall_summary(trades)
    direction_analysis(trades)
    exit_reason_analysis(trades)
    monthly_analysis(trades)
    day_of_week_analysis(trades)
    symbol_analysis(trades)
    duration_analysis(trades)
    entry_hour_analysis(trades)
    pnl_distribution(trades)
    equity_curve(trades)

    # Save to file
    save_summary(trades, summary_path)


if __name__ == '__main__':
    main()
