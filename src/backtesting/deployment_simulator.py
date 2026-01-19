"""
Realistic Deployment Simulator
==============================
Simulates actual HFT deployment conditions:
- 24/7 trading for 1 week
- Thousands of markets to choose from
- Position limits (10 max positions/hour)
- Minimum trade size ($3)
- Maximum exposure (75%)
- Realistic market flow and resolution timing

Run 1000 simulations to get statistical distribution of outcomes.
"""
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import math


@dataclass
class DeploymentConfig:
    """Deployment constraints matching real-world conditions."""
    initial_capital: float = 75.0
    
    # Position limits
    max_positions_per_hour: int = 10
    max_concurrent_positions: int = 6
    max_exposure_pct: float = 0.75      # 75% max deployed
    
    # Trade sizing
    min_trade_size: float = 3.0
    max_trade_size: float = 40.0
    
    # Market universe
    markets_available: int = 500        # Simulated open markets at any time
    new_markets_per_hour: int = 5       # New markets appearing
    resolving_markets_per_hour: int = 3 # Markets resolving
    
    # Timing
    simulation_hours: int = 168         # 1 week = 168 hours
    check_interval_minutes: int = 15    # Check markets every 15 min
    
    # Trading costs
    profit_fee_rate: float = 0.02
    spread_cost: float = 0.008
    slippage: float = 0.003


@dataclass
class SimulatedMarket:
    """A simulated market in the universe."""
    market_id: str
    question: str
    yes_price: float
    sentiment: float
    volume_24h: float
    spread: float
    hours_to_resolution: float
    true_probability: float  # Hidden true outcome probability
    resolution: Optional[bool] = None  # Set when resolved
    created_at: datetime = field(default_factory=datetime.now)
    
    def will_resolve_yes(self) -> bool:
        """Determine resolution based on true probability."""
        if self.resolution is None:
            self.resolution = random.random() < self.true_probability
        return self.resolution


@dataclass
class Position:
    """An open position."""
    market_id: str
    direction: str
    entry_price: float
    size: float
    entry_time: datetime
    target_resolution: datetime


@dataclass
class TradeResult:
    """Result of a closed trade."""
    market_id: str
    direction: str
    entry_price: float
    exit_price: float
    size: float
    gross_pnl: float
    fees: float
    net_pnl: float
    hold_hours: float
    won: bool


class MarketUniverse:
    """
    Simulates thousands of Polymarket markets.
    """
    
    def __init__(self, config: DeploymentConfig, seed: int = None):
        self.config = config
        if seed is not None:
            random.seed(seed)
        
        self.markets: Dict[str, SimulatedMarket] = {}
        self.market_counter = 0
        
        # Initialize with starting markets
        self._initialize_markets()
    
    def _initialize_markets(self):
        """Create initial market universe."""
        for _ in range(self.config.markets_available):
            self._create_market(datetime.now())
    
    def _create_market(self, current_time: datetime) -> SimulatedMarket:
        """Create a new random market."""
        self.market_counter += 1
        
        # Random market characteristics
        true_prob = random.uniform(0.15, 0.85)
        
        # Price is noisy estimate of true probability
        noise = random.gauss(0, 0.12)
        yes_price = max(0.05, min(0.95, true_prob + noise))
        
        # Sentiment somewhat correlated with true probability
        sentiment_base = (true_prob - 0.5) * 1.5
        sentiment = max(-1, min(1, sentiment_base + random.gauss(0, 0.25)))
        
        # Market quality varies
        volume = random.lognormvariate(7, 1.5)  # Log-normal volume
        spread = random.uniform(0.01, 0.08)
        
        # Resolution timing
        hours_to_resolution = random.uniform(24, 336)  # 1-14 days
        
        market = SimulatedMarket(
            market_id=f"MKT-{self.market_counter:06d}",
            question=f"Simulated Market {self.market_counter}",
            yes_price=yes_price,
            sentiment=sentiment,
            volume_24h=volume,
            spread=spread,
            hours_to_resolution=hours_to_resolution,
            true_probability=true_prob,
            created_at=current_time,
        )
        
        self.markets[market.market_id] = market
        return market
    
    def update(self, current_time: datetime, elapsed_hours: float):
        """
        Update market universe - add new markets, resolve old ones.
        """
        # Add new markets
        new_markets = int(self.config.new_markets_per_hour * elapsed_hours)
        for _ in range(new_markets):
            self._create_market(current_time)
        
        # Update existing markets
        to_remove = []
        for market_id, market in self.markets.items():
            # Update hours to resolution
            market.hours_to_resolution -= elapsed_hours
            
            # Price drift towards true value as resolution approaches
            if market.hours_to_resolution > 0:
                drift_factor = elapsed_hours / market.hours_to_resolution
                drift = (market.true_probability - market.yes_price) * drift_factor * 0.3
                market.yes_price = max(0.05, min(0.95, market.yes_price + drift + random.gauss(0, 0.01)))
                
                # Sentiment also drifts
                sent_drift = ((market.true_probability - 0.5) * 2 - market.sentiment) * drift_factor * 0.2
                market.sentiment = max(-1, min(1, market.sentiment + sent_drift + random.gauss(0, 0.05)))
            
            # Mark for removal if resolved
            if market.hours_to_resolution <= 0:
                market.will_resolve_yes()  # Trigger resolution
                to_remove.append(market_id)
        
        # Remove resolved markets (but keep reference for position settlement)
        # Don't actually remove - positions need to reference them
    
    def get_tradeable_markets(self, min_hours: int = 24) -> List[SimulatedMarket]:
        """Get markets that are tradeable (not too close to resolution)."""
        return [
            m for m in self.markets.values()
            if m.hours_to_resolution >= min_hours and m.resolution is None
        ]
    
    def get_market(self, market_id: str) -> Optional[SimulatedMarket]:
        """Get a specific market."""
        return self.markets.get(market_id)


