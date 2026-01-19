"""
Swing Trading Strategy Benchmark Suite
Tests buy-low-sell-high strategy across various market conditions.
"""
import random
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class SwingScenario:
    """A market scenario for swing trading backtesting."""
    name: str
    category: str  # 'normal', 'edge_case'
    description: str
    
    # Price path
    prices: List[float]  # Hourly prices over test period
    volumes: List[float]  # Hourly volumes
    
    # Metadata
    initial_price: float
    final_price: float
    volatility: float
    max_drawdown: float
    max_runup: float
    
    # Expected behavior
    has_dip_opportunity: bool
    expected_trades: int  # Approximate expected trades


@dataclass 
class SwingBacktestResult:
    """Result from backtesting a swing strategy."""
    scenario_name: str
    initial_capital: float
    final_capital: float
    return_pct: float
    
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    
    max_drawdown: float
    avg_hold_hours: float
    
    # Trade details
    trades: List[Dict] = field(default_factory=list)


class SwingScenarioGenerator:
    """Generate realistic market scenarios for swing strategy testing."""
    
    def __init__(self, seed: int = 42):
        self.rng = np.random.RandomState(seed)
        random.seed(seed)
    
    def generate_price_path(self, hours: int = 168, initial_price: float = 0.5,
                           volatility: float = 0.02, drift: float = 0.0,
                           dips: List[Tuple[int, float]] = None,
                           pumps: List[Tuple[int, float]] = None) -> List[float]:
        """
        Generate a realistic price path.
        
        Args:
            hours: Number of hours
            initial_price: Starting price
            volatility: Hourly volatility (std dev of returns)
            drift: Hourly drift (positive = upward trend)
            dips: List of (hour, magnitude) for forced dips
            pumps: List of (hour, magnitude) for forced pumps
            
        Returns:
            List of hourly prices
        """
        prices = [initial_price]
        
        for i in range(1, hours):
            # Base random walk
            return_pct = self.rng.normal(drift, volatility)
            new_price = prices[-1] * (1 + return_pct)
            
            # Apply forced dips
            if dips:
                for dip_hour, dip_mag in dips:
                    if i == dip_hour:
                        new_price *= (1 - dip_mag)
            
            # Apply forced pumps
            if pumps:
                for pump_hour, pump_mag in pumps:
                    if i == pump_hour:
                        new_price *= (1 + pump_mag)
            
            # Clamp to valid range
            new_price = max(0.05, min(0.95, new_price))
            prices.append(new_price)
        
        return prices
    
    def generate_volume_path(self, hours: int = 168, base_volume: float = 1000,
                            volatility: float = 0.3) -> List[float]:
        """Generate realistic volume path."""
        volumes = []
        for _ in range(hours):
            vol = base_volume * (1 + self.rng.normal(0, volatility))
            volumes.append(max(100, vol))
        return volumes
    
    def create_dip_recovery_scenario(self) -> SwingScenario:
        """Scenario: Price dips then recovers - ideal for swing trading."""
        # Create a pattern with clear dip and recovery
        dips = [(24, 0.15), (72, 0.12)]  # Dips at 24h and 72h
        pumps = [(36, 0.10), (96, 0.08)]  # Recoveries
        
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.50,
            volatility=0.015,
            drift=0.001,
            dips=dips,
            pumps=pumps
        )
        
        volumes = self.generate_volume_path(168, 1500)
        
        return SwingScenario(
            name="dip_recovery",
            category="normal",
            description="Classic dip and recovery pattern - ideal for swing trading",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,
            expected_trades=3,
        )
    
    def create_trending_up_scenario(self) -> SwingScenario:
        """Scenario: Strong uptrend with small pullbacks."""
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.40,
            volatility=0.012,
            drift=0.003,  # Strong upward drift
        )
        volumes = self.generate_volume_path(168, 2000)
        
        return SwingScenario(
            name="trending_up",
            category="normal",
            description="Strong uptrend with minor pullbacks",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,
            expected_trades=2,
        )
    
    def create_trending_down_scenario(self) -> SwingScenario:
        """Scenario: Downtrend - dip buys get stopped out."""
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.60,
            volatility=0.015,
            drift=-0.003,  # Downward drift
        )
        volumes = self.generate_volume_path(168, 1200)
        
        return SwingScenario(
            name="trending_down",
            category="normal",
            description="Downtrend - dip buying fails",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,  # Dips exist but don't recover
            expected_trades=2,
        )
    
    def create_ranging_scenario(self) -> SwingScenario:
        """Scenario: Sideways range-bound market."""
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.50,
            volatility=0.008,
            drift=0.0,
        )
        volumes = self.generate_volume_path(168, 800)
        
        return SwingScenario(
            name="ranging",
            category="normal",
            description="Sideways range-bound market",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=False,  # Small moves, not enough for swing
            expected_trades=1,
        )
    
    def create_high_volatility_scenario(self) -> SwingScenario:
        """Scenario: High volatility with large swings."""
        dips = [(12, 0.20), (48, 0.18), (100, 0.15)]
        pumps = [(24, 0.15), (60, 0.12), (120, 0.10)]
        
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.50,
            volatility=0.025,
            drift=0.0,
            dips=dips,
            pumps=pumps
        )
        volumes = self.generate_volume_path(168, 3000)
        
        return SwingScenario(
            name="high_volatility",
            category="normal",
            description="High volatility with large swings",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,
            expected_trades=5,
        )
    
    def create_flash_crash_scenario(self) -> SwingScenario:
        """Edge case: Sudden flash crash and recovery."""
        dips = [(36, 0.35)]  # 35% flash crash
        pumps = [(40, 0.25)]  # Partial recovery
        
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.55,
            volatility=0.01,
            drift=0.001,
            dips=dips,
            pumps=pumps
        )
        volumes = self.generate_volume_path(168, 5000)
        
        return SwingScenario(
            name="flash_crash",
            category="edge_case",
            description="Flash crash followed by recovery",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,
            expected_trades=1,
        )
    
    def create_dead_cat_bounce_scenario(self) -> SwingScenario:
        """Edge case: Price crashes, bounces, then continues down."""
        prices = [0.60]
        # Initial decline
        for i in range(40):
            prices.append(prices[-1] * (1 + self.rng.normal(-0.003, 0.01)))
        # Bounce (trap for dip buyers)
        for i in range(20):
            prices.append(prices[-1] * (1 + self.rng.normal(0.004, 0.01)))
        # Continue down
        for i in range(108):
            prices.append(prices[-1] * (1 + self.rng.normal(-0.002, 0.01)))
        
        prices = [max(0.05, min(0.95, p)) for p in prices]
        volumes = self.generate_volume_path(168, 2000)
        
        return SwingScenario(
            name="dead_cat_bounce",
            category="edge_case",
            description="Bounce after crash that fails - trap",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,
            expected_trades=1,
        )
    
    def create_low_volume_scenario(self) -> SwingScenario:
        """Edge case: Low volume market - should skip."""
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.50,
            volatility=0.02,
            drift=0.0,
        )
        volumes = self.generate_volume_path(168, 150)  # Low volume
        
        return SwingScenario(
            name="low_volume",
            category="edge_case",
            description="Low volume market - should avoid",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=False,
            expected_trades=0,
        )
    
    def create_multiple_dips_scenario(self) -> SwingScenario:
        """Scenario: Multiple buyable dips in one week."""
        dips = [(20, 0.12), (50, 0.10), (80, 0.11), (120, 0.09)]
        pumps = [(30, 0.08), (62, 0.07), (95, 0.08), (140, 0.06)]
        
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.50,
            volatility=0.01,
            drift=0.0005,
            dips=dips,
            pumps=pumps
        )
        volumes = self.generate_volume_path(168, 2000)
        
        return SwingScenario(
            name="multiple_dips",
            category="normal",
            description="Multiple dip-and-recovery cycles",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,
            expected_trades=4,
        )
    
    def create_slow_grind_scenario(self) -> SwingScenario:
        """Scenario: Slow steady grind up with no clear dips."""
        prices = self.generate_price_path(
            hours=168,
            initial_price=0.45,
            volatility=0.005,
            drift=0.002,
        )
        volumes = self.generate_volume_path(168, 1000)
        
        return SwingScenario(
            name="slow_grind_up",
            category="normal",
            description="Slow steady rise with no dips",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=False,
            expected_trades=0,
        )
    
    def create_whipsaw_scenario(self) -> SwingScenario:
        """Edge case: Rapid whipsaws that stop out trades."""
        prices = [0.50]
        for i in range(168):
            # Alternating direction
            direction = 1 if i % 8 < 4 else -1
            prices.append(prices[-1] * (1 + direction * self.rng.uniform(0.02, 0.04)))
        
        prices = [max(0.05, min(0.95, p)) for p in prices]
        volumes = self.generate_volume_path(168, 2500)
        
        return SwingScenario(
            name="whipsaw",
            category="edge_case",
            description="Rapid whipsaws that trigger stops",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=np.std(np.diff(prices) / prices[:-1]),
            max_drawdown=self._calc_max_drawdown(prices),
            max_runup=self._calc_max_runup(prices),
            has_dip_opportunity=True,
            expected_trades=3,
        )
    
    def _calc_max_drawdown(self, prices: List[float]) -> float:
        """Calculate maximum drawdown."""
        peak = prices[0]
        max_dd = 0
        for p in prices:
            if p > peak:
                peak = p
            dd = (peak - p) / peak
            if dd > max_dd:
                max_dd = dd
        return max_dd
    
    def _calc_max_runup(self, prices: List[float]) -> float:
        """Calculate maximum runup from a trough."""
        trough = prices[0]
        max_ru = 0
        for p in prices:
            if p < trough:
                trough = p
            if trough > 0:
                ru = (p - trough) / trough
                if ru > max_ru:
                    max_ru = ru
        return max_ru
    
    def generate_all_scenarios(self) -> List[SwingScenario]:
        """Generate all predefined scenarios."""
        return [
            self.create_dip_recovery_scenario(),
            self.create_trending_up_scenario(),
            self.create_trending_down_scenario(),
            self.create_ranging_scenario(),
            self.create_high_volatility_scenario(),
            self.create_flash_crash_scenario(),
            self.create_dead_cat_bounce_scenario(),
            self.create_low_volume_scenario(),
            self.create_multiple_dips_scenario(),
            self.create_slow_grind_scenario(),
            self.create_whipsaw_scenario(),
        ]


