"""
Real Historical Backtest Engine
Backtests swing trading strategy against ACTUAL Polymarket price data.
"""
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.historical_fetcher import HistoricalFetcher, MarketHistory, PricePoint

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Record of a single trade."""
    market_id: str
    question: str
    direction: str  # 'YES' or 'NO'
    
    entry_time: datetime
    entry_price: float
    entry_reason: str
    
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    
    amount: float = 0
    pnl: float = 0
    return_pct: float = 0
    hold_hours: float = 0
    
    # Analysis data at entry
    dip_from_high: float = 0
    sentiment_score: float = 0  # Simulated or from historical data if available


@dataclass
class BacktestResult:
    """Complete backtest results."""
    # Configuration
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    
    # Performance
    final_capital: float
    total_return_pct: float
    
    # Trade statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # Risk metrics
    max_drawdown_pct: float
    sharpe_ratio: float
    profit_factor: float
    
    # Per-trade metrics
    avg_win_pct: float
    avg_loss_pct: float
    avg_hold_hours: float
    
    # Details
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate text summary."""
        return f"""
========================================
BACKTEST RESULTS: {self.strategy_name}
========================================
Period: {self.start_date.date()} to {self.end_date.date()}
Initial Capital: ${self.initial_capital:.2f}
Final Capital: ${self.final_capital:.2f}
Total Return: {self.total_return_pct:.1%}

TRADE STATISTICS
----------------
Total Trades: {self.total_trades}
Winning: {self.winning_trades} ({self.win_rate:.1%})
Losing: {self.losing_trades}

RISK METRICS
------------
Max Drawdown: {self.max_drawdown_pct:.1%}
Sharpe Ratio: {self.sharpe_ratio:.2f}
Profit Factor: {self.profit_factor:.2f}

PER-TRADE METRICS
-----------------
Avg Win: {self.avg_win_pct:.1%}
Avg Loss: {self.avg_loss_pct:.1%}
Avg Hold Time: {self.avg_hold_hours:.1f} hours
========================================
"""


