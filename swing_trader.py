#!/usr/bin/env python3
"""
Swing Trader - Buy Low, Sell High Strategy
Uses Grok AI, Reddit sentiment, and price history for swing trading.

Usage:
    python swing_trader.py                  # Start trading
    python swing_trader.py --status         # Check status
    python swing_trader.py --reset          # Reset account
    python swing_trader.py --interval 10    # 10 minute cycles
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('swing_trader.log'),
    ]
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load environment
from dotenv import load_dotenv
load_dotenv()


class SwingTrader:
    """
    Swing trader using Grok AI, Reddit, and price history.
    
    Strategy: Buy on dips, sell on recovery.
    """
    
    def __init__(self, initial_capital: float = 75.0, data_dir: str = "./data",
                 openrouter_api_key: Optional[str] = None):
        """
        Initialize the swing trader.
        
        Args:
            initial_capital: Starting capital
            data_dir: Directory for data storage
            openrouter_api_key: API key for Grok via OpenRouter
        """
        self.initial_capital = initial_capital
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "swing_trader_state.json"
        
        # API key for Grok
        self.openrouter_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        
        # Initialize components
        self._setup_components()
        
        # Load state
        self.state = self._load_state()
    
    def _setup_components(self):
        """Initialize all trading components."""
        # Price tracker
        try:
            from data.price_tracker import PriceTracker
            self.price_tracker = PriceTracker(str(self.data_dir))
            logger.info("Price tracker initialized")
        except Exception as e:
            logger.warning(f"Price tracker init failed: {e}")
            self.price_tracker = None
        
        # Grok analyzer
        try:
            from analysis.grok_analyzer import GrokAnalyzer
            self.grok = GrokAnalyzer(self.openrouter_key)
            if self.grok.is_available():
                logger.info("Grok AI analyzer initialized")
            else:
                logger.warning("Grok API key not available")
                self.grok = None
        except Exception as e:
            logger.warning(f"Grok init failed: {e}")
            self.grok = None
        
        # Reddit scraper
        try:
            from data.reddit_scraper import RedditScraper
            self.reddit = RedditScraper()
            logger.info("Reddit scraper initialized")
        except Exception as e:
            logger.warning(f"Reddit scraper init failed: {e}")
            self.reddit = None
        
        # Polymarket client
        try:
            from data.polymarket_client import PolymarketClient
            self.polymarket = PolymarketClient()
            logger.info("Polymarket client initialized")
        except Exception as e:
            logger.warning(f"Polymarket client init failed: {e}")
            self.polymarket = None
        
        # Swing strategy
        try:
            from strategies.swing_strategy import SwingStrategy, SwingConfig
            self.strategy = SwingStrategy(SwingConfig(
                min_dip_pct=0.08,
                take_profit_pct=0.08,  # Conservative
                stop_loss_pct=0.15,    # Moderate
                max_hold_hours=24,
                use_trailing_stop=True,
                trailing_stop_pct=0.05,
            ))
            logger.info("Swing strategy initialized")
        except Exception as e:
            logger.warning(f"Swing strategy init failed: {e}")
            self.strategy = None
        
        # Sentiment analyzer (fallback)
        try:
            from analysis.sentiment_analyzer import SentimentAnalyzer
            self.sentiment = SentimentAnalyzer()
        except Exception:
            self.sentiment = None
    
    def _load_state(self) -> Dict:
        """Load trading state from disk."""
        default_state = {
            'initial_capital': self.initial_capital,
            'capital': self.initial_capital,
            'positions': [],
            'closed_trades': [],
            'trade_counter': 0,
            'high_water_mark': self.initial_capital,
            'max_drawdown': 0.0,
            'start_time': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'last_price_update': None,
        }
        
        if not self.state_file.exists():
            return default_state
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            logger.info(f"Loaded state: ${state['capital']:.2f} capital, {len(state['positions'])} positions")
            return state
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return default_state
    
    def _save_state(self):
        """Save state to disk."""
        self.state['last_update'] = datetime.now().isoformat()
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def reset(self):
        """Reset the trading account."""
        self.state = {
            'initial_capital': self.initial_capital,
            'capital': self.initial_capital,
            'positions': [],
            'closed_trades': [],
            'trade_counter': 0,
            'high_water_mark': self.initial_capital,
            'max_drawdown': 0.0,
            'start_time': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'last_price_update': None,
        }
        self._save_state()
        logger.info("Account reset")
    
    def get_status(self) -> Dict:
        """Get account status."""
        invested = sum(p['amount'] for p in self.state['positions'])
        unrealized = sum(p.get('unrealized_pnl', 0) for p in self.state['positions'])
        equity = self.state['capital'] + invested + unrealized
        
        trades = self.state['closed_trades']
        total_trades = len(trades)
        winning = sum(1 for t in trades if t.get('pnl', 0) > 0)
        realized_pnl = sum(t.get('pnl', 0) for t in trades)
        
        start = datetime.fromisoformat(self.state['start_time'])
        running = datetime.now() - start
        
        return {
            'initial_capital': self.state['initial_capital'],
            'current_capital': round(self.state['capital'], 2),
            'invested': round(invested, 2),
            'unrealized_pnl': round(unrealized, 2),
            'total_equity': round(equity, 2),
            'realized_pnl': round(realized_pnl, 2),
            'total_return_pct': round((equity - self.state['initial_capital']) / self.state['initial_capital'] * 100, 1),
            'open_positions': len(self.state['positions']),
            'total_trades': total_trades,
            'winning_trades': winning,
            'win_rate_pct': round(winning / total_trades * 100, 1) if total_trades > 0 else 0,
            'max_drawdown_pct': round(self.state['max_drawdown'] * 100, 1),
            'running_time': str(running).split('.')[0],
        }
    
    def _update_price_history(self):
        """Update price history for tracked markets (hourly)."""
        if not self.polymarket or not self.price_tracker:
            return
        
        # Check if we should update (hourly)
        last_update = self.state.get('last_price_update')
        if last_update:
            last = datetime.fromisoformat(last_update)
            if (datetime.now() - last).total_seconds() < 55 * 60:  # Less than 55 min
                return
        
        logger.info("Updating price history...")
        
        try:
            markets = self.polymarket.get_active_markets(limit=100, min_volume=200)
            
            for market in markets:
                self.price_tracker.update_price(
                    market_id=market.id,
                    price=market.yes_price,
                    volume_24h=market.volume_24h
                )
            
            self.price_tracker.save()
            self.state['last_price_update'] = datetime.now().isoformat()
            logger.info(f"Updated prices for {len(markets)} markets")
            
        except Exception as e:
            logger.error(f"Price update failed: {e}")
    
    def _get_sentiment_data(self, market_question: str) -> Dict:
        """Get sentiment data from multiple sources."""
        sentiment_data = {'score': 0, 'sources': []}
        
        # Try Reddit
        if self.reddit:
            try:
                posts = self.reddit.get_market_related_posts(market_question, max_posts=10)
                if posts:
                    # Simple sentiment from post scores
                    avg_score = sum(p.score for p in posts) / len(posts)
                    # High scores = positive sentiment
                    reddit_sentiment = min(1, avg_score / 1000)  # Normalize
                    sentiment_data['reddit_score'] = reddit_sentiment
                    sentiment_data['reddit_posts'] = len(posts)
                    sentiment_data['sources'].append('reddit')
            except Exception as e:
                logger.debug(f"Reddit sentiment failed: {e}")
        
        # Try Grok Twitter/X sentiment (backup when Reddit fails)
        if self.grok and self.grok.is_available() and 'reddit' not in sentiment_data['sources']:
            try:
                # Extract key topic from market question
                topic = self._extract_topic(market_question)
                twitter_data = self.grok.get_twitter_sentiment(topic)
                if twitter_data:
                    twitter_sentiment = twitter_data.get('overall_sentiment', 0)
                    sentiment_data['twitter_score'] = twitter_sentiment
                    sentiment_data['twitter_direction'] = twitter_data.get('trending_direction', 'neutral')
                    sentiment_data['twitter_volume'] = twitter_data.get('volume', 'low')
                    sentiment_data['sources'].append('twitter')
                    logger.debug(f"Twitter sentiment for {topic}: {twitter_sentiment}")
            except Exception as e:
                logger.debug(f"Twitter sentiment failed: {e}")
        
        # Try traditional sentiment analyzer
        if self.sentiment:
            try:
                result = self.sentiment.analyze(market_question)
                sentiment_data['nlp_score'] = result.compound_score
                sentiment_data['sources'].append('nlp')
            except Exception:
                pass
        
        # Combine scores (prioritize Twitter > Reddit > NLP)
        scores = []
        if 'twitter_score' in sentiment_data:
            scores.append(sentiment_data['twitter_score'] * 1.2)  # Weight Twitter higher
        if 'reddit_score' in sentiment_data:
            scores.append(sentiment_data['reddit_score'])
        if 'nlp_score' in sentiment_data:
            scores.append(sentiment_data['nlp_score'] * 0.8)  # Weight NLP lower
        
        if scores:
            sentiment_data['score'] = sum(scores) / len(scores)
        else:
            sentiment_data['score'] = 0
        
        return sentiment_data
    
    def _extract_topic(self, market_question: str) -> str:
        """Extract the main topic from a market question for sentiment search."""
        # Remove common question words
        stop_words = {
            'will', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of',
            'by', 'be', 'is', 'are', 'was', 'were', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'can', 'could',
            'would', 'should', 'may', 'might', 'must', 'shall',
            'this', 'that', 'these', 'those', 'it', 'its',
            'before', 'after', 'during', 'between', 'under', 'over',
            'and', 'or', 'but', 'if', 'then', 'else', 'when', 'where',
            'what', 'which', 'who', 'whom', 'whose', 'why', 'how',
        }
        
        words = market_question.lower().replace('?', '').replace('!', '').split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Return first 3-4 meaningful words as topic
        return ' '.join(keywords[:4])
    
    def _get_grok_analysis(self, market_question: str, price: float, 
                          news: List[str] = None) -> Optional[Dict]:
        """Get Grok AI analysis for a market."""
        if not self.grok or not self.grok.is_available():
            return None
        
        try:
            analysis = self.grok.analyze_market(
                market_question=market_question,
                current_price=price,
                recent_news=news or []
            )
            
            if analysis:
                return {
                    'sentiment_score': analysis.sentiment_score,
                    'confidence': analysis.confidence,
                    'price_direction': analysis.price_direction,
                    'key_factors': analysis.key_factors,
                    'summary': analysis.summary,
                }
        except Exception as e:
            logger.debug(f"Grok analysis failed: {e}")
        
        return None
    
    def _find_opportunities(self) -> List[Dict]:
        """Find buy opportunities."""
        if not self.polymarket:
            return []
        
        opportunities = []
        
        try:
            markets = self.polymarket.get_active_markets(limit=50, min_volume=500)
            logger.info(f"Scanning {len(markets)} markets for opportunities...")
            
            for market in markets[:30]:  # Limit to prevent API overload
                try:
                    # Get price analysis
                    price_analysis = None
                    if self.price_tracker:
                        analysis = self.price_tracker.get_analysis(market.id)
                        if analysis:
                            price_analysis = {
                                'is_dip': analysis.is_dip,
                                'dip_size': analysis.dip_size,
                                'change_24h': analysis.change_24h,
                                'momentum': analysis.momentum,
                            }
                    
                    # Skip if not a dip
                    if not price_analysis or not price_analysis.get('is_dip'):
                        continue
                    
                    # Get sentiment
                    sentiment = self._get_sentiment_data(market.question)
                    
                    # Get Grok analysis (for best opportunities)
                    grok_analysis = None
                    if price_analysis.get('dip_size', 0) >= 0.10:  # Only for big dips
                        grok_analysis = self._get_grok_analysis(
                            market.question, 
                            market.yes_price
                        )
                    
                    # Evaluate entry
                    market_data = {
                        'id': market.id,
                        'question': market.question,
                        'price': market.yes_price,
                        'volume_24h': market.volume_24h,
                        'yes_token_id': market.yes_token_id,
                        'no_token_id': market.no_token_id,
                    }
                    
                    if self.strategy:
                        signal = self.strategy.evaluate_entry(
                            market_data,
                            price_analysis,
                            sentiment,
                            grok_analysis
                        )
                        
                        if signal:
                            opportunities.append({
                                'market_data': market_data,
                                'signal': signal,
                                'price_analysis': price_analysis,
                                'sentiment': sentiment,
                                'grok': grok_analysis,
                            })
                    
                except Exception as e:
                    logger.debug(f"Error analyzing {market.id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Market scan failed: {e}")
        
        # Sort by dip size (biggest dips first)
        opportunities.sort(
            key=lambda x: x['signal'].dip_size or 0,
            reverse=True
        )
        
        return opportunities
    
    def _check_exits(self):
        """Check positions for exit signals."""
        if not self.strategy or not self.polymarket:
            return
        
        for position in list(self.state['positions']):
            try:
                # Get current price
                token_id = position.get('yes_token_id') or position.get('token_id')
                if not token_id:
                    continue
                
                current_price = self.polymarket.get_price(token_id, side="sell")
                if not current_price:
                    continue
                
                # Update position
                shares = position['amount'] / position['entry_price']
                position['current_price'] = current_price
                position['unrealized_pnl'] = shares * current_price - position['amount']
                
                # Evaluate exit
                signal = self.strategy.evaluate_exit(position, current_price)
                
                if signal:
                    self._close_position(position, current_price, signal.reason)
                    
            except Exception as e:
                logger.debug(f"Exit check failed for {position.get('market_id')}: {e}")
    
    def _open_position(self, opportunity: Dict) -> bool:
        """Open a new position."""
        signal = opportunity['signal']
        market = opportunity['market_data']
        
        # Calculate position size
        size = self.strategy.calculate_position_size(
            self.state['capital'],
            signal,
            len(self.state['positions'])
        )
        
        if size < 3:  # Minimum $3
            return False
        
        if size > self.state['capital']:
            return False
        
        # Check exposure limit
        invested = sum(p['amount'] for p in self.state['positions'])
        max_exposure = self.state['initial_capital'] * 0.70
        if invested + size > max_exposure:
            return False
        
        # Create position
        self.state['trade_counter'] += 1
        position = {
            'position_id': f"SWING-{self.state['trade_counter']}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'market_id': market['id'],
            'market_question': market['question'],
            'direction': signal.direction,
            'entry_time': datetime.now().isoformat(),
            'entry_price': market['price'],
            'current_price': market['price'],
            'amount': size,
            'unrealized_pnl': 0,
            'yes_token_id': market.get('yes_token_id'),
            'no_token_id': market.get('no_token_id'),
            'entry_reason': signal.reason,
            'dip_size': signal.dip_size,
        }
        
        self.state['positions'].append(position)
        self.state['capital'] -= size
        
        logger.info(f"OPENED: {signal.direction} ${size:.2f} @ {market['price']:.2f} | {signal.reason}")
        logger.info(f"  Market: {market['question'][:60]}")
        
        return True
    
    def _close_position(self, position: Dict, exit_price: float, reason: str):
        """Close a position."""
        shares = position['amount'] / position['entry_price']
        pnl = shares * exit_price - position['amount']
        
        # Apply Polymarket fee (2% on profits)
        if pnl > 0:
            pnl *= 0.98
        
        return_pct = pnl / position['amount'] * 100
        
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
            'return_pct': round(return_pct, 1),
            'reason': reason,
        }
        self.state['closed_trades'].append(trade)
        
        # Update capital
        self.state['capital'] += position['amount'] + pnl
        
        # Update high water mark and drawdown
        equity = self.state['capital'] + sum(p['amount'] for p in self.state['positions'])
        if equity > self.state['high_water_mark']:
            self.state['high_water_mark'] = equity
        
        dd = (self.state['high_water_mark'] - equity) / self.state['high_water_mark']
        if dd > self.state['max_drawdown']:
            self.state['max_drawdown'] = dd
        
        # Remove position
        self.state['positions'] = [p for p in self.state['positions'] 
                                   if p['position_id'] != position['position_id']]
        
        # Clear trailing stop tracking
        if self.strategy:
            self.strategy.clear_position_high(position['market_id'])
        
        result = "WIN" if pnl > 0 else "LOSS"
        logger.info(f"CLOSED [{reason}]: {result} ${pnl:+.2f} ({return_pct:+.1f}%)")
        logger.info(f"  Market: {position['market_question'][:60]}")
    
    def run_cycle(self) -> Dict:
        """Run one trading cycle."""
        cycle_start = datetime.now()
        result = {
            'timestamp': cycle_start.isoformat(),
            'opportunities_found': 0,
            'positions_opened': 0,
            'positions_closed': 0,
        }
        
        # Update price history (hourly)
        self._update_price_history()
        
        # Check exits first
        initial_positions = len(self.state['positions'])
        self._check_exits()
        result['positions_closed'] = initial_positions - len(self.state['positions'])
        
        # Find opportunities
        opportunities = self._find_opportunities()
        result['opportunities_found'] = len(opportunities)
        
        # Open new positions (max 2 per cycle)
        for opp in opportunities[:2]:
            if self._open_position(opp):
                result['positions_opened'] += 1
        
        # Save state
        self._save_state()
        
        result['status'] = self.get_status()
        return result
    
    def run(self, interval_minutes: int = 10):
        """Run the trading loop."""
        print("\n" + "=" * 60)
        print("SWING TRADER - Buy Low, Sell High")
        print("=" * 60)
        print(f"\nCapital: ${self.state['capital']:.2f}")
        print(f"Grok AI: {'Enabled' if self.grok and self.grok.is_available() else 'Disabled'}")
        print(f"Reddit: {'Enabled' if self.reddit else 'Disabled'}")
        print(f"Interval: {interval_minutes} minutes")
        print("\nPress Ctrl+C to stop\n")
        
        try:
            cycle_count = 0
            while True:
                cycle_count += 1
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cycle {cycle_count}")
                
                result = self.run_cycle()
                status = result['status']
                
                print(f"  Opportunities: {result['opportunities_found']}")
                print(f"  Opened: {result['positions_opened']} | Closed: {result['positions_closed']}")
                print(f"  Open positions: {status['open_positions']}")
                print(f"  Capital: ${status['current_capital']:.2f} | Return: {status['total_return_pct']:+.1f}%")
                print(f"  Win Rate: {status['win_rate_pct']:.1f}% ({status['winning_trades']}/{status['total_trades']})")
                
                # Show positions
                if self.state['positions']:
                    print("\n  Current positions:")
                    for p in self.state['positions']:
                        pnl = p.get('unrealized_pnl', 0)
                        pnl_pct = pnl / p['amount'] * 100 if p['amount'] > 0 else 0
                        print(f"    {p['direction']} ${p['amount']:.2f} @ {p['entry_price']:.2f} "
                              f"-> {p.get('current_price', p['entry_price']):.2f} ({pnl_pct:+.1f}%)")
                
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


def print_status(trader: SwingTrader):
    """Print formatted status."""
    status = trader.get_status()
    
    print("\n" + "=" * 60)
    print("SWING TRADER STATUS")
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
    
    print(f"\nPOSITIONS: {status['open_positions']}")
    
    if trader.state['positions']:
        for p in trader.state['positions']:
            pnl = p.get('unrealized_pnl', 0)
            pnl_pct = pnl / p['amount'] * 100 if p['amount'] > 0 else 0
            print(f"  {p['direction']} ${p['amount']:.2f} @ {p['entry_price']:.2f} "
                  f"-> {p.get('current_price', p['entry_price']):.2f}")
            print(f"    PnL: ${pnl:+.2f} ({pnl_pct:+.1f}%) | {p['market_question'][:50]}")
    
    print(f"\nRunning: {status['running_time']}")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Swing Trader - Buy Low, Sell High")
    parser.add_argument('--capital', type=float, default=75.0, help='Starting capital')
    parser.add_argument('--interval', type=int, default=10, help='Cycle interval in minutes')
    parser.add_argument('--status', action='store_true', help='Show status')
    parser.add_argument('--reset', action='store_true', help='Reset account')
    parser.add_argument('--api-key', type=str, help='OpenRouter API key for Grok')
    
    args = parser.parse_args()
    
    # Get API key from args or environment
    api_key = args.api_key or os.getenv("OPENROUTER_API_KEY")
    
    trader = SwingTrader(
        initial_capital=args.capital,
        openrouter_api_key=api_key
    )
    
    if args.reset:
        trader.reset()
        print("Account reset!")
        return
    
    if args.status:
        print_status(trader)
        return
    
    trader.run(interval_minutes=args.interval)


if __name__ == '__main__':
    main()
