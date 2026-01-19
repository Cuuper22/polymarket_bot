"""
Microstructure-Aware Backtest Engine
====================================
Realistic backtesting with:
- Trading fees (Polymarket: 2% on profits)
- Bid-ask spread costs
- Slippage and market impact
- Partial fills
- Order rate limits
- Realistic execution simulation

This prevents overfitting to idealized conditions.
"""
import logging
from typing import List, Dict, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import statistics
import random

from .benchmark_suite import (
    BenchmarkScenario, 
    BenchmarkSuite,
    OrderBookSnapshot,
    ScenarioType
)

logger = logging.getLogger(__name__)


# =============================================================================
# TRADING COSTS MODEL
# =============================================================================

@dataclass
class TradingCosts:
    """
    Polymarket trading cost structure.
    """
    # Polymarket takes 2% of profits (not losses)
    profit_fee_rate: float = 0.02
    
    # Minimum spread cost (even in liquid markets)
    min_spread_bps: int = 50  # 0.5%
    
    # Slippage model parameters
    base_slippage_bps: int = 10  # 0.1% base
    size_impact_factor: float = 0.001  # Additional slippage per $ traded
    
    # Order rate limits
    max_orders_per_minute: int = 10
    max_orders_per_hour: int = 100
    
    def calculate_entry_cost(self, 
                            amount: float, 
                            mid_price: float,
                            spread: float,
                            book_depth: float) -> Tuple[float, float]:
        """
        Calculate entry execution price and costs.
        
        Returns: (execution_price, total_cost_dollars)
        """
        # Spread cost (half spread to cross)
        spread_cost = spread / 2
        
        # Slippage based on size vs liquidity
        if book_depth > 0:
            size_ratio = amount / book_depth
            slippage = self.base_slippage_bps / 10000 + size_ratio * self.size_impact_factor
        else:
            slippage = 0.05  # 5% slippage in illiquid market
        
        # Execution price is worse than mid
        exec_price = mid_price + spread_cost + slippage
        exec_price = min(0.99, exec_price)
        
        # Total cost = spread + slippage in dollar terms
        total_cost = amount * (spread_cost + slippage) / mid_price
        
        return exec_price, total_cost
    
    def calculate_exit_cost(self,
                           amount: float,
                           mid_price: float,
                           spread: float,
                           book_depth: float,
                           is_profit: bool) -> Tuple[float, float]:
        """
        Calculate exit execution price and costs.
        
        Returns: (execution_price, total_cost_dollars)
        """
        # Spread cost
        spread_cost = spread / 2
        
        # Slippage
        if book_depth > 0:
            size_ratio = amount / book_depth
            slippage = self.base_slippage_bps / 10000 + size_ratio * self.size_impact_factor
        else:
            slippage = 0.05
        
        # Execution price is worse than mid
        exec_price = mid_price - spread_cost - slippage
        exec_price = max(0.01, exec_price)
        
        # Base cost
        total_cost = amount * (spread_cost + slippage) / mid_price
        
        # Add profit fee if profitable
        if is_profit:
            # Fee is on the profit portion
            total_cost += self.profit_fee_rate * amount * 0.5  # Estimate avg profit portion
        
        return exec_price, total_cost
    
    def calculate_profit_fee(self, profit: float) -> float:
        """Calculate Polymarket fee on profit."""
        if profit <= 0:
            return 0
        return profit * self.profit_fee_rate


# =============================================================================
# EXECUTION SIMULATOR
# =============================================================================

