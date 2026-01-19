#!/usr/bin/env python3
"""
Paper Trading Runner - Uses Edge-Aware Strategy
Run this script to start paper trading with the validated strategy.

Usage:
    python paper_trade_runner.py                    # Start with defaults
    python paper_trade_runner.py --capital 100     # Start with $100
    python paper_trade_runner.py --status          # Show current status
    python paper_trade_runner.py --reset           # Reset account
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('paper_trading.log'),
    ]
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))


@dataclass
class PaperTradeState:
    """Persistent paper trading state."""
    initial_capital: float
    capital: float
    positions: List[Dict]
    closed_trades: List[Dict]
    trade_counter: int
    high_water_mark: float
    max_drawdown: float
    start_time: str
    last_update: str


class EdgeAwarePaperTrader:
    """
    Paper trader using the validated Edge-Aware strategy.
    """
    
    def __init__(self, initial_capital: float = 75.0, data_dir: str = "./data"):
        self.initial_capital = initial_capital
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "edge_aware_paper_state.json"
        
        # Load or initialize state
        self.state = self._load_state()
        
        # Strategy configuration (validated parameters)
        self.config = {
            'min_edge': 0.03,
            'min_confidence': 0.42,
            'volatile_min_edge': 0.06,
            'volatile_min_confidence': 0.50,
            'base_position_pct': 0.08,
            'max_position_pct': 0.12,
            'min_position': 3.0,
            'max_position': 12.0,
            'max_spread': 0.12,
            'min_volume': 200,
            'max_concurrent_positions': 8,
            'max_exposure_pct': 0.80,
            'take_profit_pct': 0.50,  # 50% gain
            'stop_loss_pct': 0.30,    # 30% loss
        }
        
        # Try to import live data clients
        self._setup_clients()
    
    def _setup_clients(self):
        """Setup data clients with fallback to simulated data."""
        try:
            from data.polymarket_client import PolymarketClient
            from data.news_aggregator import NewsAggregator
            from analysis.sentiment_analyzer import SentimentAnalyzer
            
            self.client = PolymarketClient()
            self.news_aggregator = NewsAggregator()
            self.sentiment_analyzer = SentimentAnalyzer()
            self.live_data = True
            logger.info("Connected to live Polymarket data")
        except Exception as e:
            logger.warning(f"Live data unavailable: {e}")
            logger.info("Using simulated market data")
            self.live_data = False
            self.client = None
            self.news_aggregator = None
            self.sentiment_analyzer = None
    
    def _load_state(self) -> PaperTradeState:
        """Load state from disk or create new."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded state: ${data['capital']:.2f} capital, {len(data['positions'])} positions")
                return PaperTradeState(
                    initial_capital=data['initial_capital'],
                    capital=data['capital'],
                    positions=data['positions'],
                    closed_trades=data['closed_trades'],
                    trade_counter=data['trade_counter'],
                    high_water_mark=data['high_water_mark'],
                    max_drawdown=data['max_drawdown'],
                    start_time=data['start_time'],
                    last_update=data['last_update'],
                )
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        
        # New state
        return PaperTradeState(
            initial_capital=self.initial_capital,
            capital=self.initial_capital,
            positions=[],
            closed_trades=[],
            trade_counter=0,
            high_water_mark=self.initial_capital,
            max_drawdown=0.0,
            start_time=datetime.now().isoformat(),
            last_update=datetime.now().isoformat(),
        )
    
    def _save_state(self):
        """Save state to disk."""
        self.state.last_update = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump({
                'initial_capital': self.state.initial_capital,
                'capital': self.state.capital,
                'positions': self.state.positions,
                'closed_trades': self.state.closed_trades,
                'trade_counter': self.state.trade_counter,
                'high_water_mark': self.state.high_water_mark,
                'max_drawdown': self.state.max_drawdown,
                'start_time': self.state.start_time,
                'last_update': self.state.last_update,
            }, f, indent=2, default=str)
    
    def reset(self):
        """Reset the paper trading account."""
        self.state = PaperTradeState(
            initial_capital=self.initial_capital,
            capital=self.initial_capital,
            positions=[],
            closed_trades=[],
            trade_counter=0,
            high_water_mark=self.initial_capital,
            max_drawdown=0.0,
            start_time=datetime.now().isoformat(),
            last_update=datetime.now().isoformat(),
        )
        self._save_state()
        logger.info("Account reset to initial state")
    
    def get_status(self) -> Dict:
        """Get current account status."""
        # Calculate metrics
        invested = sum(p['amount'] for p in self.state.positions)
        unrealized_pnl = sum(p.get('unrealized_pnl', 0) for p in self.state.positions)
        total_equity = self.state.capital + invested + unrealized_pnl
        
        total_trades = len(self.state.closed_trades)
        winning_trades = sum(1 for t in self.state.closed_trades if t.get('pnl', 0) > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        total_pnl = sum(t.get('pnl', 0) for t in self.state.closed_trades)
        
        # Time running
        start = datetime.fromisoformat(self.state.start_time)
        running_time = datetime.now() - start
        
        return {
            'initial_capital': self.state.initial_capital,
            'current_capital': round(self.state.capital, 2),
            'invested': round(invested, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_equity': round(total_equity, 2),
            'realized_pnl': round(total_pnl, 2),
            'total_return_pct': round((total_equity - self.state.initial_capital) / self.state.initial_capital * 100, 1),
            'open_positions': len(self.state.positions),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate_pct': round(win_rate * 100, 1),
            'max_drawdown_pct': round(self.state.max_drawdown * 100, 1),
            'running_time': str(running_time).split('.')[0],
        }
    
    def _detect_regime(self, market_data: Dict) -> str:
        """Detect market regime."""
        sentiment = market_data.get('sentiment', 0)
        price = market_data.get('price', 0.5)
        volume = market_data.get('volume', 0)
        
        # Sentiment trap detection
        if abs(sentiment) > 0.3 and abs(sentiment - (price - 0.5) * 2) > 0.5:
            return 'trap'
        
        # High volume = news driven
        if volume > 1000:
            return 'news_driven'
        
        # Trending
        if price > 0.7 or price < 0.3:
            return 'trending'
        
        # Volatile
        spread = market_data.get('spread', 0.05)
        if spread > 0.08:
            return 'volatile'
        
        return 'ranging'
    
    def _calculate_signal(self, market_data: Dict) -> Optional[Dict]:
        """Calculate trading signal using edge-aware strategy."""
        regime = self._detect_regime(market_data)
        
        # Skip traps and ranging markets
        if regime in ['trap', 'ranging']:
            return None
        
        sentiment = market_data.get('sentiment', 0)
        price = market_data.get('price', 0.5)
        spread = market_data.get('spread', 0.05)
        
        # Check spread
        if spread > self.config['max_spread']:
            return None
        
        # Calculate edge
        implied_prob = 0.5 + sentiment * 0.4
        implied_prob = max(0.1, min(0.9, implied_prob))
        
        edge = abs(implied_prob - price)
        
        # Adjust thresholds for volatile regime
        min_edge = self.config['volatile_min_edge'] if regime == 'volatile' else self.config['min_edge']
        min_conf = self.config['volatile_min_confidence'] if regime == 'volatile' else self.config['min_confidence']
        
        confidence = min(0.8, 0.4 + abs(sentiment) * 0.5)
        
        if edge < min_edge or confidence < min_conf:
            return None
        
        direction = 'YES' if implied_prob > price else 'NO'
        trade_price = price if direction == 'YES' else (1 - price)
        
        # Position sizing
        base_pct = self.config['base_position_pct']
        if regime == 'news_driven' and edge > 0.08:
            position_pct = self.config['max_position_pct']
        elif regime == 'volatile':
            position_pct = base_pct * 0.6
        else:
            position_pct = base_pct
        
        amount = self.state.capital * position_pct
        amount = max(self.config['min_position'], min(self.config['max_position'], amount))
        
        # Check exposure limits
        invested = sum(p['amount'] for p in self.state.positions)
        max_exposure = self.state.initial_capital * self.config['max_exposure_pct']
        if invested + amount > max_exposure:
            return None
        
        # Check position count
        if len(self.state.positions) >= self.config['max_concurrent_positions']:
            return None
        
        return {
            'direction': direction,
            'price': trade_price,
            'amount': round(amount, 2),
            'edge': round(edge, 3),
            'confidence': round(confidence, 3),
            'regime': regime,
        }
    
    def _get_live_opportunities(self) -> List[Dict]:
        """Get opportunities from live market data."""
        if not self.live_data:
            return []
        
        opportunities = []
        
        try:
            markets = self.client.get_active_markets(
                limit=50,
                min_volume=self.config['min_volume']
            )
            
            for market in markets[:20]:
                # Get sentiment
                market_news = self.news_aggregator.get_market_news(
                    market.question,
                    market_keywords=market.question.split()[:5]
                )
                
                if market_news:
                    news_texts = [f"{n.title} {n.content}" for n in market_news[:5]]
                    sentiment_result = self.sentiment_analyzer.analyze(" ".join(news_texts))
                    sentiment = sentiment_result.compound_score
                else:
                    sentiment = 0
                
                # Get order book for spread
                spread = 0.05
                if market.yes_token_id:
                    order_book = self.client.get_order_book(market.yes_token_id)
                    if order_book:
                        spread = order_book.spread
                
                market_data = {
                    'id': market.id,
                    'question': market.question,
                    'price': market.yes_price,
                    'sentiment': sentiment,
                    'spread': spread,
                    'volume': market.volume_24h,
                    'yes_token_id': market.yes_token_id,
                    'no_token_id': market.no_token_id,
                }
                
                signal = self._calculate_signal(market_data)
                if signal:
                    opportunities.append({
                        **market_data,
                        **signal,
                    })
                    
        except Exception as e:
            logger.error(f"Error fetching live opportunities: {e}")
        
        return sorted(opportunities, key=lambda x: x['edge'], reverse=True)
    
    def _get_simulated_opportunities(self) -> List[Dict]:
        """Generate simulated market opportunities for testing."""
        opportunities = []
        
        market_templates = [
            "Will Bitcoin reach $100k?",
            "Will Fed cut rates?",
            "Will Tesla stock rise?",
            "Will inflation drop below 3%?",
            "Will unemployment stay below 5%?",
            "Will GDP growth exceed 2%?",
            "Will housing prices fall?",
            "Will oil prices rise?",
            "Will S&P 500 hit new high?",
            "Will gold reach $2500?",
        ]
        
        for i, template in enumerate(market_templates):
            # Simulate market conditions
            price = random.uniform(0.25, 0.75)
            sentiment = random.uniform(-0.5, 0.5)
            spread = random.uniform(0.02, 0.10)
            volume = random.uniform(100, 2000)
            
            market_data = {
                'id': f'sim-market-{i}',
                'question': template,
                'price': price,
                'sentiment': sentiment,
                'spread': spread,
                'volume': volume,
                'yes_token_id': f'yes-{i}',
                'no_token_id': f'no-{i}',
            }
            
            signal = self._calculate_signal(market_data)
            if signal:
                opportunities.append({
                    **market_data,
                    **signal,
                })
        
        return sorted(opportunities, key=lambda x: x['edge'], reverse=True)
    
    def _update_positions(self):
        """Update position prices and check for exits."""
        for position in list(self.state.positions):
            # Simulate price movement
            if not self.live_data:
                # Random walk with drift toward resolution
                current_price = position.get('current_price', position['entry_price'])
                drift = 0.01 if random.random() > 0.5 else -0.01
                noise = random.gauss(0, 0.02)
                new_price = current_price + drift + noise
                new_price = max(0.01, min(0.99, new_price))
            else:
                # Get live price
                try:
                    token_id = position.get('yes_token_id') if position['direction'] == 'YES' else position.get('no_token_id')
                    new_price = self.client.get_price(token_id, side="sell") or position['entry_price']
                except Exception:
                    new_price = position.get('current_price', position['entry_price'])
            
            # Update position
            position['current_price'] = new_price
            shares = position['amount'] / position['entry_price']
            position['unrealized_pnl'] = shares * new_price - position['amount']
            
            # Check for exit conditions
            return_pct = position['unrealized_pnl'] / position['amount']
            
            should_close = False
            close_reason = None
            
            # Resolution (price near 0 or 1)
            if new_price >= 0.95 or new_price <= 0.05:
                should_close = True
                close_reason = 'resolution'
            # Take profit
            elif return_pct >= self.config['take_profit_pct']:
                should_close = True
                close_reason = 'take_profit'
            # Stop loss
            elif return_pct <= -self.config['stop_loss_pct']:
                should_close = True
                close_reason = 'stop_loss'
            # Time-based exit (after 24 hours in simulation)
            elif not self.live_data:
                entry_time = datetime.fromisoformat(position['entry_time'])
                if datetime.now() - entry_time > timedelta(hours=24):
                    should_close = True
                    close_reason = 'time_exit'
            
            if should_close and close_reason:
                self._close_position(position, new_price, close_reason)
    
    def _close_position(self, position: Dict, exit_price: float, reason: str):
        """Close a position and record the trade."""
        shares = position['amount'] / position['entry_price']
        
        # Calculate PnL based on exit type
        if exit_price >= 0.95:  # Win
            pnl = shares * 1.0 - position['amount']
        elif exit_price <= 0.05:  # Lose
            pnl = -position['amount']
        else:  # Sold before resolution
            pnl = shares * exit_price - position['amount']
        
        # Apply Polymarket fee (2% on profits only)
        if pnl > 0:
            pnl *= 0.98
        
        # Record trade
        trade = {
            'trade_id': f"TRADE-{position['position_id']}",
            'market_id': position['market_id'],
            'market_question': position['market_question'],
            'direction': position['direction'],
            'entry_time': position['entry_time'],
            'exit_time': datetime.now().isoformat(),
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'amount': position['amount'],
            'pnl': round(pnl, 2),
            'return_pct': round(pnl / position['amount'] * 100, 1),
            'reason': reason,
        }
        
        self.state.closed_trades.append(trade)
        
        # Update capital
        self.state.capital += position['amount'] + pnl
        
        # Update high water mark and drawdown
        if self.state.capital > self.state.high_water_mark:
            self.state.high_water_mark = self.state.capital
        
        current_dd = (self.state.high_water_mark - self.state.capital) / self.state.high_water_mark
        if current_dd > self.state.max_drawdown:
            self.state.max_drawdown = current_dd
        
        # Remove position
        self.state.positions = [p for p in self.state.positions if p['position_id'] != position['position_id']]
        
        result = "WIN" if pnl > 0 else "LOSS"
        logger.info(f"CLOSED [{reason}] {result}: ${pnl:+.2f} ({trade['return_pct']:+.1f}%) - {position['market_question'][:40]}")
    
    def _open_position(self, opportunity: Dict) -> bool:
        """Open a new position."""
        if opportunity['amount'] > self.state.capital:
            return False
        
        self.state.trade_counter += 1
        position_id = f"PAPER-{self.state.trade_counter}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        position = {
            'position_id': position_id,
            'market_id': opportunity['id'],
            'market_question': opportunity['question'],
            'direction': opportunity['direction'],
            'entry_time': datetime.now().isoformat(),
            'entry_price': opportunity['price'],
            'current_price': opportunity['price'],
            'amount': opportunity['amount'],
            'edge': opportunity['edge'],
            'confidence': opportunity['confidence'],
            'regime': opportunity['regime'],
            'unrealized_pnl': 0,
            'yes_token_id': opportunity.get('yes_token_id'),
            'no_token_id': opportunity.get('no_token_id'),
        }
        
        self.state.positions.append(position)
        self.state.capital -= opportunity['amount']
        
        logger.info(f"OPENED: {opportunity['direction']} ${opportunity['amount']:.2f} @ {opportunity['price']:.2f} "
                   f"(edge={opportunity['edge']:.1%}, {opportunity['regime']}) - {opportunity['question'][:40]}")
        
        return True
    
    def run_cycle(self) -> Dict:
        """Run one trading cycle."""
        cycle_start = datetime.now()
        
        # Update existing positions
        self._update_positions()
        
        # Get new opportunities
        if self.live_data:
            opportunities = self._get_live_opportunities()
        else:
            opportunities = self._get_simulated_opportunities()
        
        # Open new positions
        positions_opened = 0
        for opp in opportunities[:2]:  # Max 2 per cycle
            if self._open_position(opp):
                positions_opened += 1
        
        # Save state
        self._save_state()
        
        return {
            'timestamp': cycle_start.isoformat(),
            'opportunities_found': len(opportunities),
            'positions_opened': positions_opened,
            'open_positions': len(self.state.positions),
            'status': self.get_status(),
        }
    
    def run(self, interval_minutes: int = 15):
        """Run the paper trading loop."""
        print("\n" + "=" * 60)
        print("EDGE-AWARE PAPER TRADING")
        print("=" * 60)
        print(f"\nCapital: ${self.state.capital:.2f}")
        print(f"Data source: {'Live Polymarket' if self.live_data else 'Simulated'}")
        print(f"Scan interval: {interval_minutes} minutes")
        print("Press Ctrl+C to stop\n")
        
        try:
            while True:
                result = self.run_cycle()
                
                status = result['status']
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cycle complete")
                print(f"  Opportunities: {result['opportunities_found']}")
                print(f"  Opened: {result['positions_opened']} | Open: {result['open_positions']}")
                print(f"  Capital: ${status['current_capital']:.2f} | Return: {status['total_return_pct']:+.1f}%")
                print(f"  Win Rate: {status['win_rate_pct']:.1f}% ({status['winning_trades']}/{status['total_trades']})")
                
                print(f"\nSleeping {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\n\nStopping...")
            self._save_state()
            
            status = self.get_status()
            print("\n" + "=" * 60)
            print("FINAL STATUS")
            print("=" * 60)
            for key, value in status.items():
                print(f"  {key}: {value}")


def print_status(trader: EdgeAwarePaperTrader):
    """Print formatted status."""
    status = trader.get_status()
    
    print("\n" + "=" * 60)
    print("PAPER TRADING STATUS")
    print("=" * 60)
    
    print("\nACCOUNT:")
    print(f"  Initial Capital:  ${status['initial_capital']:.2f}")
    print(f"  Current Capital:  ${status['current_capital']:.2f}")
    print(f"  Invested:         ${status['invested']:.2f}")
    print(f"  Total Equity:     ${status['total_equity']:.2f}")
    print(f"  Total Return:     {status['total_return_pct']:+.1f}%")
    
    print("\nPERFORMANCE:")
    print(f"  Realized PnL:     ${status['realized_pnl']:+.2f}")
    print(f"  Unrealized PnL:   ${status['unrealized_pnl']:+.2f}")
    print(f"  Win Rate:         {status['win_rate_pct']:.1f}%")
    print(f"  Total Trades:     {status['total_trades']}")
    print(f"  Max Drawdown:     {status['max_drawdown_pct']:.1f}%")
    
    print("\nPOSITIONS:")
    print(f"  Open:             {status['open_positions']}")
    
    if trader.state.positions:
        print("\n  Current Positions:")
        for p in trader.state.positions:
            pnl = p.get('unrealized_pnl', 0)
            pnl_pct = pnl / p['amount'] * 100 if p['amount'] > 0 else 0
            print(f"    {p['direction']} ${p['amount']:.2f} @ {p['entry_price']:.2f} -> {p.get('current_price', p['entry_price']):.2f}")
            print(f"      PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%) | {p['market_question'][:40]}")
    
    print(f"\nRunning Time: {status['running_time']}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Edge-Aware Paper Trading Runner")
    parser.add_argument('--capital', type=float, default=75.0, help='Starting capital (default: $75)')
    parser.add_argument('--interval', type=int, default=15, help='Scan interval in minutes (default: 15)')
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--reset', action='store_true', help='Reset account')
    
    args = parser.parse_args()
    
    trader = EdgeAwarePaperTrader(initial_capital=args.capital)
    
    if args.reset:
        trader.reset()
        print("Account reset!")
        return
    
    if args.status:
        print_status(trader)
        return
    
    # Run trading loop
    trader.run(interval_minutes=args.interval)


if __name__ == '__main__':
    main()