class DeploymentSimulator:
    """
    Simulates realistic deployment of the trading strategy.
    """
    
    def __init__(self, 
                 strategy_fn: Callable,
                 config: DeploymentConfig = None):
        self.strategy_fn = strategy_fn
        self.config = config or DeploymentConfig()
    
    def run_simulation(self, seed: int = None) -> Dict:
        """
        Run a single week-long simulation.
        
        Returns performance metrics.
        """
        if seed is not None:
            random.seed(seed)
        
        # Initialize
        universe = MarketUniverse(self.config, seed)
        capital = self.config.initial_capital
        positions: Dict[str, Position] = {}
        closed_trades: List[TradeResult] = []
        
        # Tracking
        equity_curve = []
        hourly_positions_opened = 0
        current_hour = 0
        
        # Time simulation
        start_time = datetime.now()
        current_time = start_time
        end_time = start_time + timedelta(hours=self.config.simulation_hours)
        
        interval_hours = self.config.check_interval_minutes / 60
        
        while current_time < end_time:
            # Reset hourly counter
            elapsed_hours = (current_time - start_time).total_seconds() / 3600
            new_hour = int(elapsed_hours)
            if new_hour > current_hour:
                current_hour = new_hour
                hourly_positions_opened = 0
            
            # Update market universe
            universe.update(current_time, interval_hours)
            
            # Check for position resolutions
            positions_to_close = []
            for market_id, position in positions.items():
                market = universe.get_market(market_id)
                if market and market.resolution is not None:
                    positions_to_close.append((market_id, market))
            
            # Close resolved positions
            for market_id, market in positions_to_close:
                position = positions[market_id]
                won = (position.direction == "YES" and market.resolution) or \
                      (position.direction == "NO" and not market.resolution)
                
                exit_price = 1.0 if won else 0.0
                gross_pnl = (exit_price - position.entry_price) * position.size / position.entry_price if position.direction == "YES" else \
                           ((1-exit_price) - (1-position.entry_price)) * position.size / (1-position.entry_price)
                
                fees = max(0, gross_pnl) * self.config.profit_fee_rate
                net_pnl = gross_pnl - fees
                
                capital += position.size + net_pnl
                
                closed_trades.append(TradeResult(
                    market_id=market_id,
                    direction=position.direction,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    size=position.size,
                    gross_pnl=gross_pnl,
                    fees=fees,
                    net_pnl=net_pnl,
                    hold_hours=(current_time - position.entry_time).total_seconds() / 3600,
                    won=won,
                ))
                
                del positions[market_id]
            
            # Calculate current exposure
            invested = sum(p.size for p in positions.values())
            exposure_pct = invested / capital if capital > 0 else 1.0
            
            # Look for new opportunities
            if (hourly_positions_opened < self.config.max_positions_per_hour and
                len(positions) < self.config.max_concurrent_positions and
                exposure_pct < self.config.max_exposure_pct):
                
                tradeable = universe.get_tradeable_markets(min_hours=48)
                
                # Score and rank markets
                opportunities = []
                for market in tradeable:
                    if market.market_id in positions:
                        continue
                    
                    # Build market state for strategy
                    market_state = {
                        "price": market.yes_price,
                        "sentiment": market.sentiment,
                        "volume_24h": market.volume_24h,
                        "spread": market.spread,
                        "hours_to_resolution": market.hours_to_resolution,
                    }
                    
                    # Get signal from strategy
                    available_capital = capital - invested
                    signal = self.strategy_fn(market_state, available_capital)
                    
                    if signal and signal.get("action") == "buy":
                        opportunities.append((market, signal))
                
                # Take best opportunities up to limits
                opportunities.sort(key=lambda x: x[1].get("edge", 0) * x[1].get("confidence", 0), reverse=True)
                
                for market, signal in opportunities[:3]:  # Max 3 per check
                    if hourly_positions_opened >= self.config.max_positions_per_hour:
                        break
                    if len(positions) >= self.config.max_concurrent_positions:
                        break
                    
                    invested = sum(p.size for p in positions.values())
                    if invested / capital >= self.config.max_exposure_pct:
                        break
                    
                    # Validate size
                    size = signal.get("amount", 0)
                    size = max(self.config.min_trade_size, size)
                    size = min(self.config.max_trade_size, size)
                    size = min(size, (capital * self.config.max_exposure_pct) - invested)
                    
                    if size < self.config.min_trade_size:
                        continue
                    
                    # Apply entry costs
                    entry_cost = size * (self.config.spread_cost + self.config.slippage)
                    entry_price = signal.get("price", market.yes_price)
                    if signal.get("direction") == "YES":
                        entry_price += self.config.spread_cost / 2
                    else:
                        entry_price = 1 - market.yes_price + self.config.spread_cost / 2
                    
                    # Open position
                    positions[market.market_id] = Position(
                        market_id=market.market_id,
                        direction=signal.get("direction", "YES"),
                        entry_price=entry_price,
                        size=size,
                        entry_time=current_time,
                        target_resolution=current_time + timedelta(hours=market.hours_to_resolution),
                    )
                    
                    capital -= size
                    hourly_positions_opened += 1
            
            # Record equity
            mark_to_market = sum(
                p.size * (universe.get_market(p.market_id).yes_price / p.entry_price if p.direction == "YES" 
                         else (1 - universe.get_market(p.market_id).yes_price) / (1 - p.entry_price))
                for p in positions.values()
                if universe.get_market(p.market_id)
            )
            equity = capital + mark_to_market
            equity_curve.append((current_time, equity))
            
            # Advance time
            current_time += timedelta(minutes=self.config.check_interval_minutes)
        
        # Close any remaining positions at current prices (simulate early exit)
        for market_id, position in list(positions.items()):
            market = universe.get_market(market_id)
            if market:
                # Exit at current price with slippage
                if position.direction == "YES":
                    exit_price = market.yes_price - self.config.spread_cost / 2 - self.config.slippage
                else:
                    exit_price = (1 - market.yes_price) - self.config.spread_cost / 2 - self.config.slippage
                
                gross_pnl = (exit_price - position.entry_price) * position.size / position.entry_price
                fees = max(0, gross_pnl) * self.config.profit_fee_rate
                net_pnl = gross_pnl - fees
                
                capital += position.size + net_pnl
                
                closed_trades.append(TradeResult(
                    market_id=market_id,
                    direction=position.direction,
                    entry_price=position.entry_price,
                    exit_price=exit_price,
                    size=position.size,
                    gross_pnl=gross_pnl,
                    fees=fees,
                    net_pnl=net_pnl,
                    hold_hours=(current_time - position.entry_time).total_seconds() / 3600,
                    won=gross_pnl > 0,
                ))
        
        # Calculate metrics
        return self._calculate_metrics(closed_trades, equity_curve, capital)
    
    def _calculate_metrics(self, trades: List[TradeResult], 
                          equity_curve: List[Tuple], 
                          final_capital: float) -> Dict:
        """Calculate performance metrics."""
        
        if not trades:
            return {
                "final_capital": final_capital,
                "total_return_pct": (final_capital - self.config.initial_capital) / self.config.initial_capital * 100,
                "total_trades": 0,
                "win_rate": 0,
                "avg_trade_pnl": 0,
                "total_fees": 0,
                "max_drawdown": 0,
                "sharpe": 0,
            }
        
        total_pnl = sum(t.net_pnl for t in trades)
        wins = [t for t in trades if t.won]
        losses = [t for t in trades if not t.won]
        
        # Drawdown
        peak = self.config.initial_capital
        max_dd = 0
        for _, equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)
        
        # Sharpe (simplified)
        if len(trades) > 1:
            returns = [t.net_pnl / t.size for t in trades]
            avg_ret = statistics.mean(returns)
            std_ret = statistics.stdev(returns) if len(returns) > 1 else 1
            sharpe = avg_ret / std_ret * (52 ** 0.5) if std_ret > 0 else 0
        else:
            sharpe = 0
        
        return {
            "final_capital": round(final_capital, 2),
            "total_return_pct": round((final_capital - self.config.initial_capital) / self.config.initial_capital * 100, 2),
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "avg_trade_pnl": round(statistics.mean([t.net_pnl for t in trades]), 2),
            "total_fees": round(sum(t.fees for t in trades), 2),
            "max_drawdown": round(max_dd * 100, 1),
            "sharpe": round(sharpe, 2),
            "avg_hold_hours": round(statistics.mean([t.hold_hours for t in trades]), 1),
        }
    
    def run_monte_carlo(self, num_simulations: int = 1000, 
                       progress_interval: int = 100) -> Dict:
        """
        Run Monte Carlo simulation with many trials.
        """
        results = []
        
        for i in range(num_simulations):
            seed = i * 17 + 42  # Deterministic but varied seeds
            result = self.run_simulation(seed=seed)
            results.append(result)
            
            if (i + 1) % progress_interval == 0:
                print(f"  Completed {i + 1}/{num_simulations} simulations...")
        
        # Aggregate statistics
        returns = [r["total_return_pct"] for r in results]
        win_rates = [r["win_rate"] for r in results]
        drawdowns = [r["max_drawdown"] for r in results]
        trade_counts = [r["total_trades"] for r in results]
        
        return {
            "simulations": num_simulations,
            "returns": {
                "mean": round(statistics.mean(returns), 2),
                "median": round(statistics.median(returns), 2),
                "std": round(statistics.stdev(returns), 2),
                "min": round(min(returns), 2),
                "max": round(max(returns), 2),
                "p5": round(sorted(returns)[int(num_simulations * 0.05)], 2),
                "p25": round(sorted(returns)[int(num_simulations * 0.25)], 2),
                "p75": round(sorted(returns)[int(num_simulations * 0.75)], 2),
                "p95": round(sorted(returns)[int(num_simulations * 0.95)], 2),
            },
            "win_rate": {
                "mean": round(statistics.mean(win_rates), 1),
                "min": round(min(win_rates), 1),
                "max": round(max(win_rates), 1),
            },
            "drawdown": {
                "mean": round(statistics.mean(drawdowns), 1),
                "max": round(max(drawdowns), 1),
            },
            "trades": {
                "mean": round(statistics.mean(trade_counts), 1),
                "min": min(trade_counts),
                "max": max(trade_counts),
            },
            "distribution": {
                "negative": len([r for r in returns if r < 0]),
                "0_to_5": len([r for r in returns if 0 <= r < 5]),
                "5_to_10": len([r for r in returns if 5 <= r < 10]),
                "10_to_15": len([r for r in returns if 10 <= r < 15]),
                "15_to_20": len([r for r in returns if 15 <= r < 20]),
                "20_plus": len([r for r in returns if r >= 20]),
            },
            "individual_results": results,
        }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '.')
    
    from strategies.edge_aware_strategy import create_edge_aware_strategy, get_edge_aware_signal_fn
    
    print("Creating strategy...")
    strategy = create_edge_aware_strategy()
    signal_fn = get_edge_aware_signal_fn(strategy)
    
    print("Running single simulation...")
    config = DeploymentConfig()
    simulator = DeploymentSimulator(signal_fn, config)
    
    result = simulator.run_simulation(seed=42)
    print(f"\nSingle Run Results:")
    for k, v in result.items():
        print(f"  {k}: {v}")
