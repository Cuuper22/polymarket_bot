#!/usr/bin/env python3
"""
Paper Trader V2 - Rigorous Forward Testing System

This paper trader logs EVERYTHING for validation:
- Every market scanned
- Every signal generated (and why)
- Every trade decision (entry/exit)
- Every price update
- Full audit trail for strategy validation

Run this for 2-4 weeks before deploying real money.
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
import csv

# Setup paths
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from dotenv import load_dotenv
load_dotenv()

# Configure detailed logging
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"paper_trader_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file),
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class TradeDecision:
    """Record of a trading decision (entry or exit)."""
    timestamp: str
    decision_type: str  # 'entry', 'exit', 'skip'
    market_id: str
    market_question: str
    
    # Market state at decision time
    current_price: float
    volume_24h: float
    
    # Analysis results
    dip_from_24h_high: float
    sentiment_score: float
    sentiment_sources: List[str]
    grok_direction: Optional[str]
    grok_confidence: Optional[float]
    
    # Decision
    action: str  # 'buy', 'sell', 'hold', 'skip'
    reason: str
    
    # Trade details (if action is buy/sell)
    amount: Optional[float] = None
    direction: Optional[str] = None  # 'YES' or 'NO'
    
    # For exits
    entry_price: Optional[float] = None
    return_pct: Optional[float] = None
    hold_hours: Optional[float] = None


@dataclass
class Position:
    """An open position."""
    position_id: str
    market_id: str
    market_question: str
    direction: str
    entry_time: str
    entry_price: float
    amount: float
    current_price: float
    unrealized_pnl: float
    entry_reason: str
    dip_at_entry: float
    sentiment_at_entry: float
    highest_price: float  # For trailing stop


@dataclass
class ClosedTrade:
    """A completed trade."""
    trade_id: str
    position_id: str
    market_id: str
    market_question: str
    direction: str
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    amount: float
    pnl: float
    return_pct: float
    hold_hours: float
    entry_reason: str
    exit_reason: str
    dip_at_entry: float
    sentiment_at_entry: float


class PaperTraderV2:
    """
    Rigorous paper trading system with full audit logging.
    """
    
    def __init__(self, initial_capital: float = 75.0, data_dir: str = "./data"):
        self.initial_capital = initial_capital
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # State files
        self.state_file = self.data_dir / "paper_trader_v2_state.json"
        self.decisions_file = self.data_dir / "trade_decisions.csv"
        self.trades_file = self.data_dir / "completed_trades.csv"
        
        # Initialize components
        self._setup_components()
        
        # Load state
        self.state = self._load_state()
        
        # Initialize CSV files
        self._init_csv_files()
    
    def _setup_components(self):
        """Initialize trading components."""
        # Price tracker
        try:
            from data.price_tracker import PriceTracker
            self.price_tracker = PriceTracker(str(self.data_dir))
            logger.info("Price tracker: OK")
        except Exception as e:
            logger.warning(f"Price tracker failed: {e}")
            self.price_tracker = None
        
        # Grok analyzer
        try:
            from analysis.grok_analyzer import GrokAnalyzer
            self.grok = GrokAnalyzer()
            if self.grok.is_available():
                logger.info("Grok AI: OK")
            else:
                logger.warning("Grok AI: No API key")
                self.grok = None
        except Exception as e:
            logger.warning(f"Grok failed: {e}")
            self.grok = None
        
        # Reddit scraper
        try:
            from data.reddit_scraper import RedditScraper
            self.reddit = RedditScraper()
            logger.info("Reddit scraper: OK")
        except Exception as e:
            logger.warning(f"Reddit failed: {e}")
            self.reddit = None
        
        # Polymarket client
        try:
            from data.polymarket_client import PolymarketClient
            self.polymarket = PolymarketClient()
            logger.info("Polymarket client: OK")
        except Exception as e:
            logger.error(f"Polymarket client failed: {e}")
            self.polymarket = None
        
        # Strategy parameters (hybrid swing)
        self.config = {
            'min_dip_pct': 0.08,
            'min_sentiment': 0.1,
            'min_volume': 500,
            'min_price': 0.10,
            'max_price': 0.90,
            'take_profit_pct': 0.08,
            'stop_loss_pct': 0.15,
            'max_hold_hours': 24,
            'trailing_stop_pct': 0.05,
            'position_size_pct': 0.10,
            'max_position_usd': 15.0,
            'max_positions': 6,
            'fee_rate': 0.02,
        }
    
    def _load_state(self) -> Dict:
        """Load state from disk."""
        default = {
            'capital': self.initial_capital,
            'positions': [],
            'closed_trades': [],
            'trade_counter': 0,
            'decision_counter': 0,
            'start_time': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'high_water_mark': self.initial_capital,
            'max_drawdown': 0.0,
            'daily_stats': {},
        }
        
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return default
    
    def _save_state(self):
        """Save state to disk."""
        self.state['last_update'] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
    
    def _init_csv_files(self):
        """Initialize CSV log files with headers."""
        if not self.decisions_file.exists():
            with open(self.decisions_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'decision_type', 'market_id', 'market_question',
                    'current_price', 'volume_24h', 'dip_from_24h_high',
                    'sentiment_score', 'sentiment_sources', 'grok_direction',
                    'grok_confidence', 'action', 'reason', 'amount', 'direction',
                    'entry_price', 'return_pct', 'hold_hours'
                ])
        
        if not self.trades_file.exists():
            with open(self.trades_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'trade_id', 'position_id', 'market_id', 'market_question',
                    'direction', 'entry_time', 'exit_time', 'entry_price',
                    'exit_price', 'amount', 'pnl', 'return_pct', 'hold_hours',
                    'entry_reason', 'exit_reason', 'dip_at_entry', 'sentiment_at_entry'
                ])
    
    def _log_decision(self, decision: TradeDecision):
        """Log a trade decision to CSV."""
        self.state['decision_counter'] += 1
        
        with open(self.decisions_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                decision.timestamp, decision.decision_type, decision.market_id,
                decision.market_question[:100], decision.current_price,
                decision.volume_24h, decision.dip_from_24h_high,
                decision.sentiment_score, ','.join(decision.sentiment_sources),
                decision.grok_direction, decision.grok_confidence,
                decision.action, decision.reason, decision.amount,
                decision.direction, decision.entry_price, decision.return_pct,
                decision.hold_hours
            ])
    
    def _log_trade(self, trade: ClosedTrade):
        """Log a completed trade to CSV."""
        with open(self.trades_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.trade_id, trade.position_id, trade.market_id,
                trade.market_question[:100], trade.direction, trade.entry_time,
                trade.exit_time, trade.entry_price, trade.exit_price,
                trade.amount, trade.pnl, trade.return_pct, trade.hold_hours,
                trade.entry_reason, trade.exit_reason, trade.dip_at_entry,
                trade.sentiment_at_entry
            ])
    
    def _get_sentiment(self, question: str) -> Dict:
        """Get sentiment from all sources."""
        result = {'score': 0, 'sources': []}
        
        # Try Reddit
        if self.reddit:
            try:
                posts = self.reddit.get_market_related_posts(question, max_posts=5)
                if posts:
                    avg_score = sum(p.score for p in posts) / len(posts)
                    reddit_sent = min(1, avg_score / 500)
                    result['reddit_score'] = reddit_sent
                    result['sources'].append('reddit')
            except Exception as e:
                logger.debug(f"Reddit failed: {e}")
        
        # Try Grok Twitter
        if self.grok and 'reddit' not in result['sources']:
            try:
                # Extract topic
                words = question.lower().replace('?', '').split()
                stop = {'will', 'the', 'a', 'an', 'in', 'on', 'to', 'be', 'is'}
                topic = ' '.join([w for w in words if w not in stop][:4])
                
                twitter = self.grok.get_twitter_sentiment(topic)
                if twitter:
                    result['twitter_score'] = twitter.get('overall_sentiment', 0)
                    result['sources'].append('twitter')
            except Exception as e:
                logger.debug(f"Twitter failed: {e}")
        
        # Combine
        scores = [result.get('reddit_score', 0), result.get('twitter_score', 0)]
        valid = [s for s in scores if s != 0]
        result['score'] = sum(valid) / len(valid) if valid else 0
        
        return result
    
    def _get_grok_analysis(self, question: str, price: float) -> Optional[Dict]:
        """Get Grok AI analysis."""
        if not self.grok:
            return None
        
        try:
            analysis = self.grok.analyze_market(question, price)
            if analysis:
                return {
                    'sentiment': analysis.sentiment_score,
                    'direction': analysis.price_direction,
                    'confidence': analysis.confidence,
                    'factors': analysis.key_factors,
                }
        except:
            pass
        
        return None
    
    def _check_exits(self):
        """Check all positions for exit signals."""
        now = datetime.now()
        
        for pos_dict in list(self.state['positions']):
            try:
                # Get current price
                token_id = pos_dict.get('yes_token_id')
                if not token_id:
                    continue
                
                current_price = self.polymarket.get_price(token_id, side="sell")
                if not current_price:
                    continue
                
                # Update position
                pos_dict['current_price'] = current_price
                if current_price > pos_dict.get('highest_price', current_price):
                    pos_dict['highest_price'] = current_price
                
                entry_price = pos_dict['entry_price']
                entry_time = datetime.fromisoformat(pos_dict['entry_time'])
                hold_hours = (now - entry_time).total_seconds() / 3600
                return_pct = (current_price - entry_price) / entry_price
                
                shares = pos_dict['amount'] / entry_price
                pos_dict['unrealized_pnl'] = shares * current_price - pos_dict['amount']
                
                # Check exit conditions
                should_exit = False
                exit_reason = ""
                
                # Take profit
                if return_pct >= self.config['take_profit_pct']:
                    should_exit = True
                    exit_reason = f"take_profit ({return_pct:.1%})"
                
                # Stop loss
                elif return_pct <= -self.config['stop_loss_pct']:
                    should_exit = True
                    exit_reason = f"stop_loss ({return_pct:.1%})"
                
                # Trailing stop
                elif pos_dict.get('highest_price', entry_price) > entry_price:
                    high = pos_dict['highest_price']
                    drop = (high - current_price) / high
                    if drop >= self.config['trailing_stop_pct']:
                        should_exit = True
                        exit_reason = f"trailing_stop (dropped {drop:.1%} from high)"
                
                # Time exit
                elif hold_hours >= self.config['max_hold_hours']:
                    should_exit = True
                    exit_reason = f"time_exit ({hold_hours:.1f}h)"
                
                if should_exit:
                    self._close_position(pos_dict, current_price, exit_reason)
                    
            except Exception as e:
                logger.error(f"Exit check error: {e}")
    
    def _close_position(self, pos_dict: Dict, exit_price: float, reason: str):
        """Close a position and log everything."""
        now = datetime.now()
        
        entry_price = pos_dict['entry_price']
        entry_time = datetime.fromisoformat(pos_dict['entry_time'])
        hold_hours = (now - entry_time).total_seconds() / 3600
        
        shares = pos_dict['amount'] / entry_price
        pnl = shares * exit_price - pos_dict['amount']
        return_pct = (exit_price - entry_price) / entry_price
        
        # Apply fee on profits
        if pnl > 0:
            pnl *= (1 - self.config['fee_rate'])
        
        # Log decision
        decision = TradeDecision(
            timestamp=now.isoformat(),
            decision_type='exit',
            market_id=pos_dict['market_id'],
            market_question=pos_dict['market_question'],
            current_price=exit_price,
            volume_24h=0,
            dip_from_24h_high=0,
            sentiment_score=0,
            sentiment_sources=[],
            grok_direction=None,
            grok_confidence=None,
            action='sell',
            reason=reason,
            amount=pos_dict['amount'],
            direction=pos_dict['direction'],
            entry_price=entry_price,
            return_pct=return_pct,
            hold_hours=hold_hours,
        )
        self._log_decision(decision)
        
        # Log completed trade
        self.state['trade_counter'] += 1
        trade = ClosedTrade(
            trade_id=f"T{self.state['trade_counter']:05d}",
            position_id=pos_dict['position_id'],
            market_id=pos_dict['market_id'],
            market_question=pos_dict['market_question'],
            direction=pos_dict['direction'],
            entry_time=pos_dict['entry_time'],
            exit_time=now.isoformat(),
            entry_price=entry_price,
            exit_price=exit_price,
            amount=pos_dict['amount'],
            pnl=round(pnl, 2),
            return_pct=return_pct,
            hold_hours=hold_hours,
            entry_reason=pos_dict.get('entry_reason', ''),
            exit_reason=reason,
            dip_at_entry=pos_dict.get('dip_at_entry', 0),
            sentiment_at_entry=pos_dict.get('sentiment_at_entry', 0),
        )
        self._log_trade(trade)
        
        # Update state
        self.state['capital'] += pos_dict['amount'] + pnl
        self.state['closed_trades'].append(asdict(trade))
        self.state['positions'] = [
            p for p in self.state['positions']
            if p['position_id'] != pos_dict['position_id']
        ]
        
        # Update high water mark and drawdown
        equity = self._get_equity()
        if equity > self.state['high_water_mark']:
            self.state['high_water_mark'] = equity
        dd = (self.state['high_water_mark'] - equity) / self.state['high_water_mark']
        if dd > self.state['max_drawdown']:
            self.state['max_drawdown'] = dd
        
        result = "WIN" if pnl > 0 else "LOSS"
        logger.info(f"CLOSED [{result}] ${pnl:+.2f} ({return_pct:+.1%}) | {reason}")
        logger.info(f"  {pos_dict['market_question'][:60]}")
    
    def _scan_opportunities(self) -> List[Dict]:
        """Scan markets for entry opportunities."""
        if not self.polymarket:
            return []
        
        opportunities = []
        
        try:
            markets = self.polymarket.get_active_markets(limit=50, min_volume=500)
            logger.info(f"Scanning {len(markets)} markets...")
            
            for market in markets[:30]:
                now = datetime.now()
                
                # Get price analysis
                dip_size = 0
                if self.price_tracker:
                    analysis = self.price_tracker.get_analysis(market.id)
                    if analysis:
                        dip_size = analysis.dip_size if analysis.is_dip else 0
                
                # Get sentiment
                sentiment = self._get_sentiment(market.question)
                
                # Get Grok analysis (only for significant dips)
                grok = None
                if dip_size >= 0.10 and self.grok:
                    grok = self._get_grok_analysis(market.question, market.yes_price)
                
                # Evaluate entry
                action = 'skip'
                reason = ''
                
                # Price filter
                if market.yes_price < self.config['min_price']:
                    reason = f"price too low ({market.yes_price:.2f})"
                elif market.yes_price > self.config['max_price']:
                    reason = f"price too high ({market.yes_price:.2f})"
                # Dip filter
                elif dip_size < self.config['min_dip_pct']:
                    reason = f"dip too small ({dip_size:.1%})"
                # Sentiment filter
                elif sentiment['score'] < self.config['min_sentiment']:
                    reason = f"sentiment too low ({sentiment['score']:.2f})"
                # Position limit
                elif len(self.state['positions']) >= self.config['max_positions']:
                    reason = "max positions reached"
                else:
                    action = 'buy'
                    reason = f"Dip {dip_size:.1%}, sentiment {sentiment['score']:.2f}"
                
                # Log ALL decisions (including skips for significant dips)
                if dip_size >= 0.05 or action == 'buy':
                    decision = TradeDecision(
                        timestamp=now.isoformat(),
                        decision_type='entry_scan',
                        market_id=market.id,
                        market_question=market.question,
                        current_price=market.yes_price,
                        volume_24h=market.volume_24h,
                        dip_from_24h_high=dip_size,
                        sentiment_score=sentiment['score'],
                        sentiment_sources=sentiment['sources'],
                        grok_direction=grok.get('direction') if grok else None,
                        grok_confidence=grok.get('confidence') if grok else None,
                        action=action,
                        reason=reason,
                    )
                    self._log_decision(decision)
                
                if action == 'buy':
                    opportunities.append({
                        'market': market,
                        'dip_size': dip_size,
                        'sentiment': sentiment,
                        'grok': grok,
                        'reason': reason,
                    })
                    
        except Exception as e:
            logger.error(f"Scan error: {e}")
        
        return opportunities
    
    def _open_position(self, opp: Dict) -> bool:
        """Open a new position."""
        market = opp['market']
        
        # Calculate position size
        size = min(
            self.state['capital'] * self.config['position_size_pct'],
            self.config['max_position_usd']
        )
        size = max(3.0, min(size, self.state['capital'] * 0.95))
        
        if size < 3:
            return False
        
        now = datetime.now()
        self.state['trade_counter'] += 1
        
        pos_id = f"P{self.state['trade_counter']:05d}-{now.strftime('%Y%m%d%H%M%S')}"
        
        position = {
            'position_id': pos_id,
            'market_id': market.id,
            'market_question': market.question,
            'direction': 'YES',
            'entry_time': now.isoformat(),
            'entry_price': market.yes_price,
            'amount': size,
            'current_price': market.yes_price,
            'unrealized_pnl': 0,
            'entry_reason': opp['reason'],
            'dip_at_entry': opp['dip_size'],
            'sentiment_at_entry': opp['sentiment']['score'],
            'highest_price': market.yes_price,
            'yes_token_id': market.yes_token_id,
        }
        
        self.state['positions'].append(position)
        self.state['capital'] -= size
        
        logger.info(f"OPENED YES ${size:.2f} @ {market.yes_price:.4f}")
        logger.info(f"  {market.question[:60]}")
        logger.info(f"  Reason: {opp['reason']}")
        
        return True
    
    def _get_equity(self) -> float:
        """Calculate total equity."""
        invested = sum(p['amount'] for p in self.state['positions'])
        unrealized = sum(p.get('unrealized_pnl', 0) for p in self.state['positions'])
        return self.state['capital'] + invested + unrealized
    
    def _update_price_history(self):
        """Update price tracker (hourly)."""
        if not self.polymarket or not self.price_tracker:
            return
        
        try:
            markets = self.polymarket.get_active_markets(limit=100, min_volume=200)
            for market in markets:
                self.price_tracker.update_price(
                    market_id=market.id,
                    price=market.yes_price,
                    volume_24h=market.volume_24h
                )
            self.price_tracker.save()
        except Exception as e:
            logger.debug(f"Price update error: {e}")
    
    def run_cycle(self) -> Dict:
        """Run one trading cycle."""
        cycle_start = datetime.now()
        
        # Update price history
        self._update_price_history()
        
        # Check exits
        initial_positions = len(self.state['positions'])
        self._check_exits()
        closed_count = initial_positions - len(self.state['positions'])
        
        # Find opportunities
        opportunities = self._scan_opportunities()
        
        # Open positions (max 2 per cycle)
        opened_count = 0
        for opp in opportunities[:2]:
            if self._open_position(opp):
                opened_count += 1
        
        # Save state
        self._save_state()
        
        return {
            'timestamp': cycle_start.isoformat(),
            'opportunities': len(opportunities),
            'opened': opened_count,
            'closed': closed_count,
            'equity': self._get_equity(),
        }
    
    def get_status(self) -> Dict:
        """Get current status."""
        equity = self._get_equity()
        trades = self.state['closed_trades']
        
        return {
            'capital': round(self.state['capital'], 2),
            'invested': round(sum(p['amount'] for p in self.state['positions']), 2),
            'unrealized': round(sum(p.get('unrealized_pnl', 0) for p in self.state['positions']), 2),
            'equity': round(equity, 2),
            'return_pct': round((equity - self.initial_capital) / self.initial_capital * 100, 1),
            'positions': len(self.state['positions']),
            'total_trades': len(trades),
            'winning': sum(1 for t in trades if t.get('pnl', 0) > 0),
            'win_rate': round(sum(1 for t in trades if t.get('pnl', 0) > 0) / len(trades) * 100, 1) if trades else 0,
            'realized_pnl': round(sum(t.get('pnl', 0) for t in trades), 2),
            'max_drawdown': round(self.state['max_drawdown'] * 100, 1),
            'decisions_logged': self.state['decision_counter'],
        }
    
    def run(self, interval_minutes: int = 10):
        """Run continuous paper trading."""
        print("\n" + "=" * 60)
        print("PAPER TRADER V2 - Rigorous Forward Testing")
        print("=" * 60)
        print(f"\nCapital: ${self.state['capital']:.2f}")
        print(f"Grok AI: {'OK' if self.grok else 'Disabled'}")
        print(f"Reddit: {'OK' if self.reddit else 'Disabled'}")
        print(f"Interval: {interval_minutes} minutes")
        print(f"\nLog file: {log_file}")
        print(f"Decisions CSV: {self.decisions_file}")
        print(f"Trades CSV: {self.trades_file}")
        print("\nPress Ctrl+C to stop\n")
        
        cycle = 0
        try:
            while True:
                cycle += 1
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Cycle {cycle}")
                
                result = self.run_cycle()
                status = self.get_status()
                
                print(f"  Opportunities: {result['opportunities']}")
                print(f"  Opened: {result['opened']} | Closed: {result['closed']}")
                print(f"  Equity: ${status['equity']:.2f} ({status['return_pct']:+.1f}%)")
                print(f"  Win Rate: {status['win_rate']:.1f}% ({status['winning']}/{status['total_trades']})")
                print(f"  Decisions logged: {status['decisions_logged']}")
                
                if self.state['positions']:
                    print("\n  Positions:")
                    for p in self.state['positions']:
                        pnl_pct = p.get('unrealized_pnl', 0) / p['amount'] * 100
                        print(f"    {p['direction']} ${p['amount']:.2f} @ {p['entry_price']:.4f} ({pnl_pct:+.1f}%)")
                
                print(f"\nSleeping {interval_minutes} minutes...")
                time.sleep(interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\n\nStopping...")
            self._save_state()
            
            status = self.get_status()
            print("\n" + "=" * 60)
            print("FINAL STATUS")
            print("=" * 60)
            for k, v in status.items():
                print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Paper Trader V2 - Rigorous Testing")
    parser.add_argument('--capital', type=float, default=75.0)
    parser.add_argument('--interval', type=int, default=10)
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--reset', action='store_true')
    
    args = parser.parse_args()
    
    trader = PaperTraderV2(initial_capital=args.capital)
    
    if args.reset:
        import os
        for f in [trader.state_file, trader.decisions_file, trader.trades_file]:
            if f.exists():
                os.remove(f)
        print("Reset complete!")
        return
    
    if args.status:
        status = trader.get_status()
        print("\n" + "=" * 60)
        print("PAPER TRADER V2 STATUS")
        print("=" * 60)
        for k, v in status.items():
            print(f"  {k}: {v}")
        print()
        return
    
    trader.run(interval_minutes=args.interval)


if __name__ == '__main__':
    main()
