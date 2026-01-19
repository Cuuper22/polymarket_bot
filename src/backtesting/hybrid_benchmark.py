"""
Hybrid Strategy Benchmark
Combines edge-aware entry signals with swing trading exits (buy low, sell high).
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class HybridScenario:
    """Market scenario with price and sentiment data."""
    name: str
    category: str
    hours: int
    
    # Price data (hourly)
    prices: List[float]
    volumes: List[float]
    
    # Sentiment data (hourly) - simulated
    sentiment_scores: List[float]  # -1 to 1
    
    # Metadata
    initial_price: float
    has_opportunity: bool


@dataclass
class HybridResult:
    """Result from hybrid strategy backtest."""
    scenario_name: str
    initial_capital: float
    final_capital: float
    return_pct: float
    
    total_trades: int
    winning_trades: int
    win_rate: float
    
    total_pnl: float
    max_drawdown: float
    avg_hold_hours: float
    
    trades: List[Dict] = field(default_factory=list)


class HybridScenarioGenerator:
    """Generate scenarios with correlated price and sentiment."""
    
    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)
    
    def generate_correlated_scenario(self, hours: int = 168,
                                     initial_price: float = 0.5,
                                     sentiment_correlation: float = 0.6,
                                     volatility: float = 0.02,
                                     include_dips: bool = True) -> HybridScenario:
        """
        Generate price path with correlated sentiment.
        
        Args:
            hours: Duration
            initial_price: Starting price
            sentiment_correlation: How much sentiment leads price (0-1)
            volatility: Price volatility
            include_dips: Whether to include dip opportunities
        """
        # Generate base sentiment path
        sentiment = [0.0]
        for _ in range(1, hours):
            # Sentiment mean-reverts but has momentum
            new_sent = sentiment[-1] * 0.95 + self.rng.normal(0, 0.15)
            new_sent = max(-1, min(1, new_sent))
            sentiment.append(new_sent)
        
        # Generate price path influenced by sentiment
        prices = [initial_price]
        for i in range(1, hours):
            # Price follows sentiment with lag and noise
            sent_influence = sentiment[max(0, i-3)] * 0.01 * sentiment_correlation
            noise = self.rng.normal(0, volatility)
            
            new_price = prices[-1] * (1 + sent_influence + noise)
            new_price = max(0.05, min(0.95, new_price))
            prices.append(new_price)
        
        # Add dip opportunities (sentiment stays positive but price drops)
        if include_dips:
            num_dips = self.rng.randint(1, 4)
            for _ in range(num_dips):
                dip_hour = self.rng.randint(24, hours - 24)
                dip_size = self.rng.uniform(0.08, 0.20)
                
                # Drop price
                prices[dip_hour] *= (1 - dip_size)
                
                # Keep sentiment positive (this is the opportunity)
                sentiment[dip_hour] = abs(sentiment[dip_hour]) * 0.5 + 0.3
                
                # Recovery over next hours
                recovery_hours = self.rng.randint(6, 18)
                for j in range(1, min(recovery_hours, hours - dip_hour)):
                    recovery = dip_size * (j / recovery_hours) * 0.8
                    prices[dip_hour + j] = prices[dip_hour] * (1 + recovery)
        
        # Clamp prices
        prices = [max(0.05, min(0.95, p)) for p in prices]
        
        # Generate volumes
        volumes = [self.rng.uniform(500, 3000) for _ in range(hours)]
        
        return HybridScenario(
            name=f"correlated_{self.rng.randint(10000)}",
            category="normal",
            hours=hours,
            prices=prices,
            volumes=volumes,
            sentiment_scores=sentiment,
            initial_price=initial_price,
            has_opportunity=include_dips,
        )
    
    def generate_sentiment_trap(self, hours: int = 168) -> HybridScenario:
        """
        Generate scenario where sentiment is wrong (trap).
        Price dips but sentiment is also negative - avoid this.
        """
        prices = [0.55]
        sentiment = [0.0]
        
        for i in range(1, hours):
            # Gradual decline with negative sentiment
            prices.append(prices[-1] * (1 + self.rng.normal(-0.002, 0.015)))
            sentiment.append(max(-1, sentiment[-1] * 0.9 + self.rng.normal(-0.1, 0.1)))
        
        prices = [max(0.05, min(0.95, p)) for p in prices]
        volumes = [self.rng.uniform(300, 1500) for _ in range(hours)]
        
        return HybridScenario(
            name="sentiment_trap",
            category="edge_case",
            hours=hours,
            prices=prices,
            volumes=volumes,
            sentiment_scores=sentiment,
            initial_price=prices[0],
            has_opportunity=False,  # Should NOT trade this
        )
    
    def generate_momentum_scenario(self, direction: str = "up",
                                   hours: int = 168) -> HybridScenario:
        """Generate strong momentum scenario."""
        drift = 0.003 if direction == "up" else -0.003
        sent_bias = 0.3 if direction == "up" else -0.3
        
        prices = [0.45 if direction == "up" else 0.55]
        sentiment = [sent_bias]
        
        for i in range(1, hours):
            prices.append(prices[-1] * (1 + self.rng.normal(drift, 0.012)))
            sentiment.append(max(-1, min(1, sent_bias + self.rng.normal(0, 0.1))))
        
        prices = [max(0.05, min(0.95, p)) for p in prices]
        volumes = [self.rng.uniform(1000, 4000) for _ in range(hours)]
        
        return HybridScenario(
            name=f"momentum_{direction}",
            category="normal",
            hours=hours,
            prices=prices,
            volumes=volumes,
            sentiment_scores=sentiment,
            initial_price=prices[0],
            has_opportunity=direction == "up",
        )
    
    def generate_all(self) -> List[HybridScenario]:
        """Generate all scenario types."""
        scenarios = []
        
        # Multiple correlated scenarios with dips
        for i in range(5):
            self.rng = np.random.RandomState(42 + i)
            scenarios.append(self.generate_correlated_scenario(
                initial_price=self.rng.uniform(0.35, 0.65),
                include_dips=True
            ))
        
        # Scenarios without clear dips
        for i in range(3):
            self.rng = np.random.RandomState(100 + i)
            scenarios.append(self.generate_correlated_scenario(
                include_dips=False
            ))
        
        # Traps
        self.rng = np.random.RandomState(200)
        scenarios.append(self.generate_sentiment_trap())
        
        # Momentum
        self.rng = np.random.RandomState(300)
        scenarios.append(self.generate_momentum_scenario("up"))
        scenarios.append(self.generate_momentum_scenario("down"))
        
        return scenarios


class HybridBacktestEngine:
    """
    Backtest engine for hybrid strategy.
    
    Entry: Buy when price dips AND sentiment is positive (divergence)
    Exit: Sell on price recovery (take profit) or stop loss
    """
    
    def __init__(self, initial_capital: float = 75.0,
                 min_dip_pct: float = 0.08,
                 min_sentiment: float = 0.1,
                 take_profit_pct: float = 0.08,
                 stop_loss_pct: float = 0.15,
                 max_hold_hours: int = 24,
                 position_size_pct: float = 0.10,
                 max_positions: int = 6,
                 fee_rate: float = 0.02):
        
        self.initial_capital = initial_capital
        self.min_dip_pct = min_dip_pct
        self.min_sentiment = min_sentiment
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_hours = max_hold_hours
        self.position_size_pct = position_size_pct
        self.max_positions = max_positions
        self.fee_rate = fee_rate
    
    def run_backtest(self, scenario: HybridScenario) -> HybridResult:
        """Run backtest on a scenario."""
        capital = self.initial_capital
        positions = []  # List of active positions
        trades = []
        high_water = capital
        max_dd = 0
        
        for hour in range(24, scenario.hours):
            price = scenario.prices[hour]
            sentiment = scenario.sentiment_scores[hour]
            volume = scenario.volumes[hour]
            
            # Check exits first
            for pos in list(positions):
                entry_price = pos['entry_price']
                hold_hours = hour - pos['entry_hour']
                return_pct = (price - entry_price) / entry_price
                
                should_exit = False
                reason = ""
                
                if return_pct >= self.take_profit_pct:
                    should_exit = True
                    reason = "take_profit"
                elif return_pct <= -self.stop_loss_pct:
                    should_exit = True
                    reason = "stop_loss"
                elif hold_hours >= self.max_hold_hours:
                    should_exit = True
                    reason = "time_exit"
                
                if should_exit:
                    shares = pos['amount'] / entry_price
                    pnl = shares * price - pos['amount']
                    if pnl > 0:
                        pnl *= (1 - self.fee_rate)
                    
                    trades.append({
                        'entry_hour': pos['entry_hour'],
                        'exit_hour': hour,
                        'entry_price': entry_price,
                        'exit_price': price,
                        'amount': pos['amount'],
                        'pnl': pnl,
                        'return_pct': return_pct,
                        'reason': reason,
                        'sentiment_at_entry': pos['sentiment'],
                    })
                    
                    capital += pos['amount'] + pnl
                    positions.remove(pos)
            
            # Check entry
            if len(positions) < self.max_positions and volume >= 500:
                # Calculate dip from 24h high
                window = scenario.prices[max(0, hour-24):hour]
                window_high = max(window) if window else price
                dip_pct = (window_high - price) / window_high if window_high > 0 else 0
                
                # Entry condition: price dipped AND sentiment is positive
                if dip_pct >= self.min_dip_pct and sentiment >= self.min_sentiment:
                    amount = min(capital * self.position_size_pct, 15.0)
                    amount = max(3.0, amount)
                    
                    if amount <= capital * 0.95:
                        positions.append({
                            'entry_hour': hour,
                            'entry_price': price,
                            'amount': amount,
                            'dip_pct': dip_pct,
                            'sentiment': sentiment,
                        })
                        capital -= amount
            
            # Track drawdown
            equity = capital + sum(
                (p['amount'] / p['entry_price']) * price 
                for p in positions
            )
            if equity > high_water:
                high_water = equity
            dd = (high_water - equity) / high_water if high_water > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Close remaining positions
        final_price = scenario.prices[-1]
        for pos in positions:
            shares = pos['amount'] / pos['entry_price']
            pnl = shares * final_price - pos['amount']
            if pnl > 0:
                pnl *= (1 - self.fee_rate)
            trades.append({
                'entry_hour': pos['entry_hour'],
                'exit_hour': scenario.hours - 1,
                'entry_price': pos['entry_price'],
                'exit_price': final_price,
                'amount': pos['amount'],
                'pnl': pnl,
                'return_pct': (final_price - pos['entry_price']) / pos['entry_price'],
                'reason': 'end',
                'sentiment_at_entry': pos['sentiment'],
            })
            capital += pos['amount'] + pnl
        
        # Calculate metrics
        winning = [t for t in trades if t['pnl'] > 0]
        
        return HybridResult(
            scenario_name=scenario.name,
            initial_capital=self.initial_capital,
            final_capital=capital,
            return_pct=(capital - self.initial_capital) / self.initial_capital,
            total_trades=len(trades),
            winning_trades=len(winning),
            win_rate=len(winning) / len(trades) if trades else 0,
            total_pnl=sum(t['pnl'] for t in trades),
            max_drawdown=max_dd,
            avg_hold_hours=np.mean([t['exit_hour'] - t['entry_hour'] for t in trades]) if trades else 0,
            trades=trades,
        )


def run_hybrid_benchmark(num_seeds: int = 100) -> Dict:
    """Run multi-seed hybrid benchmark."""
    all_returns = []
    all_win_rates = []
    
    print(f"Running {num_seeds}-seed hybrid benchmark...")
    
    for seed in range(num_seeds):
        if (seed + 1) % 20 == 0:
            print(f"  Seed {seed + 1}/{num_seeds}...")
        
        generator = HybridScenarioGenerator(seed=seed)
        scenarios = generator.generate_all()
        
        engine = HybridBacktestEngine(
            initial_capital=75.0,
            min_dip_pct=0.08,
            min_sentiment=0.1,  # Require positive sentiment
            take_profit_pct=0.08,
            stop_loss_pct=0.15,
            max_hold_hours=24,
        )
        
        seed_pnl = 0
        seed_trades = 0
        seed_wins = 0
        
        for scenario in scenarios:
            result = engine.run_backtest(scenario)
            seed_pnl += result.total_pnl
            seed_trades += result.total_trades
            seed_wins += result.winning_trades
        
        all_returns.append(seed_pnl / 75.0)  # Return as fraction
        if seed_trades > 0:
            all_win_rates.append(seed_wins / seed_trades)
    
    return {
        'num_seeds': num_seeds,
        'mean_return': np.mean(all_returns),
        'median_return': np.median(all_returns),
        'std_return': np.std(all_returns),
        'min_return': np.min(all_returns),
        'max_return': np.max(all_returns),
        'mean_win_rate': np.mean(all_win_rates),
        'positive_seeds': sum(1 for r in all_returns if r > 0),
        'above_5pct': sum(1 for r in all_returns if r > 0.05),
        'above_10pct': sum(1 for r in all_returns if r > 0.10),
    }


def run_hybrid_monte_carlo(num_sims: int = 1000) -> Dict:
    """Run Monte Carlo simulation of hybrid strategy."""
    results = []
    
    print(f"Running {num_sims} hybrid Monte Carlo simulations...")
    
    for sim in range(num_sims):
        if (sim + 1) % 100 == 0:
            print(f"  Simulation {sim + 1}/{num_sims}...")
        
        seed = sim * 7919
        generator = HybridScenarioGenerator(seed=seed)
        
        # Generate random scenario
        rng = np.random.RandomState(seed)
        scenario = generator.generate_correlated_scenario(
            hours=168,
            initial_price=rng.uniform(0.30, 0.70),
            sentiment_correlation=rng.uniform(0.3, 0.8),
            volatility=rng.uniform(0.01, 0.03),
            include_dips=rng.random() > 0.3,  # 70% chance of dips
        )
        
        engine = HybridBacktestEngine(
            initial_capital=75.0,
            min_dip_pct=0.08,
            min_sentiment=0.1,
            take_profit_pct=0.08,
            stop_loss_pct=0.15,
            max_hold_hours=24,
        )
        
        result = engine.run_backtest(scenario)
        results.append({
            'return_pct': result.return_pct,
            'trades': result.total_trades,
            'win_rate': result.win_rate,
            'max_dd': result.max_drawdown,
        })
    
    returns = [r['return_pct'] for r in results]
    
    return {
        'num_sims': num_sims,
        'mean_return': np.mean(returns),
        'median_return': np.median(returns),
        'std_return': np.std(returns),
        'pct_5': np.percentile(returns, 5),
        'pct_95': np.percentile(returns, 95),
        'positive_weeks': sum(1 for r in returns if r > 0) / len(returns),
        'above_5pct': sum(1 for r in returns if r > 0.05) / len(returns),
        'above_10pct': sum(1 for r in returns if r > 0.10) / len(returns),
        'negative_weeks': sum(1 for r in returns if r < 0) / len(returns),
        'mean_trades': np.mean([r['trades'] for r in results]),
        'mean_win_rate': np.mean([r['win_rate'] for r in results if r['trades'] > 0]),
    }


if __name__ == "__main__":
    print("Testing hybrid benchmark...")
    result = run_hybrid_benchmark(num_seeds=10)
    print(f"Mean return: {result['mean_return']:.2%}")
