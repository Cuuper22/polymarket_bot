"""
Backtesting Engine - Simulates trading strategies on historical data
"""
import logging
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import json

logger = logging.getLogger(__name__)


class TradeOutcome(Enum):
    """Outcome of a trade."""
    WIN = "win"
    LOSS = "loss"
    PENDING = "pending"
    CANCELLED = "cancelled"


@dataclass
class BacktestTrade:
    """A single trade in the backtest."""
    trade_id: str
    market_id: str
    market_question: str
    direction: str  # YES or NO
    entry_time: datetime
    entry_price: float
    amount: float
    shares: float
    
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    outcome: TradeOutcome = TradeOutcome.PENDING
    pnl: float = 0.0
    return_pct: float = 0.0
    
    # Signal info
    edge_at_entry: float = 0.0
    confidence_at_entry: float = 0.0
    signals: List[str] = field(default_factory=list)
    
    def close(self, exit_price: float, exit_time: datetime, won: bool):
        """Close the trade."""
        self.exit_price = exit_price
        self.exit_time = exit_time
        
        if won:
            self.outcome = TradeOutcome.WIN
            # Win pays $1 per share
            self.pnl = self.shares * 1.0 - self.amount
        else:
            self.outcome = TradeOutcome.LOSS
            # Lose entire bet
            self.pnl = -self.amount
        
        self.return_pct = self.pnl / self.amount if self.amount > 0 else 0