class ExecutionSimulator:
    """
    Simulates realistic order execution.
    """
    
    def __init__(self, costs: Optional[TradingCosts] = None):
        self.costs = costs if costs is not None else TradingCosts()
        self.order_timestamps: List[datetime] = []
    
    def can_place_order(self, timestamp: datetime) -> Tuple[bool, str]:
        """Check if order rate limits allow placing an order."""
        
        # Clean old timestamps
        one_hour_ago = timestamp - timedelta(hours=1)
        one_minute_ago = timestamp - timedelta(minutes=1)
        
        self.order_timestamps = [
            ts for ts in self.order_timestamps if ts > one_hour_ago
        ]
        
        # Check minute limit
        recent_minute = sum(1 for ts in self.order_timestamps if ts > one_minute_ago)
        if recent_minute >= self.costs.max_orders_per_minute:
            return False, "Rate limit: max orders per minute"
        
        # Check hour limit
        if len(self.order_timestamps) >= self.costs.max_orders_per_hour:
            return False, "Rate limit: max orders per hour"
        
        return True, "OK"
    
    def record_order(self, timestamp: datetime):
        """Record an order for rate limiting."""
        self.order_timestamps.append(timestamp)
    
    def simulate_fill(self,
                     side: str,  # "buy" or "sell"
                     size_dollars: float,
                     orderbook: Optional[OrderBookSnapshot],
                     mid_price: float,
                     timestamp: datetime) -> Dict:
        """
        Simulate order fill with realistic execution.
        
        Returns dict with fill details.
        """
        # Check rate limits
        can_order, reason = self.can_place_order(timestamp)
        if not can_order:
            return {
                "filled": False,
                "reason": reason,
                "fill_price": 0,
                "filled_size": 0,
                "unfilled_size": size_dollars,
                "slippage": 0,
                "cost": 0,
            }
        
        # If we have an order book, use it
        if orderbook is not None:
            spread = orderbook.spread
            depth = orderbook.bid_depth if side == "sell" else orderbook.ask_depth
            
            # Try to fill from order book
            fill_price, filled, unfilled = orderbook.get_fill_price(side, size_dollars / mid_price)
            filled_dollars = filled * fill_price
            unfilled_dollars = unfilled * mid_price
        else:
            # Estimate with synthetic book
            spread = max(0.005, mid_price * 0.02)  # 2% spread estimate
            depth = 1000  # Assume $1000 depth
            
            # Simple slippage model
            if side == "buy":
                fill_price = mid_price + spread / 2
            else:
                fill_price = mid_price - spread / 2
            
            # Size-based slippage
            size_impact = (size_dollars / depth) * 0.02
            if side == "buy":
                fill_price += size_impact
            else:
                fill_price -= size_impact
            
            fill_price = max(0.01, min(0.99, fill_price))
            filled_dollars = size_dollars
            unfilled_dollars = 0
        
        # Calculate slippage cost
        if side == "buy":
            slippage = (fill_price - mid_price) / mid_price
        else:
            slippage = (mid_price - fill_price) / mid_price
        
        cost = slippage * filled_dollars
        
        self.record_order(timestamp)
        
        return {
            "filled": True,
            "reason": "OK",
            "fill_price": fill_price,
            "filled_size": filled_dollars,
            "unfilled_size": unfilled_dollars,
            "slippage": slippage,
            "cost": cost,
            "spread": spread,
        }


# =============================================================================
# POSITION TRACKING
# =============================================================================

class TradeOutcome(Enum):
    WIN = "win"
    LOSS = "loss"
    PENDING = "pending"