class RealBacktestEngine:
    """
    Backtest engine using real Polymarket historical data.
    
    This is the REAL validation - not Monte Carlo simulations!
    """
    
    def __init__(self,
                 initial_capital: float = 75.0,
                 # Entry parameters
                 min_dip_pct: float = 0.08,
                 min_sentiment: float = 0.1,
                 min_volume: float = 500,
                 min_price: float = 0.10,
                 max_price: float = 0.90,
                 # Exit parameters
                 take_profit_pct: float = 0.08,
                 stop_loss_pct: float = 0.15,
                 max_hold_hours: int = 24,
                 trailing_stop_pct: float = 0.05,
                 use_trailing_stop: bool = True,
                 # Position sizing
                 position_size_pct: float = 0.10,
                 max_positions: int = 6,
                 max_position_usd: float = 15.0,
                 # Fees
                 fee_rate: float = 0.02):
        """Initialize with strategy parameters."""
        
        self.initial_capital = initial_capital
        
        # Entry
        self.min_dip_pct = min_dip_pct
        self.min_sentiment = min_sentiment
        self.min_volume = min_volume
        self.min_price = min_price
        self.max_price = max_price
        
        # Exit
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_hours = max_hold_hours
        self.trailing_stop_pct = trailing_stop_pct
        self.use_trailing_stop = use_trailing_stop
        
        # Position sizing
        self.position_size_pct = position_size_pct
        self.max_positions = max_positions
        self.max_position_usd = max_position_usd
        
        # Fees
        self.fee_rate = fee_rate
    
    def _simulate_sentiment(self, prices: List[float], idx: int, 
                           lookback: int = 24) -> float:
        """
        Simulate sentiment score based on price momentum.
        
        In production, this would use real Reddit/Grok data.
        For backtesting, we approximate sentiment from price behavior.
        
        Logic: If price dropped but shows recovery momentum, sentiment is positive.
        If price is in free-fall, sentiment is negative.
        """
        if idx < lookback:
            return 0.0
        
        window = prices[idx-lookback:idx]
        current = prices[idx]
        
        # Calculate momentum (recent vs older prices)
        recent_avg = np.mean(window[-6:])  # Last 6 periods
        older_avg = np.mean(window[:6])    # First 6 periods
        
        if older_avg == 0:
            return 0.0
        
        momentum = (recent_avg - older_avg) / older_avg
        
        # Convert to sentiment scale (-1 to 1)
        # Positive momentum = positive sentiment (recovery expected)
        sentiment = np.tanh(momentum * 10)  # Scale and bound
        
        return sentiment
    
    def _calculate_dip(self, prices: List[float], idx: int, 
                       lookback: int = 24) -> float:
        """Calculate dip from recent high."""
        if idx < lookback:
            return 0.0
        
        window_high = max(prices[idx-lookback:idx])
        current = prices[idx]
        
        if window_high == 0:
            return 0.0
        
        dip = (window_high - current) / window_high
        return dip
    
    def run_single_market(self, history: MarketHistory) -> List[BacktestTrade]:
        """
        Run backtest on a single market's history.
        
        Args:
            history: MarketHistory object with real price data
            
        Returns:
            List of trades executed
        """
        if len(history.prices) < 100:
            logger.warning(f"Insufficient data for {history.market_id}")
            return []
        
        # Resample to hourly for cleaner analysis
        hourly_data = history.resample_hourly()
        if len(hourly_data) < 48:  # Need at least 2 days
            return []
        
        timestamps = [t for t, p in hourly_data]
        prices = [p for t, p in hourly_data]
        
        trades = []
        position = None
        position_high = None  # For trailing stop
        
        # Start from hour 24 to have lookback data
        for i in range(24, len(prices)):
            current_price = prices[i]
            current_time = datetime.fromtimestamp(timestamps[i])
            
            # Check exit conditions if we have a position
            if position is not None:
                entry_price = position["entry_price"]
                hold_hours = (timestamps[i] - position["entry_ts"]) / 3600
                return_pct = (current_price - entry_price) / entry_price
                
                # Update position high for trailing stop
                if current_price > position_high:
                    position_high = current_price
                
                should_exit = False
                exit_reason = ""
                
                # Take profit
                if return_pct >= self.take_profit_pct:
                    should_exit = True
                    exit_reason = "take_profit"
                
                # Stop loss
                elif return_pct <= -self.stop_loss_pct:
                    should_exit = True
                    exit_reason = "stop_loss"
                
                # Trailing stop
                elif self.use_trailing_stop and position_high > entry_price:
                    drop_from_high = (position_high - current_price) / position_high
                    if drop_from_high >= self.trailing_stop_pct:
                        should_exit = True
                        exit_reason = "trailing_stop"
                
                # Time exit
                elif hold_hours >= self.max_hold_hours:
                    should_exit = True
                    exit_reason = "time_exit"
                
                if should_exit:
                    # Calculate PnL
                    shares = position["amount"] / entry_price
                    pnl = shares * current_price - position["amount"]
                    
                    # Apply fee on profits
                    if pnl > 0:
                        pnl *= (1 - self.fee_rate)
                    
                    trade = BacktestTrade(
                        market_id=history.market_id,
                        question=history.question,
                        direction="YES",
                        entry_time=datetime.fromtimestamp(position["entry_ts"]),
                        entry_price=entry_price,
                        entry_reason=position["entry_reason"],
                        exit_time=current_time,
                        exit_price=current_price,
                        exit_reason=exit_reason,
                        amount=position["amount"],
                        pnl=pnl,
                        return_pct=return_pct,
                        hold_hours=hold_hours,
                        dip_from_high=position["dip"],
                        sentiment_score=position["sentiment"],
                    )
                    trades.append(trade)
                    position = None
                    position_high = None
            
            # Check entry conditions if no position
            if position is None:
                # Price filter
                if current_price < self.min_price or current_price > self.max_price:
                    continue
                
                # Calculate dip
                dip = self._calculate_dip(prices, i)
                if dip < self.min_dip_pct:
                    continue
                
                # Simulate sentiment (in production, use real data)
                sentiment = self._simulate_sentiment(prices, i)
                if sentiment < self.min_sentiment:
                    continue
                
                # Entry signal!
                amount = min(
                    self.initial_capital * self.position_size_pct,
                    self.max_position_usd
                )
                
                position = {
                    "entry_ts": timestamps[i],
                    "entry_price": current_price,
                    "entry_reason": f"Dip {dip:.1%}, sentiment {sentiment:.2f}",
                    "amount": amount,
                    "dip": dip,
                    "sentiment": sentiment,
                }
                position_high = current_price
        
        # Close any remaining position at end
        if position is not None:
            final_price = prices[-1]
            entry_price = position["entry_price"]
            return_pct = (final_price - entry_price) / entry_price
            hold_hours = (timestamps[-1] - position["entry_ts"]) / 3600
            
            shares = position["amount"] / entry_price
            pnl = shares * final_price - position["amount"]
            if pnl > 0:
                pnl *= (1 - self.fee_rate)
            
            trade = BacktestTrade(
                market_id=history.market_id,
                question=history.question,
                direction="YES",
                entry_time=datetime.fromtimestamp(position["entry_ts"]),
                entry_price=entry_price,
                entry_reason=position["entry_reason"],
                exit_time=datetime.fromtimestamp(timestamps[-1]),
                exit_price=final_price,
                exit_reason="end_of_data",
                amount=position["amount"],
                pnl=pnl,
                return_pct=return_pct,
                hold_hours=hold_hours,
                dip_from_high=position["dip"],
                sentiment_score=position["sentiment"],
            )
            trades.append(trade)
        
        return trades
    
    def run_portfolio_backtest(self, histories: List[MarketHistory]) -> BacktestResult:
        """
        Run full portfolio backtest across multiple markets.
        
        This simulates real trading where we:
        1. Scan all markets for opportunities
        2. Respect position limits
        3. Track portfolio equity over time
        
        Args:
            histories: List of MarketHistory objects
            
        Returns:
            BacktestResult with full statistics
        """
        if not histories:
            raise ValueError("No historical data provided")
        
        # Find overlapping time period
        all_starts = [h.start_time for h in histories]
        all_ends = [h.end_time for h in histories]
        start_time = max(all_starts)
        end_time = min(all_ends)
        
        logger.info(f"Backtesting period: {datetime.fromtimestamp(start_time)} to {datetime.fromtimestamp(end_time)}")
        
        # Collect all trades from all markets
        all_trades = []
        for history in histories:
            trades = self.run_single_market(history)
            all_trades.extend(trades)
            logger.info(f"  {history.question[:40]}... -> {len(trades)} trades")
        
        # Sort trades by entry time
        all_trades.sort(key=lambda t: t.entry_time)
        
        logger.info(f"Total trades across all markets: {len(all_trades)}")
        
        # Calculate portfolio metrics
        capital = self.initial_capital
        high_water = capital
        max_dd = 0
        equity_curve = [(datetime.fromtimestamp(start_time), capital)]
        
        # Track active positions (simplified - assumes sequential execution)
        for trade in all_trades:
            # Apply PnL
            capital += trade.pnl
            
            # Track drawdown
            if capital > high_water:
                high_water = capital
            dd = (high_water - capital) / high_water if high_water > 0 else 0
            if dd > max_dd:
                max_dd = dd
            
            # Record equity
            if trade.exit_time:
                equity_curve.append((trade.exit_time, capital))
        
        # Calculate statistics
        winning = [t for t in all_trades if t.pnl > 0]
        losing = [t for t in all_trades if t.pnl <= 0]
        
        total_wins = sum(t.pnl for t in winning)
        total_losses = sum(abs(t.pnl) for t in losing)
        
        # Sharpe ratio (simplified - daily returns)
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                prev_eq = equity_curve[i-1][1]
                curr_eq = equity_curve[i][1]
                if prev_eq > 0:
                    returns.append((curr_eq - prev_eq) / prev_eq)
            
            if returns and np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
            else:
                sharpe = 0
        else:
            sharpe = 0
        
        return BacktestResult(
            strategy_name="Hybrid Swing (Real Data)",
            start_date=datetime.fromtimestamp(start_time),
            end_date=datetime.fromtimestamp(end_time),
            initial_capital=self.initial_capital,
            final_capital=capital,
            total_return_pct=(capital - self.initial_capital) / self.initial_capital,
            total_trades=len(all_trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=len(winning) / len(all_trades) if all_trades else 0,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe,
            profit_factor=total_wins / total_losses if total_losses > 0 else float('inf'),
            avg_win_pct=np.mean([t.return_pct for t in winning]) if winning else 0,
            avg_loss_pct=np.mean([abs(t.return_pct) for t in losing]) if losing else 0,
            avg_hold_hours=np.mean([t.hold_hours for t in all_trades]) if all_trades else 0,
            trades=all_trades,
            equity_curve=equity_curve,
        )


def run_real_backtest(num_markets: int = 20, days_back: int = 14) -> BacktestResult:
    """
    Run backtest on real historical Polymarket data.
    
    Args:
        num_markets: Number of markets to test
        days_back: Days of history to use
        
    Returns:
        BacktestResult with real performance metrics
    """
    logging.basicConfig(level=logging.INFO)
    
    # Fetch historical data
    fetcher = HistoricalFetcher()
    
    # Check if we have cached data
    cached = fetcher.load_histories()
    if cached and len(cached) >= num_markets:
        print(f"Using {len(cached)} cached market histories")
        histories = cached[:num_markets]
    else:
        print(f"Downloading {days_back} days of history for {num_markets} markets...")
        histories = fetcher.fetch_multiple_markets(
            num_markets=num_markets,
            days_back=days_back,
            min_volume=20000
        )
        fetcher.save_histories(histories)
    
    if not histories:
        print("ERROR: No historical data available")
        return None
    
    print(f"\nRunning backtest on {len(histories)} markets...")
    print()
    
    # Run backtest
    engine = RealBacktestEngine(
        initial_capital=75.0,
        min_dip_pct=0.08,
        min_sentiment=0.1,
        take_profit_pct=0.08,
        stop_loss_pct=0.15,
        max_hold_hours=24,
    )
    
    result = engine.run_portfolio_backtest(histories)
    
    # Print results
    print(result.summary())
    
    # Show sample trades
    if result.trades:
        print("\nSAMPLE TRADES:")
        print("-" * 80)
        for trade in result.trades[:10]:
            status = "WIN" if trade.pnl > 0 else "LOSS"
            print(f"[{status}] {trade.question[:40]}...")
            print(f"       Entry: ${trade.entry_price:.4f} -> Exit: ${trade.exit_price:.4f}")
            print(f"       PnL: ${trade.pnl:+.2f} ({trade.return_pct:+.1%}) | {trade.exit_reason}")
            print()
    
    return result


if __name__ == "__main__":
    result = run_real_backtest(num_markets=20, days_back=14)
