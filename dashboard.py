#!/usr/bin/env python3
"""
Simple Monitoring Dashboard for Polymarket Bot
Displays real-time paper trading status in the terminal.

Usage:
    python dashboard.py           # Run dashboard
    python dashboard.py --refresh 5  # Refresh every 5 seconds
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def load_state(state_file: Path) -> dict:
    """Load paper trading state from file."""
    if not state_file.exists():
        return None
    
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except Exception:
        return None


def format_currency(value: float) -> str:
    """Format currency with color."""
    if value >= 0:
        return f"{Colors.GREEN}${value:,.2f}{Colors.END}"
    else:
        return f"{Colors.RED}${value:,.2f}{Colors.END}"


def format_pct(value: float, invert: bool = False) -> str:
    """Format percentage with color."""
    if invert:
        value = -value
    if value >= 0:
        return f"{Colors.GREEN}{value:+.1f}%{Colors.END}"
    else:
        return f"{Colors.RED}{value:+.1f}%{Colors.END}"


def draw_bar(value: float, max_value: float, width: int = 20, filled: str = '#', empty: str = '-') -> str:
    """Draw a progress bar."""
    if max_value <= 0:
        return empty * width
    
    fill_width = int(min(1.0, value / max_value) * width)
    return filled * fill_width + empty * (width - fill_width)


def calculate_metrics(state: dict) -> dict:
    """Calculate all dashboard metrics."""
    initial = state.get('initial_capital', 75.0)  # Default to 75 if not present
    capital = state.get('capital', initial)
    positions = state.get('positions', [])
    trades = state.get('closed_trades', [])
    
    # Current values
    invested = sum(p.get('amount', 0) for p in positions)
    unrealized = sum(p.get('unrealized_pnl', 0) for p in positions)
    equity = capital + invested + unrealized
    
    # Returns
    total_return = (equity - initial) / initial * 100
    realized_pnl = sum(t.get('pnl', 0) for t in trades)
    
    # Trade stats
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
    losing_trades = sum(1 for t in trades if t.get('pnl', 0) < 0)
    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
    
    # Average win/loss
    wins = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
    losses = [abs(t['pnl']) for t in trades if t.get('pnl', 0) < 0]
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    profit_factor = sum(wins) / sum(losses) if losses and sum(losses) > 0 else float('inf')
    
    # Drawdown
    max_dd = state.get('max_drawdown', 0) * 100
    current_dd = (state.get('high_water_mark', initial) - equity) / state.get('high_water_mark', initial) * 100
    
    # Time
    try:
        start_time = datetime.fromisoformat(state.get('start_time', datetime.now().isoformat()))
        running_time = datetime.now() - start_time
    except:
        running_time = timedelta(0)
    
    # Recent trades
    recent_trades = sorted(trades, key=lambda t: t.get('exit_time', ''), reverse=True)[:5]
    
    return {
        'initial': initial,
        'capital': capital,
        'invested': invested,
        'unrealized': unrealized,
        'equity': equity,
        'total_return': total_return,
        'realized_pnl': realized_pnl,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_dd': max_dd,
        'current_dd': current_dd,
        'positions': positions,
        'recent_trades': recent_trades,
        'running_time': running_time,
        'high_water_mark': state.get('high_water_mark', initial),
    }


def render_dashboard(state: dict):
    """Render the dashboard."""
    if not state:
        print(f"\n{Colors.YELLOW}No paper trading state found.{Colors.END}")
        print("Run: python paper_trade_runner.py")
        return
    
    m = calculate_metrics(state)
    
    # Header
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  POLYMARKET BOT - PAPER TRADING DASHBOARD{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"  Last Update: {state.get('last_update', 'N/A')}")
    print(f"  Running: {str(m['running_time']).split('.')[0]}")
    
    # Account Overview
    print(f"\n{Colors.BOLD}  ACCOUNT OVERVIEW{Colors.END}")
    print(f"  {'-' * 40}")
    
    equity_bar = draw_bar(m['equity'], m['initial'] * 2)
    print(f"  Initial Capital:  ${m['initial']:.2f}")
    print(f"  Current Equity:   {format_currency(m['equity'])} [{equity_bar}]")
    print(f"  Available:        ${m['capital']:.2f}")
    print(f"  Invested:         ${m['invested']:.2f}")
    print(f"  Total Return:     {format_pct(m['total_return'])}")
    
    # PnL
    print(f"\n{Colors.BOLD}  PROFIT & LOSS{Colors.END}")
    print(f"  {'-' * 40}")
    print(f"  Realized PnL:     {format_currency(m['realized_pnl'])}")
    print(f"  Unrealized PnL:   {format_currency(m['unrealized'])}")
    print(f"  High Water Mark:  ${m['high_water_mark']:.2f}")
    
    # Risk
    print(f"\n{Colors.BOLD}  RISK METRICS{Colors.END}")
    print(f"  {'-' * 40}")
    dd_bar = draw_bar(m['current_dd'], 35)
    max_dd_bar = draw_bar(m['max_dd'], 35)
    print(f"  Current Drawdown: {format_pct(m['current_dd'], invert=True)} [{dd_bar}]")
    print(f"  Max Drawdown:     {format_pct(m['max_dd'], invert=True)} [{max_dd_bar}]")
    
    # Trading Stats
    print(f"\n{Colors.BOLD}  TRADING STATISTICS{Colors.END}")
    print(f"  {'-' * 40}")
    print(f"  Total Trades:     {m['total_trades']}")
    print(f"  Wins/Losses:      {Colors.GREEN}{m['winning_trades']}{Colors.END} / {Colors.RED}{m['losing_trades']}{Colors.END}")
    win_bar = draw_bar(m['win_rate'], 100)
    print(f"  Win Rate:         {format_pct(m['win_rate'] - 50)} [{win_bar}] {m['win_rate']:.1f}%")
    print(f"  Avg Win:          {format_currency(m['avg_win'])}")
    print(f"  Avg Loss:         {format_currency(-m['avg_loss'])}")
    pf_str = f"{m['profit_factor']:.2f}" if m['profit_factor'] < float('inf') else "INF"
    print(f"  Profit Factor:    {pf_str}")
    
    # Open Positions
    print(f"\n{Colors.BOLD}  OPEN POSITIONS ({len(m['positions'])}){Colors.END}")
    print(f"  {'-' * 40}")
    
    if not m['positions']:
        print(f"  {Colors.YELLOW}No open positions{Colors.END}")
    else:
        for p in m['positions']:
            pnl = p.get('unrealized_pnl', 0)
            pnl_pct = pnl / p['amount'] * 100 if p['amount'] > 0 else 0
            direction_color = Colors.GREEN if p['direction'] == 'YES' else Colors.RED
            pnl_str = format_currency(pnl)
            
            print(f"  {direction_color}{p['direction']}{Colors.END} ${p['amount']:.2f} @ {p['entry_price']:.2f}")
            print(f"      Now: {p.get('current_price', p['entry_price']):.2f} | PnL: {pnl_str} ({pnl_pct:+.1f}%)")
            print(f"      {p.get('market_question', 'Unknown')[:50]}")
    
    # Recent Trades
    print(f"\n{Colors.BOLD}  RECENT TRADES{Colors.END}")
    print(f"  {'-' * 40}")
    
    if not m['recent_trades']:
        print(f"  {Colors.YELLOW}No completed trades{Colors.END}")
    else:
        for t in m['recent_trades'][:5]:
            pnl = t.get('pnl', 0)
            result = f"{Colors.GREEN}WIN{Colors.END}" if pnl > 0 else f"{Colors.RED}LOSS{Colors.END}"
            exit_time = t.get('exit_time', '')[:16].replace('T', ' ')
            
            print(f"  [{result}] {format_currency(pnl)} | {t.get('reason', 'N/A')}")
            print(f"      {t.get('direction', '?')} ${t.get('amount', 0):.2f} | {exit_time}")
    
    # Footer
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"  {Colors.YELLOW}Press Ctrl+C to exit{Colors.END}")


def main():
    parser = argparse.ArgumentParser(description="Paper Trading Dashboard")
    parser.add_argument('--refresh', type=int, default=5, help='Refresh interval in seconds')
    parser.add_argument('--state-file', type=str, default='./data/paper_trader_v2_state.json', 
                       help='Path to state file')
    
    args = parser.parse_args()
    state_file = Path(args.state_file)
    
    # Also check alternative state files
    alt_state_files = [
        Path('./data/paper_trader_v2_state.json'),
        Path('./data/swing_trader_state.json'),
        Path('./data/edge_aware_paper_state.json'),
    ]
    
    print(f"Watching: {state_file}")
    print(f"Refresh: every {args.refresh} seconds")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            clear_screen()
            
            # Try primary state file, then alternatives
            state = load_state(state_file)
            if not state:
                for alt_file in alt_state_files:
                    state = load_state(alt_file)
                    if state:
                        break
            
            render_dashboard(state)
            
            time.sleep(args.refresh)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Dashboard stopped.{Colors.END}")


if __name__ == '__main__':
    main()