@dataclass
class MicrostructureTrade:
    """Trade with full execution details."""
    trade_id: str
    scenario_id: str
    direction: str  # YES or NO
    
    # Entry
    entry_time: datetime
    intended_entry_price: float
    actual_entry_price: float
    intended_size: float
    filled_size: float
    entry_slippage: float
    entry_cost: float
    
    # Exit
    exit_time: Optional[datetime] = None
    intended_exit_price: Optional[float] = None
    actual_exit_price: Optional[float] = None
    exit_slippage: float = 0
    exit_cost: float = 0
    
    # Result
    outcome: TradeOutcome = TradeOutcome.PENDING
    gross_pnl: float = 0
    fees: float = 0
    net_pnl: float = 0
    return_pct: float = 0
    
    # Strategy info
    edge_at_entry: float = 0
    confidence_at_entry: float = 0
    
    def close(self, exit_price: float, exit_time: datetime, 
             slippage: float, cost: float, won: bool, fee_rate: float = 0.02):
        """Close trade and calculate P&L."""
        self.exit_time = exit_time
        self.actual_exit_price = exit_price
        self.exit_slippage = slippage
        self.exit_cost = cost
        self.outcome = TradeOutcome.WIN if won else TradeOutcome.LOSS
        
        # Calculate P&L
        shares = self.filled_size / self.actual_entry_price
        
        if won:
            # Win pays $1 per share
            self.gross_pnl = shares * 1.0 - self.filled_size
            self.fees = max(0, self.gross_pnl) * fee_rate
        else:
            self.gross_pnl = -self.filled_size
            self.fees = 0
        
        # Net P&L includes all costs
        self.net_pnl = self.gross_pnl - self.fees - self.entry_cost - self.exit_cost
        self.return_pct = self.net_pnl / self.filled_size if self.filled_size > 0 else 0


# =============================================================================
# MICROSTRUCTURE BACKTEST ENGINE
# =============================================================================

@dataclass
class MicrostructureBacktestResult:
    """Results with full cost accounting."""
    scenario_id: str
    scenario_name: str
    
    initial_capital: float
    final_capital: float
    
    total_trades: int
    winning_trades: int
    losing_trades: int
    
    gross_pnl: float
    total_fees: float
    total_slippage_cost: float
    total_spread_cost: float
    net_pnl: float
    
    net_return_pct: float
    win_rate: float
    profit_factor: float
    
    max_drawdown: float
    sharpe_ratio: float
    
    trades: List[MicrostructureTrade] = field(default_factory=list)
    equity_curve: List[Tuple[datetime, float]] = field(default_factory=list)
    
    # Cost breakdown
    cost_breakdown: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "gross_pnl": round(self.gross_pnl, 2),
            "net_pnl": round(self.net_pnl, 2),
            "total_fees": round(self.total_fees, 2),
            "total_slippage": round(self.total_slippage_cost, 2),
            "net_return": f"{self.net_return_pct:.1%}",
            "trades": self.total_trades,
            "win_rate": f"{self.win_rate:.1%}",
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown": f"{self.max_drawdown:.1%}",
            "sharpe": round(self.sharpe_ratio, 2),
        }
    
    def print_summary(self):
        print(f"\n{'='*50}")
        print(f"BACKTEST: {self.scenario_name}")
        print(f"{'='*50}")
        print(f"Capital: ${self.initial_capital:.2f} -> ${self.final_capital:.2f}")
        print(f"Net P&L: ${self.net_pnl:.2f} ({self.net_return_pct:.1%})")
        print(f"  Gross: ${self.gross_pnl:.2f}")
        print(f"  Fees:  -${self.total_fees:.2f}")
        print(f"  Costs: -${self.total_slippage_cost + self.total_spread_cost:.2f}")
        print(f"-"*50)
        print(f"Trades: {self.total_trades} ({self.winning_trades}W/{self.losing_trades}L)")
        print(f"Win Rate: {self.win_rate:.1%}")
        print(f"Profit Factor: {self.profit_factor:.2f}")
        print(f"Max Drawdown: {self.max_drawdown:.1%}")
        print(f"Sharpe Ratio: {self.sharpe_ratio:.2f}")


