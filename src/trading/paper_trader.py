"""
Paper Trading System - Simulates live trading without real money
Perfect for testing strategies before going live
"""
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from config.settings import settings
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    """A paper trading position."""
    position_id: str
    market_id: str
    market_question: str
    token_id: str
    direction: str  # YES or NO
    
    entry_time: datetime
    entry_price: float
    amount: float
    shares: float
    
    # Tracking
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    
    # Signals used
    edge_at_entry: float = 0.0
    confidence_at_entry: float = 0.0
    signals: List[str] = field(default_factory=list)
    
    # Closure
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    realized_pnl: Optional[float] = None
    closed: bool = False
    
    def update_price(self, price: float):
        """Update current price and unrealized PnL."""
        self.current_price = price
        # Value = shares * price
        current_value = self.shares * price
        self.unrealized_pnl = current_value - self.amount
    
    def close(self, exit_price: float):
        """Close the position."""
        self.exit_time = datetime.now()
        self.exit_price = exit_price
        
        # Final value
        if exit_price >= 0.99:  # Win
            self.realized_pnl = self.shares * 1.0 - self.amount
        elif exit_price <= 0.01:  # Lose
            self.realized_pnl = -self.amount
        else:
            # Sold before resolution
            self.realized_pnl = self.shares * exit_price - self.amount
        
        self.closed = True
    
    def to_dict(self) -> Dict:
        return {
            'position_id': self.position_id,
            'market_id': self.market_id,
            'market_question': self.market_question[:50],
            'direction': self.direction,
            'entry_time': self.entry_time.isoformat(),
            'entry_price': self.entry_price,
            'amount': self.amount,
            'shares': self.shares,
            'current_price': self.current_price,
            'unrealized_pnl': round(self.unrealized_pnl, 2),
            'closed': self.closed,
            'realized_pnl': round(self.realized_pnl, 2) if self.realized_pnl else None,
        }


@dataclass
class PaperTrade:
    """Record of a completed paper trade."""
    trade_id: str
    position_id: str
    market_id: str
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    amount: float
    pnl: float
    return_pct: float
    won: bool