@dataclass
class BacktestResult:
    """Results of a backtest run."""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    total_trades: int
    winning_trades: int
    losing_trades: int
    
    total_pnl: float
    total_return_pct: float
    
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    
    max_drawdown: float
    max_drawdown_date: datetime
    
    sharpe_ratio: float
    sortino_ratio: float
    
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[tuple] = field(default_factory=list)  # (date, equity)
    
    def to_dict(self) -> Dict:
        return {
            'period': f"{self.start_date.date()} to {self.end_date.date()}",
            'initial_capital': self.initial_capital,
            'final_capital': round(self.final_capital, 2),
            'total_pnl': round(self.total_pnl, 2),
            'total_return': f"{self.total_return_pct:.1%}",
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': f"{self.win_rate:.1%}",
            'avg_win': round(self.avg_win, 2),
            'avg_loss': round(self.avg_loss, 2),
            'profit_factor': round(self.profit_factor, 2),
            'max_drawdown': f"{self.max_drawdown:.1%}",
            'sharpe_ratio': round(self.sharpe_ratio, 2),
        }
    
    def print_summary(self):
        """Print a formatted summary."""
        print("\n" + "=" * 50)
        print("BACKTEST RESULTS")
        print("=" * 50)
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Initial Capital: ${self.initial_capital:.2f}")
        print(f"Final Capital: ${self.final_capital:.2f}")
        print(f"Total Return: {self.total_return_pct:.1%}")
        print("-" * 50)
        print(f"Total Trades: {self.total_trades}")
        print(f"Win Rate: {self.win_rate:.1%} ({self.winning_trades}W / {self.losing_trades}L)")
        print(f"Average Win: ${self.avg_win:.2f}")
        print(f"Average Loss: ${self.avg_loss:.2f}")
        print(f"Profit Factor: {self.profit_factor:.2f}")
        print("-" * 50)
        print(f"Max Drawdown: {self.max_drawdown:.1%}")
        print(f"Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print("=" * 50)


@dataclass
class SimulatedMarket:
    """A simulated market for backtesting."""
    market_id: str
    question: str
    start_price: float
    end_price: float
    resolution: bool  # True = YES wins, False = NO wins
    resolution_date: datetime
    
    # Price history: [(timestamp, price), ...]
    price_history: List[tuple] = field(default_factory=list)
    
    # Simulated news/sentiment
    sentiment_history: List[tuple] = field(default_factory=list)
    volume_history: List[tuple] = field(default_factory=list)


class BacktestEngine:
    """
    Main backtesting engine.
    """
    
    def __init__(self, initial_capital: float = 75.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: Dict[str, BacktestTrade] = {}
        self.closed_trades: List[BacktestTrade] = []
        self.equity_curve: List[tuple] = []
        self.trade_counter = 0
    
    def run_backtest(self, 
                    markets: List[SimulatedMarket],
                    strategy_fn: Callable,
                    start_date: datetime,
                    end_date: datetime) -> BacktestResult:
        """
        Run a backtest on simulated markets.
        
        Args:
            markets: List of simulated markets
            strategy_fn: Function that takes (market_data, capital) and returns trade signal
            start_date: Start date
            end_date: End date
        
        Returns:
            BacktestResult with performance metrics
        """
        self.capital = self.initial_capital
        self.positions = {}
        self.closed_trades = []
        self.equity_curve = [(start_date, self.initial_capital)]
        
        # Track metrics
        high_water_mark = self.initial_capital
        max_drawdown = 0
        max_drawdown_date = start_date
        
        # Simulate day by day
        current_date = start_date
        while current_date <= end_date:
            
            # Check for market resolutions
            for market in markets:
                if market.market_id in self.positions:
                    if current_date >= market.resolution_date:
                        # Resolve position
                        trade = self.positions[market.market_id]
                        won = (trade.direction == "YES" and market.resolution) or \
                              (trade.direction == "NO" and not market.resolution)
                        
                        trade.close(
                            exit_price=1.0 if won else 0.0,
                            exit_time=current_date,
                            won=won
                        )
                        
                        self.capital += trade.pnl + trade.amount  # Return capital + pnl
                        self.closed_trades.append(trade)
                        del self.positions[market.market_id]
            
            # Look for new opportunities
            for market in markets:
                if market.market_id in self.positions:
                    continue
                if current_date >= market.resolution_date:
                    continue
                
                # Get current market state
                market_data = self._get_market_state(market, current_date)
                if not market_data:
                    continue

                # Run strategy
                signal = strategy_fn(market_data, self.capital)

                if signal and signal.get('action') == 'buy':
                    # Open position
                    amount = min(signal.get('amount', 0), self.capital * 0.15)
                    if amount >= 1.0:
                        price = signal.get('price', market_data['price'])
                        if price <= 0 or price >= 1:
                            continue
                        direction = signal.get('direction', 'YES')

                        trade = BacktestTrade(
                            trade_id=f"BT-{self.trade_counter}",
                            market_id=market.market_id,
                            market_question=market.question,
                            direction=direction,
                            entry_time=current_date,
                            entry_price=price,
                            amount=amount,
                            shares=amount / price,
                            edge_at_entry=signal.get('edge', 0),
                            confidence_at_entry=signal.get('confidence', 0),
                        )

                        self.positions[market.market_id] = trade
                        self.capital -= amount
                        self.trade_counter += 1
            
            # Record equity
            total_equity = self.capital + sum(
                t.amount for t in self.positions.values()
            )
            self.equity_curve.append((current_date, total_equity))
            
            # Track drawdown
            if total_equity > high_water_mark:
                high_water_mark = total_equity
            
            drawdown = (high_water_mark - total_equity) / high_water_mark if high_water_mark > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                max_drawdown_date = current_date
            
            current_date += timedelta(days=1)
        
        # Close any remaining positions at last price
        for market_id, trade in list(self.positions.items()):
            for market in markets:
                if market.market_id == market_id:
                    last_price = self._get_price_at(market, end_date)
                    if last_price is None:
                        continue
                    # Assume 50/50 outcome for unclosed
                    won = last_price > trade.entry_price if trade.direction == "YES" else last_price < trade.entry_price
                    trade.close(last_price, end_date, won=won)
                    self.capital += trade.pnl + trade.amount
                    self.closed_trades.append(trade)
        
        return self._calculate_results(start_date, end_date, max_drawdown, max_drawdown_date)
    
    def _get_market_state(self, market: SimulatedMarket, 
                         date: datetime) -> Optional[Dict]:
        """Get market state at a specific date."""
        price = self._get_price_at(market, date)
        if price is None:
            return None
        
        sentiment = self._get_sentiment_at(market, date)
        volume = self._get_volume_at(market, date)
        
        return {
            'market_id': market.market_id,
            'question': market.question,
            'price': price,
            'sentiment': sentiment,
            'volume': volume,
            'resolution_date': market.resolution_date,
            'days_to_resolution': (market.resolution_date - date).days,
        }
    
    def _get_price_at(self, market: SimulatedMarket, date: datetime) -> Optional[float]:
        """Get price at specific date."""
        if not market.price_history:
            return market.start_price
        
        # Find closest price
        for i, (ts, price) in enumerate(market.price_history):
            if ts >= date:
                return price
        
        return market.price_history[-1][1] if market.price_history else market.start_price
    
    def _get_sentiment_at(self, market: SimulatedMarket, date: datetime) -> float:
        """Get sentiment at specific date."""
        if not market.sentiment_history:
            return 0.0
        
        for ts, sentiment in market.sentiment_history:
            if ts >= date:
                return sentiment
        
        return market.sentiment_history[-1][1]
    
    def _get_volume_at(self, market: SimulatedMarket, date: datetime) -> float:
        """Get volume at specific date."""
        if not market.volume_history:
            return 1000.0
        
        for ts, volume in market.volume_history:
            if ts >= date:
                return volume
        
        return market.volume_history[-1][1]
    
    def _calculate_results(self, start_date: datetime, end_date: datetime,
                          max_drawdown: float, max_drawdown_date: datetime) -> BacktestResult:
        """Calculate backtest results."""
        total_trades = len(self.closed_trades)
        
        if total_trades == 0:
            return BacktestResult(
                start_date=start_date,
                end_date=end_date,
                initial_capital=self.initial_capital,
                final_capital=self.capital,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=0,
                total_return_pct=0,
                win_rate=0,
                avg_win=0,
                avg_loss=0,
                profit_factor=0,
                max_drawdown=max_drawdown,
                max_drawdown_date=max_drawdown_date,
                sharpe_ratio=0,
                sortino_ratio=0,
                trades=[],
                equity_curve=self.equity_curve,
            )
        
        wins = [t for t in self.closed_trades if t.outcome == TradeOutcome.WIN]
        losses = [t for t in self.closed_trades if t.outcome == TradeOutcome.LOSS]
        
        winning_trades = len(wins)
        losing_trades = len(losses)
        
        total_pnl = sum(t.pnl for t in self.closed_trades)
        total_return_pct = total_pnl / self.initial_capital
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        avg_win = statistics.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = abs(statistics.mean([t.pnl for t in losses])) if losses else 0
        
        total_wins = sum(t.pnl for t in wins) if wins else 0
        total_losses = abs(sum(t.pnl for t in losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Calculate Sharpe ratio
        returns = [t.return_pct for t in self.closed_trades]
        if len(returns) > 1:
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns)
            sharpe_ratio = avg_return / std_return * (252 ** 0.5) if std_return > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Calculate Sortino ratio (only downside volatility)
        negative_returns = [r for r in returns if r < 0]
        if negative_returns and len(negative_returns) > 1:
            downside_std = statistics.stdev(negative_returns)
            avg_return = statistics.mean(returns)
            sortino_ratio = avg_return / downside_std * (252 ** 0.5) if downside_std > 0 else 0
        else:
            sortino_ratio = sharpe_ratio
        
        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=self.capital,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            max_drawdown_date=max_drawdown_date,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            trades=self.closed_trades,
            equity_curve=self.equity_curve,
        )


def generate_simulated_markets(num_markets: int = 20,
                               start_date: Optional[datetime] = None,
                               duration_days: int = 30) -> List[SimulatedMarket]:
    """
    Generate simulated markets for backtesting.
    
    Creates markets with realistic price paths and outcomes.
    """
    import random
    
    if start_date is None:
        start_date = datetime.now() - timedelta(days=duration_days)
    
    markets = []
    
    questions = [
        "Will {entity} announce {action} by {date}?",
        "Will {crypto} reach ${price} by {date}?",
        "Will {person} win the {competition}?",
        "Will {country} {action} by {date}?",
        "Will {company} release {product} this {period}?",
    ]
    
    entities = ["Bitcoin", "Ethereum", "Trump", "Biden", "SEC", "Fed", "Apple", "Tesla"]
    actions = ["approval", "announcement", "launch", "ban", "decision"]
    
    for i in range(num_markets):
        # Random market parameters
        start_price = random.uniform(0.2, 0.8)
        
        # Outcome probability based on start price (with noise)
        true_prob = start_price + random.uniform(-0.2, 0.2)
        true_prob = max(0.1, min(0.9, true_prob))
        
        resolution = random.random() < true_prob
        end_price = 0.95 if resolution else 0.05
        
        resolution_date = start_date + timedelta(days=random.randint(7, duration_days))
        
        # Generate price history with random walk
        price_history = []
        current_price = start_price
        current_date = start_date
        
        while current_date < resolution_date:
            # Drift towards true outcome
            drift = (end_price - current_price) / max(1, (resolution_date - current_date).days)
            noise = random.gauss(0, 0.02)
            current_price = max(0.05, min(0.95, current_price + drift * 0.5 + noise))
            
            price_history.append((current_date, current_price))
            current_date += timedelta(hours=random.randint(4, 12))
        
        # Generate sentiment (correlated with outcome)
        sentiment_history = []
        base_sentiment = 0.3 if resolution else -0.3
        current_date = start_date
        
        while current_date < resolution_date:
            sentiment = base_sentiment + random.gauss(0, 0.3)
            sentiment = max(-1, min(1, sentiment))
            sentiment_history.append((current_date, sentiment))
            current_date += timedelta(hours=random.randint(6, 24))
        
        market = SimulatedMarket(
            market_id=f"SIM-{i}",
            question=f"Simulated Market {i}: Will outcome occur?",
            start_price=start_price,
            end_price=end_price,
            resolution=resolution,
            resolution_date=resolution_date,
            price_history=price_history,
            sentiment_history=sentiment_history,
        )
        markets.append(market)
    
    return markets