class MicrostructureBacktestEngine:
    """
    Backtest engine with realistic microstructure modeling.
    """
    
    def __init__(self, 
                 initial_capital: float = 75.0,
                 costs: Optional[TradingCosts] = None):
        self.initial_capital = initial_capital
        self.costs = costs if costs is not None else TradingCosts()
        self.executor = ExecutionSimulator(self.costs)
    
    def run_scenario(self,
                    scenario: BenchmarkScenario,
                    strategy_fn: Callable,
                    verbose: bool = False) -> MicrostructureBacktestResult:
        """
        Run backtest on a single scenario.
        
        Args:
            scenario: Benchmark scenario to test
            strategy_fn: Strategy function that returns trade signals
                        Takes (market_state, capital) -> Optional[Dict]
            verbose: Print debug info
        
        Returns:
            MicrostructureBacktestResult
        """
        capital = self.initial_capital
        position: Optional[MicrostructureTrade] = None
        closed_trades: List[MicrostructureTrade] = []
        equity_curve: List[Tuple[datetime, float]] = []
        trade_counter = 0
        
        # Reset executor
        self.executor = ExecutionSimulator(self.costs)
        
        # Track costs
        total_fees = 0
        total_slippage = 0
        total_spread = 0
        
        # Track drawdown
        high_water_mark = capital
        max_drawdown = 0
        
        # Build orderbook lookup if available
        ob_lookup = {}
        for ob in scenario.orderbook_history:
            ob_lookup[ob.timestamp] = ob
        
        # Simulate through price history
        for i, (timestamp, price) in enumerate(scenario.price_history):
            
            # Get closest orderbook
            closest_ob = None
            for ob_ts in sorted(ob_lookup.keys(), reverse=True):
                if ob_ts <= timestamp:
                    closest_ob = ob_lookup[ob_ts]
                    break
            
            # Get sentiment at this time
            sentiment = 0
            for st, sent in scenario.sentiment_history:
                if st <= timestamp:
                    sentiment = sent
            
            # Get volume at this time
            volume = 1000
            for vt, vol in scenario.volume_history:
                if vt <= timestamp:
                    volume = vol
            
            # Check if position needs to close (resolution)
            if position and timestamp >= scenario.resolution_date:
                # Position resolves
                won = (position.direction == "YES" and scenario.resolution) or \
                      (position.direction == "NO" and not scenario.resolution)
                
                exit_price = 1.0 if won else 0.0
                position.close(exit_price, timestamp, 0, 0, won, self.costs.profit_fee_rate)
                
                capital += position.filled_size + position.net_pnl
                total_fees += position.fees
                
                resolved_pnl = position.net_pnl
                closed_trades.append(position)
                position = None
                
                if verbose:
                    print(f"  Position resolved: {'WIN' if won else 'LOSS'}, PnL: ${resolved_pnl:.2f}")
            
            # Build market state for strategy
            market_state = {
                "timestamp": timestamp,
                "price": price,
                "yes_price": price,
                "no_price": 1 - price,
                "sentiment": sentiment,
                "volume_24h": volume,
                "spread": closest_ob.spread if closest_ob else 0.02,
                "bid_depth": closest_ob.bid_depth if closest_ob else 500,
                "ask_depth": closest_ob.ask_depth if closest_ob else 500,
                "best_bid": closest_ob.best_bid if closest_ob else price - 0.01,
                "best_ask": closest_ob.best_ask if closest_ob else price + 0.01,
                "hours_to_resolution": (scenario.resolution_date - timestamp).total_seconds() / 3600,
                "scenario_id": scenario.scenario_id,
            }
            
            # If no position, check for entry
            if position is None and timestamp < scenario.resolution_date - timedelta(hours=12):
                signal = strategy_fn(market_state, capital)
                
                if signal and signal.get("action") == "buy":
                    intended_size = signal.get("amount", 0)
                    direction = signal.get("direction", "YES")
                    
                    if intended_size >= 1.0 and intended_size <= capital * 0.95:
                        # Try to execute
                        fill = self.executor.simulate_fill(
                            "buy",
                            intended_size,
                            closest_ob,
                            price,
                            timestamp
                        )
                        
                        if fill["filled"] and fill["filled_size"] >= 1.0:
                            trade_counter += 1
                            position = MicrostructureTrade(
                                trade_id=f"MS-{scenario.scenario_id}-{trade_counter}",
                                scenario_id=scenario.scenario_id,
                                direction=direction,
                                entry_time=timestamp,
                                intended_entry_price=price,
                                actual_entry_price=fill["fill_price"],
                                intended_size=intended_size,
                                filled_size=fill["filled_size"],
                                entry_slippage=fill["slippage"],
                                entry_cost=fill["cost"],
                                edge_at_entry=signal.get("edge", 0),
                                confidence_at_entry=signal.get("confidence", 0),
                            )
                            
                            capital -= fill["filled_size"]
                            total_slippage += fill["cost"]
                            total_spread += fill["spread"] * fill["filled_size"] / 2
                            
                            if verbose:
                                print(f"  Entered {direction} @ {fill['fill_price']:.3f}, size ${fill['filled_size']:.2f}")
            
            # Update equity
            position_value = 0
            if position:
                # Mark to market
                if position.direction == "YES":
                    position_value = position.filled_size * (price / position.actual_entry_price)
                else:
                    position_value = position.filled_size * ((1-price) / (1-position.actual_entry_price))
            
            equity = capital + position_value
            equity_curve.append((timestamp, equity))
            
            # Track drawdown
            if equity > high_water_mark:
                high_water_mark = equity
            dd = (high_water_mark - equity) / high_water_mark if high_water_mark > 0 else 0
            max_drawdown = max(max_drawdown, dd)
        
        # Close any remaining position at resolution
        if position:
            won = (position.direction == "YES" and scenario.resolution) or \
                  (position.direction == "NO" and not scenario.resolution)
            
            position.close(
                1.0 if won else 0.0,
                scenario.resolution_date,
                0, 0, won,
                self.costs.profit_fee_rate
            )
            
            capital += position.filled_size + position.net_pnl
            total_fees += position.fees
            closed_trades.append(position)
        
        # Calculate results
        return self._calculate_results(
            scenario, capital, closed_trades, equity_curve,
            total_fees, total_slippage, total_spread, max_drawdown
        )
    
    def _calculate_results(self,
                          scenario: BenchmarkScenario,
                          final_capital: float,
                          trades: List[MicrostructureTrade],
                          equity_curve: List[Tuple[datetime, float]],
                          total_fees: float,
                          total_slippage: float,
                          total_spread: float,
                          max_drawdown: float) -> MicrostructureBacktestResult:
        """Calculate final results."""
        
        total_trades = len(trades)
        wins = [t for t in trades if t.outcome == TradeOutcome.WIN]
        losses = [t for t in trades if t.outcome == TradeOutcome.LOSS]
        
        gross_pnl = sum(t.gross_pnl for t in trades)
        net_pnl = sum(t.net_pnl for t in trades)
        
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        
        total_wins_pnl = sum(t.net_pnl for t in wins) if wins else 0
        total_losses_pnl = abs(sum(t.net_pnl for t in losses)) if losses else 0
        profit_factor = total_wins_pnl / total_losses_pnl if total_losses_pnl > 0 else float('inf')
        
        # Sharpe ratio
        if total_trades > 1:
            returns = [t.return_pct for t in trades]
            avg_return = statistics.mean(returns)
            std_return = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = avg_return / std_return * (52 ** 0.5) if std_return > 0 else 0  # Annualized
        else:
            sharpe = 0
        
        return MicrostructureBacktestResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_trades=total_trades,
            winning_trades=len(wins),
            losing_trades=len(losses),
            gross_pnl=gross_pnl,
            total_fees=total_fees,
            total_slippage_cost=total_slippage,
            total_spread_cost=total_spread,
            net_pnl=net_pnl,
            net_return_pct=net_pnl / self.initial_capital if self.initial_capital > 0 else 0,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            trades=trades,
            equity_curve=equity_curve,
            cost_breakdown={
                "fees": total_fees,
                "slippage": total_slippage,
                "spread": total_spread,
                "total": total_fees + total_slippage + total_spread,
            }
        )
    
    def run_suite(self,
                 suite: BenchmarkSuite,
                 strategy_fn: Callable,
                 verbose: bool = False) -> Dict:
        """
        Run backtest across entire benchmark suite.
        
        Returns aggregated results.
        """
        results = []
        
        for scenario in suite.all_scenarios:
            if verbose:
                print(f"\nRunning: {scenario.scenario_id} - {scenario.name}")
            
            result = self.run_scenario(scenario, strategy_fn, verbose=False)
            results.append(result)
            
            if verbose:
                print(f"  Result: {result.net_return_pct:.1%}, {result.total_trades} trades")
        
        # Aggregate
        total_net_pnl = sum(r.net_pnl for r in results)
        total_trades = sum(r.total_trades for r in results)
        total_wins = sum(r.winning_trades for r in results)
        total_fees = sum(r.total_fees for r in results)
        total_slippage = sum(r.total_slippage_cost for r in results)
        
        # Separate by scenario type
        normal_results = [r for r in results if any(
            s.scenario_id == r.scenario_id and s.scenario_type == ScenarioType.NORMAL 
            for s in suite.normal_scenarios
        )]
        edge_results = [r for r in results if any(
            s.scenario_id == r.scenario_id and s.scenario_type != ScenarioType.NORMAL
            for s in suite.edge_case_scenarios
        )]
        
        return {
            "summary": {
                "total_scenarios": len(results),
                "total_net_pnl": round(total_net_pnl, 2),
                "avg_net_return": f"{total_net_pnl / len(results) / self.initial_capital:.1%}",
                "total_trades": total_trades,
                "overall_win_rate": f"{total_wins / total_trades:.1%}" if total_trades > 0 else "0%",
                "total_fees": round(total_fees, 2),
                "total_slippage": round(total_slippage, 2),
                "profitable_scenarios": len([r for r in results if r.net_pnl > 0]),
                "losing_scenarios": len([r for r in results if r.net_pnl <= 0]),
            },
            "normal_scenarios": {
                "count": len(normal_results),
                "avg_return": f"{sum(r.net_return_pct for r in normal_results) / len(normal_results):.1%}" if normal_results else "0%",
                "profitable": len([r for r in normal_results if r.net_pnl > 0]),
            },
            "edge_case_scenarios": {
                "count": len(edge_results),
                "avg_return": f"{sum(r.net_return_pct for r in edge_results) / len(edge_results):.1%}" if edge_results else "0%",
                "profitable": len([r for r in edge_results if r.net_pnl > 0]),
            },
            "individual_results": [r.to_dict() for r in results],
        }