class PaperTradingAccount:
    """
    Paper trading account that simulates real trading.
    """
    
    def __init__(self, initial_capital: float = 75.0,
                 data_dir: Optional[Path] = None):
        """
        Args:
            initial_capital: Starting paper money
            data_dir: Directory to save state
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.data_dir = data_dir or Path("./data")
        
        self.positions: Dict[str, PaperPosition] = {}
        self.closed_trades: List[PaperTrade] = []
        self.trade_counter = 0
        
        # Performance tracking
        self.high_water_mark = initial_capital
        self.max_drawdown = 0.0
        self.total_pnl = 0.0
        
        # Load previous state if exists
        self._load_state()
    
    def open_position(self, market_id: str, market_question: str,
                     token_id: str, direction: str,
                     amount: float, price: float,
                      edge: float = 0, confidence: float = 0,
                      signals: Optional[List[str]] = None) -> Optional[PaperPosition]:

        """
        Open a new paper position.
        
        Args:
            market_id: Market identifier
            market_question: Market question text
            token_id: Token ID for trading
            direction: "YES" or "NO"
            amount: Dollar amount to invest
            price: Entry price
            edge: Estimated edge
            confidence: Confidence level
            signals: List of signal types that triggered this
        
        Returns:
            PaperPosition if successful, None otherwise
        """
        # Validate
        if amount <= 0:
            logger.warning("Invalid amount")
            return None
        
        if amount > self.capital:
            logger.warning(f"Insufficient capital: need ${amount}, have ${self.capital}")
            return None
        
        if price <= 0 or price >= 1:
            logger.warning(f"Invalid price: {price}")
            return None
        
        if market_id in self.positions:
            logger.warning(f"Already have position in {market_id}")
            return None
        
        # Create position
        self.trade_counter += 1
        position_id = f"PAPER-{self.trade_counter}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        shares = amount / price
        
        position = PaperPosition(
            position_id=position_id,
            market_id=market_id,
            market_question=market_question,
            token_id=token_id,
            direction=direction,
            entry_time=datetime.now(),
            entry_price=price,
            amount=amount,
            shares=shares,
            current_price=price,
            edge_at_entry=edge,
            confidence_at_entry=confidence,
            signals=signals or [],
        )
        
        # Deduct capital
        self.capital -= amount
        self.positions[market_id] = position
        
        logger.info(f"Opened paper position: {direction} ${amount} at {price:.2f} on '{market_question[:50]}'")
        
        self._save_state()
        return position
    
    def close_position(self, market_id: str, exit_price: float,
                      reason: str = "manual") -> Optional[PaperTrade]:
        """
        Close a paper position.
        
        Args:
            market_id: Market to close
            exit_price: Exit price
            reason: Reason for closing
        
        Returns:
            PaperTrade record
        """
        if market_id not in self.positions:
            logger.warning(f"No position found for {market_id}")
            return None
        
        position = self.positions[market_id]
        position.close(exit_price)
        
        # Calculate PnL
        pnl = position.realized_pnl
        if pnl is None:
            logger.warning(f"Missing PnL for position {position.position_id}")
            return None
        return_pct = pnl / position.amount if position.amount > 0 else 0
        won = pnl > 0
        
        # Create trade record
        exit_time = position.exit_time if position.exit_time is not None else datetime.now()

        trade = PaperTrade(
            trade_id=f"TRADE-{position.position_id}",
            position_id=position.position_id,
            market_id=market_id,
            direction=position.direction,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            amount=position.amount,
            pnl=pnl,
            return_pct=return_pct,
            won=won,
        )
        
        # Update capital and tracking
        self.capital += position.amount + pnl
        self.total_pnl += pnl
        self.closed_trades.append(trade)
        
        # Update high water mark and drawdown
        if self.capital > self.high_water_mark:
            self.high_water_mark = self.capital
        
        current_dd = (self.high_water_mark - self.capital) / self.high_water_mark
        if current_dd > self.max_drawdown:
            self.max_drawdown = current_dd
        
        del self.positions[market_id]
        
        result = "WIN" if won else "LOSS"
        logger.info(f"Closed paper position: {result} PnL=${pnl:.2f} ({return_pct:.1%})")
        
        self._save_state()
        return trade
    
    def update_position_prices(self, prices: Dict[str, float]):
        """
        Update current prices for all positions.
        
        Args:
            prices: Dict mapping market_id to current price
        """
        for market_id, position in self.positions.items():
            if market_id in prices:
                position.update_price(prices[market_id])
    
    def get_account_summary(self) -> Dict:
        """Get account summary."""
        # Calculate unrealized PnL
        unrealized_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        invested = sum(p.amount for p in self.positions.values())
        total_equity = self.capital + invested + unrealized_pnl
        
        # Calculate stats
        total_trades = len(self.closed_trades)
        winning_trades = sum(1 for t in self.closed_trades if t.won)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        return {
            'initial_capital': self.initial_capital,
            'current_capital': round(self.capital, 2),
            'invested': round(invested, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'total_equity': round(total_equity, 2),
            'realized_pnl': round(self.total_pnl, 2),
            'total_return': f"{(total_equity - self.initial_capital) / self.initial_capital:.1%}",
            'open_positions': len(self.positions),
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'win_rate': f"{win_rate:.1%}",
            'max_drawdown': f"{self.max_drawdown:.1%}",
        }
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions."""
        return [p.to_dict() for p in self.positions.values()]
    
    def get_trade_history(self, limit: int = 20) -> List[Dict]:
        """Get recent trade history."""
        trades = sorted(self.closed_trades, 
                       key=lambda t: t.exit_time, reverse=True)[:limit]
        
        return [{
            'trade_id': t.trade_id,
            'market_id': t.market_id,
            'direction': t.direction,
            'entry_time': t.entry_time.isoformat(),
            'exit_time': t.exit_time.isoformat(),
            'amount': t.amount,
            'pnl': round(t.pnl, 2),
            'return_pct': f"{t.return_pct:.1%}",
            'won': t.won,
        } for t in trades]
    
    def _save_state(self):
        """Save account state to disk."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
            state = {
                'initial_capital': self.initial_capital,
                'capital': self.capital,
                'trade_counter': self.trade_counter,
                'high_water_mark': self.high_water_mark,
                'max_drawdown': self.max_drawdown,
                'total_pnl': self.total_pnl,
                'positions': [p.to_dict() for p in self.positions.values()],
                'last_saved': datetime.now().isoformat(),
            }
            
            with open(self.data_dir / 'paper_trading_state.json', 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _load_state(self):
        """Load account state from disk."""
        try:
            state_file = self.data_dir / 'paper_trading_state.json'
            if not state_file.exists():
                return
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            self.capital = state.get('capital', self.initial_capital)
            self.trade_counter = state.get('trade_counter', 0)
            self.high_water_mark = state.get('high_water_mark', self.initial_capital)
            self.max_drawdown = state.get('max_drawdown', 0)
            self.total_pnl = state.get('total_pnl', 0)
            
            # Reload positions
            for p_data in state.get('positions', []):
                position = PaperPosition(
                    position_id=p_data['position_id'],
                    market_id=p_data['market_id'],
                    market_question=p_data['market_question'],
                    token_id=p_data.get('token_id', ''),
                    direction=p_data['direction'],
                    entry_time=datetime.fromisoformat(p_data['entry_time']),
                    entry_price=p_data['entry_price'],
                    amount=p_data['amount'],
                    shares=p_data['shares'],
                    current_price=p_data.get('current_price', p_data['entry_price']),
                )
                self.positions[position.market_id] = position
            
            logger.info(f"Loaded paper trading state: ${self.capital:.2f} capital, {len(self.positions)} positions")
            
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
    
    def reset(self, confirm: bool = False):
        """Reset the paper trading account."""
        if not confirm:
            logger.warning("Reset requires confirm=True")
            return
        
        self.capital = self.initial_capital
        self.positions = {}
        self.closed_trades = []
        self.trade_counter = 0
        self.high_water_mark = self.initial_capital
        self.max_drawdown = 0.0
        self.total_pnl = 0.0
        
        self._save_state()
        logger.info("Paper trading account reset")


class PaperTradingBot:
    """
    Automated paper trading bot.
    Runs the full trading loop in paper mode.
    """
    
    def __init__(self, initial_capital: float = 75.0):
        from ..data.polymarket_client import PolymarketClient
        from ..data.news_aggregator import NewsAggregator
        from ..analysis.sentiment_analyzer import SentimentAnalyzer
        from ..strategies.edge_detector import EdgeDetector
        from ..strategies.position_sizer import SmallBankrollOptimizer
        
        self.account = PaperTradingAccount(initial_capital)
        self.client = PolymarketClient()
        self.news_aggregator = NewsAggregator()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.edge_detector = EdgeDetector(
            min_edge=settings.MIN_EDGE_THRESHOLD,
            min_confidence=settings.MIN_CONFIDENCE,
        )
        
        # Get optimized settings for small bankroll
        optimizer = SmallBankrollOptimizer(initial_capital)
        self.position_sizer = optimizer.get_position_sizer()
        self.risk_manager = optimizer.get_risk_manager()

        self.position_sizer.kelly_fraction = settings.KELLY_FRACTION
        self.position_sizer.max_position_pct = settings.MAX_POSITION_SIZE_PCT
        self.position_sizer.min_position = settings.MIN_POSITION_SIZE
        self.position_sizer.max_positions = settings.MAX_OPEN_POSITIONS

        self.risk_manager.max_drawdown = settings.MAX_DRAWDOWN_PCT
        self.risk_manager.max_daily_loss = settings.MAX_DAILY_LOSS_PCT
        self.risk_manager.max_position_pct = settings.MAX_POSITION_SIZE_PCT
        self.risk_manager.max_positions = settings.MAX_OPEN_POSITIONS

        self.settings = {
            **optimizer.optimize_for_growth(),
            'min_edge': settings.MIN_EDGE_THRESHOLD,
            'min_confidence': settings.MIN_CONFIDENCE,
            'max_positions': settings.MAX_OPEN_POSITIONS,
            'min_volume_24h': settings.MIN_VOLUME_24H,
            'min_liquidity': settings.MIN_LIQUIDITY,
            'take_profit_pct': settings.TAKE_PROFIT_PCT,
            'stop_loss_pct': settings.STOP_LOSS_PCT,
        }
    
    def scan_for_opportunities(self, max_markets: int = 50) -> List[Dict]:
        """
        Scan markets for trading opportunities.
        
        Returns:
            List of opportunities with scores
        """
        logger.info("Scanning for opportunities...")
        
        # Get active markets
        markets = self.client.get_active_markets(
            limit=max_markets,
            min_volume=self.settings.get('min_volume_24h', 500),
            min_liquidity=self.settings.get('min_liquidity', 200)
        )
        
        if not markets:
            logger.warning("No markets found")
            return []
        
        # Get news
        news = self.news_aggregator.fetch_all_news(max_age_hours=24)
        
        opportunities = []
        
        for market in markets[:30]:  # Limit to top 30 by volume
            try:
                # Get market-specific news
                market_news = self.news_aggregator.get_market_news(
                    market.question,
                    market_keywords=market.question.split()[:5]
                )
                
                # Analyze sentiment
                if market_news:
                    news_texts = [f"{n.title} {n.content}" for n in market_news[:10]]
                    sentiment = self.sentiment_analyzer.analyze(" ".join(news_texts))
                    sentiment_score = sentiment.compound_score
                    sentiment_confidence = sentiment.confidence
                else:
                    sentiment_score = 0
                    sentiment_confidence = 0.3
                
                # Prepare market data
                order_book = None
                if market.yes_token_id:
                    order_book = self.client.get_order_book(market.yes_token_id)

                market_data = {
                    'id': market.id,
                    'question': market.question,
                    'slug': market.slug,
                    'yes_price': market.yes_price,
                    'no_price': market.no_price,
                    'yes_token_id': market.yes_token_id,
                    'no_token_id': market.no_token_id,
                    'volume_24h': market.volume_24h,
                    'liquidity': market.liquidity,
                    'best_bid': order_book.best_bid if order_book else None,
                    'best_ask': order_book.best_ask if order_book else None,
                }

                
                # Detect edge
                opportunity = self.edge_detector.detect_opportunities(
                    market_data,
                    news_data=[{'title': n.title, 'content': n.content, 
                               'published_at': n.published_at} for n in market_news[:5]],
                    sentiment_score=sentiment_score,
                    sentiment_confidence=sentiment_confidence
                )
                
                if opportunity and opportunity.edge >= self.settings['min_edge']:
                    opportunities.append(opportunity)
                    
            except Exception as e:
                logger.warning(f"Error analyzing market {market.id}: {e}")
                continue
        
        # Rank opportunities
        opportunities = self.edge_detector.rank_opportunities(opportunities)
        
        logger.info(f"Found {len(opportunities)} opportunities")
        return [o.to_dict() for o in opportunities[:10]]
    
    def execute_opportunity(self, opportunity: Dict) -> Optional[Dict]:
        """
        Execute a trading opportunity in paper mode.
        
        Args:
            opportunity: Opportunity dict from scan
        
        Returns:
            Position info if opened
        """
        # Get portfolio risk
        risk = self.risk_manager.get_portfolio_risk()
        
        if not risk.is_trading_allowed:
            logger.warning(f"Trading not allowed: {risk.reason}")
            return None
        
        # Calculate position size
        position_size = self.position_sizer.calculate_position(
            capital=self.account.capital,
            current_price=opportunity['current_price'],
            edge=opportunity['edge'],
            confidence=opportunity['confidence'],
            existing_positions=len(self.account.positions),
        )
        
        if position_size.amount < 1.0:
            logger.info(f"Position too small: {position_size.reason}")
            return None
        
        # Open position
        position = self.account.open_position(
            market_id=opportunity['market_id'],
            market_question=opportunity['market_question'],
            token_id=opportunity.get('token_id', ''),
            direction=opportunity['direction'],
            amount=position_size.amount,
            price=opportunity['current_price'],
            edge=opportunity['edge'],
            confidence=opportunity['confidence'],
        )
        
        if position:
            return position.to_dict()
        return None
    
    def update_positions(self):
        """Update prices for all positions."""
        if not self.account.positions:
            return
        
        prices = {}
        for market_id, position in self.account.positions.items():
            try:
                price = self.client.get_price(position.token_id, side="sell")
                if price:
                    prices[market_id] = price
            except Exception as e:
                logger.warning(f"Failed to get price for {market_id}: {e}")
        
        self.account.update_position_prices(prices)
    
    def check_and_close_positions(self):
        """Check positions and close if needed."""
        for market_id, position in list(self.account.positions.items()):
            try:
                # Get current price
                price = self.client.get_price(position.token_id, side="sell")
                if not price:
                    continue
                
                position.update_price(price)
                
                # Check if market resolved (price near 0 or 1)
                if price >= 0.98 or price <= 0.02:
                    self.account.close_position(market_id, price, reason="resolution")
                    continue
                
                # Check for take profit
                if position.unrealized_pnl / position.amount >= self.settings['take_profit_pct']:
                    self.account.close_position(market_id, price, reason="take_profit")
                    continue
                
                # Check for stop loss
                if position.unrealized_pnl / position.amount <= -self.settings['stop_loss_pct']:
                    self.account.close_position(market_id, price, reason="stop_loss")
                    continue
                    
            except Exception as e:
                logger.warning(f"Error checking position {market_id}: {e}")
    
    def run_cycle(self) -> Dict:
        """
        Run one trading cycle.
        
        Returns:
            Summary of actions taken
        """
        summary = {
            'timestamp': datetime.now().isoformat(),
            'opportunities_found': 0,
            'positions_opened': 0,
            'positions_closed': 0,
            'account_summary': None,
        }
        
        # Update existing positions
        self.update_positions()
        
        # Check for closes
        initial_positions = len(self.account.positions)
        self.check_and_close_positions()
        summary['positions_closed'] = initial_positions - len(self.account.positions)
        
        # Scan for new opportunities
        opportunities = self.scan_for_opportunities()
        summary['opportunities_found'] = len(opportunities)
        
        # Execute top opportunities
        for opp in opportunities[:2]:  # Max 2 new positions per cycle
            if summary['positions_opened'] >= self.settings['max_positions']:
                break
            result = self.execute_opportunity(opp)
            if result:
                summary['positions_opened'] += 1
        
        summary['account_summary'] = self.account.get_account_summary()
        
        return summary