class SwingBacktestEngine:
    """Backtest engine for swing trading strategy."""
    
    def __init__(self, initial_capital: float = 75.0,
                 take_profit_pct: float = 0.08,
                 stop_loss_pct: float = 0.15,
                 max_hold_hours: int = 24,
                 min_dip_pct: float = 0.08,
                 min_volume: float = 500,
                 fee_rate: float = 0.02):
        """
        Initialize backtest engine.
        
        Args:
            initial_capital: Starting capital
            take_profit_pct: Take profit threshold
            stop_loss_pct: Stop loss threshold
            max_hold_hours: Maximum hold time before exit
            min_dip_pct: Minimum dip size to trigger buy
            min_volume: Minimum volume to trade
            fee_rate: Polymarket fee rate on profits
        """
        self.initial_capital = initial_capital
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_hours = max_hold_hours
        self.min_dip_pct = min_dip_pct
        self.min_volume = min_volume
        self.fee_rate = fee_rate
    
    def _find_dips(self, prices: List[float], window: int = 24) -> List[Tuple[int, float]]:
        """Find dips in price series (local minimums with sufficient drop)."""
        dips = []
        
        for i in range(window, len(prices)):
            # Look at price window
            window_prices = prices[i-window:i]
            window_high = max(window_prices)
            current = prices[i]
            
            # Calculate dip from window high
            if window_high > 0:
                dip_pct = (window_high - current) / window_high
                if dip_pct >= self.min_dip_pct:
                    dips.append((i, dip_pct))
        
        return dips
    
    def run_backtest(self, scenario: SwingScenario) -> SwingBacktestResult:
        """
        Run backtest on a single scenario.
        
        Args:
            scenario: The market scenario to test
            
        Returns:
            SwingBacktestResult with performance metrics
        """
        capital = self.initial_capital
        position = None
        trades = []
        high_water_mark = capital
        max_drawdown = 0
        
        prices = scenario.prices
        volumes = scenario.volumes
        
        for hour in range(24, len(prices)):  # Start after 24h to have history
            current_price = prices[hour]
            current_volume = volumes[hour] if hour < len(volumes) else 500
            
            # Check exit if we have a position
            if position:
                entry_price = position['entry_price']
                entry_hour = position['entry_hour']
                hold_hours = hour - entry_hour
                
                return_pct = (current_price - entry_price) / entry_price
                
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
                # Time exit
                elif hold_hours >= self.max_hold_hours:
                    should_exit = True
                    exit_reason = "time_exit"
                
                if should_exit:
                    # Calculate PnL
                    shares = position['amount'] / entry_price
                    pnl = shares * current_price - position['amount']
                    
                    # Apply fee on profits
                    if pnl > 0:
                        pnl *= (1 - self.fee_rate)
                    
                    trades.append({
                        'entry_hour': entry_hour,
                        'exit_hour': hour,
                        'entry_price': entry_price,
                        'exit_price': current_price,
                        'amount': position['amount'],
                        'pnl': pnl,
                        'return_pct': return_pct,
                        'hold_hours': hold_hours,
                        'reason': exit_reason,
                    })
                    
                    capital += position['amount'] + pnl
                    position = None
            
            # Check entry if no position
            if position is None and current_volume >= self.min_volume:
                # Look for dip opportunity
                window_prices = prices[max(0, hour-24):hour]
                if window_prices:
                    window_high = max(window_prices)
                    if window_high > 0:
                        dip_pct = (window_high - current_price) / window_high
                        
                        if dip_pct >= self.min_dip_pct:
                            # Entry signal - buy the dip
                            amount = min(capital * 0.10, 15.0)  # 10% of capital, max $15
                            amount = max(3.0, amount)  # Min $3
                            
                            if amount <= capital:
                                position = {
                                    'entry_hour': hour,
                                    'entry_price': current_price,
                                    'amount': amount,
                                    'dip_pct': dip_pct,
                                }
                                capital -= amount
            
            # Track drawdown
            equity = capital
            if position:
                shares = position['amount'] / position['entry_price']
                equity += shares * current_price
            
            if equity > high_water_mark:
                high_water_mark = equity
            
            dd = (high_water_mark - equity) / high_water_mark
            if dd > max_drawdown:
                max_drawdown = dd
        
        # Close any remaining position at end
        if position:
            entry_price = position['entry_price']
            current_price = prices[-1]
            shares = position['amount'] / entry_price
            pnl = shares * current_price - position['amount']
            if pnl > 0:
                pnl *= (1 - self.fee_rate)
            
            trades.append({
                'entry_hour': position['entry_hour'],
                'exit_hour': len(prices) - 1,
                'entry_price': entry_price,
                'exit_price': current_price,
                'amount': position['amount'],
                'pnl': pnl,
                'return_pct': (current_price - entry_price) / entry_price,
                'hold_hours': len(prices) - 1 - position['entry_hour'],
                'reason': 'end_of_period',
            })
            capital += position['amount'] + pnl
        
        # Calculate metrics
        winning_trades = [t for t in trades if t['pnl'] > 0]
        losing_trades = [t for t in trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in trades)
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(abs(t['pnl']) for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        profit_factor = (sum(t['pnl'] for t in winning_trades) / 
                        sum(abs(t['pnl']) for t in losing_trades)) if losing_trades and sum(abs(t['pnl']) for t in losing_trades) > 0 else float('inf')
        
        avg_hold = sum(t['hold_hours'] for t in trades) / len(trades) if trades else 0
        
        return SwingBacktestResult(
            scenario_name=scenario.name,
            initial_capital=self.initial_capital,
            final_capital=capital,
            return_pct=(capital - self.initial_capital) / self.initial_capital,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(trades) if trades else 0,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            avg_hold_hours=avg_hold,
            trades=trades,
        )
    
    def run_suite(self, scenarios: List[SwingScenario]) -> Dict:
        """Run backtest on all scenarios."""
        results = []
        
        for scenario in scenarios:
            result = self.run_backtest(scenario)
            results.append(result)
        
        # Aggregate metrics
        total_return = sum(r.return_pct for r in results) / len(results)
        avg_win_rate = sum(r.win_rate for r in results) / len(results)
        avg_drawdown = sum(r.max_drawdown for r in results) / len(results)
        
        return {
            'results': results,
            'summary': {
                'scenarios': len(results),
                'mean_return': total_return,
                'avg_win_rate': avg_win_rate,
                'avg_max_drawdown': avg_drawdown,
                'profitable_scenarios': sum(1 for r in results if r.return_pct > 0),
            }
        }


def run_multi_seed_benchmark(num_seeds: int = 100, 
                            initial_capital: float = 75.0) -> Dict:
    """
    Run benchmark across multiple random seeds.
    
    Args:
        num_seeds: Number of random seeds to test
        initial_capital: Starting capital
        
    Returns:
        Aggregated benchmark results
    """
    all_results = []
    
    print(f"Running {num_seeds}-seed swing trading benchmark...")
    
    for seed in range(num_seeds):
        if (seed + 1) % 10 == 0:
            print(f"  Seed {seed + 1}/{num_seeds}...")
        
        generator = SwingScenarioGenerator(seed=seed)
        scenarios = generator.generate_all_scenarios()
        
        engine = SwingBacktestEngine(
            initial_capital=initial_capital,
            take_profit_pct=0.08,
            stop_loss_pct=0.15,
            max_hold_hours=24,
            min_dip_pct=0.08,
        )
        
        suite_result = engine.run_suite(scenarios)
        
        # Combine all trades from all scenarios
        all_scenario_pnl = sum(r.total_pnl for r in suite_result['results'])
        all_scenario_trades = sum(r.total_trades for r in suite_result['results'])
        all_scenario_wins = sum(r.winning_trades for r in suite_result['results'])
        
        all_results.append({
            'seed': seed,
            'mean_return': suite_result['summary']['mean_return'],
            'total_pnl': all_scenario_pnl,
            'total_trades': all_scenario_trades,
            'win_rate': all_scenario_wins / all_scenario_trades if all_scenario_trades > 0 else 0,
            'profitable_scenarios': suite_result['summary']['profitable_scenarios'],
        })
    
    # Calculate statistics
    returns = [r['mean_return'] for r in all_results]
    win_rates = [r['win_rate'] for r in all_results]
    
    return {
        'num_seeds': num_seeds,
        'mean_return': np.mean(returns),
        'median_return': np.median(returns),
        'std_return': np.std(returns),
        'min_return': np.min(returns),
        'max_return': np.max(returns),
        'mean_win_rate': np.mean(win_rates),
        'seeds_above_0': sum(1 for r in returns if r > 0),
        'seeds_above_5pct': sum(1 for r in returns if r > 0.05),
        'seeds_above_10pct': sum(1 for r in returns if r > 0.10),
        'all_results': all_results,
    }


def run_monte_carlo_simulation(num_simulations: int = 1000,
                               initial_capital: float = 75.0,
                               hours_per_sim: int = 168) -> Dict:
    """
    Run Monte Carlo simulation of swing trading.
    
    Args:
        num_simulations: Number of simulations
        initial_capital: Starting capital
        hours_per_sim: Hours per simulation (168 = 1 week)
        
    Returns:
        Simulation results
    """
    results = []
    
    print(f"Running {num_simulations} Monte Carlo simulations...")
    
    for sim in range(num_simulations):
        if (sim + 1) % 100 == 0:
            print(f"  Simulation {sim + 1}/{num_simulations}...")
        
        # Generate random scenario
        seed = sim * 7919  # Prime multiplier for variety
        generator = SwingScenarioGenerator(seed=seed)
        
        # Random market parameters
        rng = np.random.RandomState(seed)
        volatility = rng.uniform(0.01, 0.03)
        drift = rng.uniform(-0.002, 0.003)
        
        # Add random dips and pumps
        num_events = rng.randint(2, 6)
        dips = []
        pumps = []
        for _ in range(num_events):
            hour = rng.randint(12, hours_per_sim - 12)
            if rng.random() > 0.5:
                dips.append((hour, rng.uniform(0.08, 0.25)))
            else:
                pumps.append((hour, rng.uniform(0.05, 0.15)))
        
        prices = generator.generate_price_path(
            hours=hours_per_sim,
            initial_price=rng.uniform(0.30, 0.70),
            volatility=volatility,
            drift=drift,
            dips=dips,
            pumps=pumps,
        )
        volumes = generator.generate_volume_path(hours_per_sim, rng.uniform(500, 3000))
        
        scenario = SwingScenario(
            name=f"sim_{sim}",
            category="simulation",
            description="Monte Carlo simulation",
            prices=prices,
            volumes=volumes,
            initial_price=prices[0],
            final_price=prices[-1],
            volatility=volatility,
            max_drawdown=generator._calc_max_drawdown(prices),
            max_runup=generator._calc_max_runup(prices),
            has_dip_opportunity=len(dips) > 0,
            expected_trades=len(dips),
        )
        
        # Run backtest
        engine = SwingBacktestEngine(
            initial_capital=initial_capital,
            take_profit_pct=0.08,
            stop_loss_pct=0.15,
            max_hold_hours=24,
            min_dip_pct=0.08,
        )
        
        result = engine.run_backtest(scenario)
        results.append({
            'simulation': sim,
            'return_pct': result.return_pct,
            'final_capital': result.final_capital,
            'total_trades': result.total_trades,
            'win_rate': result.win_rate,
            'max_drawdown': result.max_drawdown,
            'total_pnl': result.total_pnl,
        })
    
    # Calculate statistics
    returns = [r['return_pct'] for r in results]
    
    return {
        'num_simulations': num_simulations,
        'mean_return': np.mean(returns),
        'median_return': np.median(returns),
        'std_return': np.std(returns),
        'min_return': np.min(returns),
        'max_return': np.max(returns),
        'pct_5': np.percentile(returns, 5),
        'pct_95': np.percentile(returns, 95),
        'positive_weeks': sum(1 for r in returns if r > 0) / len(returns),
        'weeks_above_5pct': sum(1 for r in returns if r > 0.05) / len(returns),
        'weeks_above_10pct': sum(1 for r in returns if r > 0.10) / len(returns),
        'negative_weeks': sum(1 for r in returns if r < 0) / len(returns),
        'mean_trades_per_week': np.mean([r['total_trades'] for r in results]),
        'mean_win_rate': np.mean([r['win_rate'] for r in results if r['total_trades'] > 0]),
        'mean_max_drawdown': np.mean([r['max_drawdown'] for r in results]),
        'all_results': results,
    }


if __name__ == "__main__":
    # Quick test
    print("Testing swing benchmark...")
    
    generator = SwingScenarioGenerator(seed=42)
    scenarios = generator.generate_all_scenarios()
    print(f"Generated {len(scenarios)} scenarios")
    
    engine = SwingBacktestEngine(initial_capital=75.0)
    suite_result = engine.run_suite(scenarios)
    
    print(f"\nSuite Results:")
    print(f"  Mean Return: {suite_result['summary']['mean_return']:.1%}")
    print(f"  Avg Win Rate: {suite_result['summary']['avg_win_rate']:.1%}")
    print(f"  Profitable Scenarios: {suite_result['summary']['profitable_scenarios']}/{len(scenarios)}")