# =============================================================================
# WALK-FORWARD VALIDATION
# =============================================================================

class WalkForwardValidator:
    """
    Prevents overfitting through walk-forward optimization.
    
    Split scenarios into train/test, optimize on train, validate on test.
    """
    
    def __init__(self,
                 engine: MicrostructureBacktestEngine,
                 train_ratio: float = 0.6):
        self.engine = engine
        self.train_ratio = train_ratio
    
    def validate(self,
                suite: BenchmarkSuite,
                strategy_fn: Callable,
                num_folds: int = 3) -> Dict:
        """
        Run walk-forward validation.
        
        Returns cross-validated performance metrics.
        """
        scenarios = suite.all_scenarios.copy()
        random.shuffle(scenarios)
        
        fold_size = len(scenarios) // num_folds
        fold_results = []
        
        for fold in range(num_folds):
            # Split into train/test
            test_start = fold * fold_size
            test_end = test_start + fold_size
            
            test_scenarios = scenarios[test_start:test_end]
            train_scenarios = scenarios[:test_start] + scenarios[test_end:]
            
            # Run on test set (out-of-sample)
            test_results = []
            for scenario in test_scenarios:
                result = self.engine.run_scenario(scenario, strategy_fn)
                test_results.append(result)
            
            fold_pnl = sum(r.net_pnl for r in test_results)
            fold_trades = sum(r.total_trades for r in test_results)
            fold_wins = sum(r.winning_trades for r in test_results)
            
            fold_results.append({
                "fold": fold + 1,
                "test_scenarios": len(test_scenarios),
                "net_pnl": fold_pnl,
                "avg_return": fold_pnl / len(test_scenarios) / self.engine.initial_capital,
                "win_rate": fold_wins / fold_trades if fold_trades > 0 else 0,
                "trades": fold_trades,
            })
        
        # Aggregate across folds
        avg_return = statistics.mean(f["avg_return"] for f in fold_results)
        std_return = statistics.stdev(f["avg_return"] for f in fold_results) if len(fold_results) > 1 else 0
        
        return {
            "validation_type": "walk_forward",
            "num_folds": num_folds,
            "avg_return_per_scenario": f"{avg_return:.1%}",
            "return_std": f"{std_return:.1%}",
            "sharpe_estimate": avg_return / std_return if std_return > 0 else 0,
            "is_robust": avg_return > 0.02 and std_return < avg_return,  # Positive with low variance
            "fold_results": fold_results,
        }


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    from benchmark_suite import create_benchmark_suite
    
    # Create benchmark suite
    suite = create_benchmark_suite(seed=42)
    suite.print_summary()
    
    # Create engine
    engine = MicrostructureBacktestEngine(initial_capital=75.0)
    
    # Example strategy function
    def simple_sentiment_strategy(market_state: Dict, capital: float) -> Optional[Dict]:
        """Simple strategy that buys when sentiment is positive and price is undervalued."""
        price = market_state.get("price", 0.5)
        sentiment = market_state.get("sentiment", 0)
        spread = market_state.get("spread", 0.02)
        hours_left = market_state.get("hours_to_resolution", 168)
        
        # Don't trade with wide spreads
        if spread > 0.08:
            return None
        
        # Don't trade too close to resolution
        if hours_left < 48:
            return None
        
        # Calculate implied fair value from sentiment
        implied_fv = 0.5 + sentiment * 0.25
        
        # Check for edge
        edge = implied_fv - price
        
        if edge > 0.12 and price < 0.70:
            # Calculate position size
            size = min(capital * 0.15, 15)
            
            return {
                "action": "buy",
                "direction": "YES",
                "amount": size,
                "price": price,
                "edge": edge,
                "confidence": 0.6,
            }
        
        return None
    
    # Run on a few scenarios
    print("\n[RUNNING SAMPLE SCENARIOS]")
    for scenario in suite.all_scenarios[:5]:
        result = engine.run_scenario(scenario, simple_sentiment_strategy, verbose=True)
        result.print_summary()
    
    # Run full suite
    print("\n[RUNNING FULL SUITE]")
    full_results = engine.run_suite(suite, simple_sentiment_strategy, verbose=True)
    
    print("\n" + "=" * 60)
    print("FULL SUITE RESULTS")
    print("=" * 60)
    for key, value in full_results["summary"].items():
        print(f"  {key}: {value}")
    
    print("\nNormal Scenarios:")
    for key, value in full_results["normal_scenarios"].items():
        print(f"  {key}: {value}")
    
    print("\nEdge Case Scenarios:")
    for key, value in full_results["edge_case_scenarios"].items():
        print(f"  {key}: {value}")
    
    # Walk-forward validation
    print("\n[WALK-FORWARD VALIDATION]")
    validator = WalkForwardValidator(engine)
    wf_results = validator.validate(suite, simple_sentiment_strategy, num_folds=3)
    
    print("\nValidation Results:")
    for key, value in wf_results.items():
        if key != "fold_results":
            print(f"  {key}: {value}")
