"""
Benchmark Runner - Full HFT Benchmark Suite Testing
====================================================
Runs the 50-scenario benchmark suite with microstructure-aware backtest
and walk-forward validation to ensure robust strategy performance.

Usage:
    python run_benchmarks.py                 # Run with default settings
    python run_benchmarks.py --verbose       # Detailed output
    python run_benchmarks.py --optimize      # Run parameter optimization
"""
import sys
import json
import random
import argparse
from datetime import datetime
from typing import Dict, List, Optional
import statistics

# Add src to path
sys.path.insert(0, 'src')

from backtesting.benchmark_suite import create_benchmark_suite, BenchmarkSuite, ScenarioType
from backtesting.microstructure_backtest import (
    MicrostructureBacktestEngine,
    WalkForwardValidator,
    TradingCosts
)
from strategies.robust_strategy import (
    RobustStrategy,
    RobustStrategyConfig,
    create_robust_strategy,
    get_strategy_signal_fn,
    PARAMETER_GRID
)
from strategies.momentum_strategy import (
    MomentumStrategy,
    MomentumConfig,
    create_momentum_strategy,
    get_momentum_signal_fn
)


def run_full_benchmark(
    strategy: RobustStrategy,
    initial_capital: float = 75.0,
    seed: int = 42,
    verbose: bool = False
) -> Dict:
    """
    Run full benchmark suite with given strategy.
    
    Returns comprehensive performance report.
    """
    print("\n" + "=" * 70)
    print("POLYMARKET BOT - HFT BENCHMARK SUITE")
    print("=" * 70)
    print(f"Initial Capital: ${initial_capital}")
    print(f"Seed: {seed}")
    print(f"Strategy: {strategy.config.min_raw_edge:.0%} min raw edge, "
          f"{strategy.config.min_net_edge:.0%} min net edge")
    
    # Create suite
    suite = create_benchmark_suite(seed=seed)
    print(f"\nLoaded {suite.scenario_count} scenarios")
    print(f"  Normal: {len(suite.normal_scenarios)}")
    print(f"  Edge Cases: {len(suite.edge_case_scenarios)}")
    
    # Create engine
    engine = MicrostructureBacktestEngine(initial_capital=initial_capital)
    
    # Get signal function
    signal_fn = get_strategy_signal_fn(strategy)
    
    # Run full suite
    print("\n" + "-" * 70)
    print("RUNNING BENCHMARK SUITE...")
    print("-" * 70)
    
    results = engine.run_suite(suite, signal_fn, verbose=verbose)
    
    # Print summary
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    
    summary = results["summary"]
    print(f"\nOVERALL PERFORMANCE:")
    print(f"  Scenarios: {summary['total_scenarios']}")
    print(f"  Total Net P&L: ${summary['total_net_pnl']}")
    print(f"  Average Return per Scenario: {summary['avg_net_return']}")
    print(f"  Total Trades: {summary['total_trades']}")
    print(f"  Overall Win Rate: {summary['overall_win_rate']}")
    print(f"  Profitable Scenarios: {summary['profitable_scenarios']}/{summary['total_scenarios']}")
    
    print(f"\nCOST BREAKDOWN:")
    print(f"  Total Fees: ${summary['total_fees']}")
    print(f"  Total Slippage: ${summary['total_slippage']}")
    
    normal = results["normal_scenarios"]
    edge = results["edge_case_scenarios"]
    
    print(f"\nNORMAL SCENARIOS ({normal['count']}):")
    print(f"  Average Return: {normal['avg_return']}")
    print(f"  Profitable: {normal['profitable']}/{normal['count']}")
    
    print(f"\nEDGE CASE SCENARIOS ({edge['count']}):")
    print(f"  Average Return: {edge['avg_return']}")
    print(f"  Profitable: {edge['profitable']}/{edge['count']}")
    
    # Calculate weekly return estimate
    # Average 1 week per scenario, so total weekly return = avg return
    avg_return_str = summary['avg_net_return']
    try:
        avg_return_pct = float(avg_return_str.replace('%', '')) / 100
    except:
        avg_return_pct = 0
    
    weekly_estimate = avg_return_pct * 100  # Already per scenario which is ~1 week
    
    print(f"\n" + "=" * 70)
    print(f"ESTIMATED WEEKLY RETURN: {weekly_estimate:.1f}%")
    if weekly_estimate >= 10:
        print("TARGET ACHIEVED: 10%+ weekly returns")
    elif weekly_estimate >= 5:
        print("PARTIAL SUCCESS: 5-10% weekly returns")
    else:
        print("NEEDS IMPROVEMENT: Below 5% weekly returns")
    print("=" * 70)
    
    return results


def run_walk_forward_validation(
    strategy: RobustStrategy,
    initial_capital: float = 75.0,
    seed: int = 42,
    num_folds: int = 5
) -> Dict:
    """
    Run walk-forward validation to check for overfitting.
    """
    print("\n" + "=" * 70)
    print("WALK-FORWARD VALIDATION")
    print("=" * 70)
    print(f"Folds: {num_folds}")
    
    # Create suite and engine
    random.seed(seed)
    suite = create_benchmark_suite(seed=seed)
    engine = MicrostructureBacktestEngine(initial_capital=initial_capital)
    
    # Create validator
    validator = WalkForwardValidator(engine)
    
    # Get signal function
    signal_fn = get_strategy_signal_fn(strategy)
    
    # Run validation
    wf_results = validator.validate(suite, signal_fn, num_folds=num_folds)
    
    print(f"\nVALIDATION RESULTS:")
    print(f"  Average Return per Scenario: {wf_results['avg_return_per_scenario']}")
    print(f"  Return Std Dev: {wf_results['return_std']}")
    print(f"  Estimated Sharpe: {wf_results['sharpe_estimate']:.2f}")
    print(f"  Is Robust: {wf_results['is_robust']}")
    
    print(f"\nFOLD BREAKDOWN:")
    for fold in wf_results["fold_results"]:
        print(f"  Fold {fold['fold']}: "
              f"P&L ${fold['net_pnl']:.2f}, "
              f"Return {fold['avg_return']:.1%}, "
              f"WR {fold['win_rate']:.0%}")
    
    return wf_results


def run_parameter_optimization(
    initial_capital: float = 75.0,
    seed: int = 42,
    max_combinations: int = 50
) -> Dict:
    """
    Run grid search to find optimal parameters.
    """
    print("\n" + "=" * 70)
    print("PARAMETER OPTIMIZATION")
    print("=" * 70)
    
    # Generate combinations
    from itertools import product
    
    params_to_test = {
        "min_raw_edge": [0.12, 0.15, 0.18],
        "min_net_edge": [0.06, 0.08, 0.10],
        "min_confidence": [0.55, 0.60, 0.65],
        "max_position_pct": [0.08, 0.12],
    }
    
    keys = list(params_to_test.keys())
    values = list(params_to_test.values())
    
    combinations = [dict(zip(keys, combo)) for combo in product(*values)]
    
    # Limit combinations
    if len(combinations) > max_combinations:
        random.seed(seed)
        combinations = random.sample(combinations, max_combinations)
    
    print(f"Testing {len(combinations)} parameter combinations...")
    
    # Create suite
    suite = create_benchmark_suite(seed=seed)
    
    best_result = None
    best_params = None
    best_score = -float('inf')
    
    results = []
    
    for i, params in enumerate(combinations):
        # Create strategy with these params
        config = RobustStrategyConfig(
            min_raw_edge=params["min_raw_edge"],
            min_net_edge=params["min_net_edge"],
            min_confidence=params["min_confidence"],
            max_position_pct=params["max_position_pct"],
        )
        strategy = RobustStrategy(config)
        
        # Create engine
        engine = MicrostructureBacktestEngine(initial_capital=initial_capital)
        signal_fn = get_strategy_signal_fn(strategy)
        
        # Run suite (quietly)
        suite_results = engine.run_suite(suite, signal_fn, verbose=False)
        
        # Extract metrics
        summary = suite_results["summary"]
        try:
            avg_return = float(summary['avg_net_return'].replace('%', '')) / 100
        except:
            avg_return = 0
        
        profitable_ratio = summary['profitable_scenarios'] / summary['total_scenarios']
        win_rate_str = summary['overall_win_rate'].replace('%', '')
        try:
            win_rate = float(win_rate_str) / 100
        except:
            win_rate = 0
        
        # Score: weighted combination of return, profitability, and win rate
        score = avg_return * 0.5 + profitable_ratio * 0.3 + win_rate * 0.2
        
        results.append({
            "params": params,
            "avg_return": avg_return,
            "profitable_ratio": profitable_ratio,
            "win_rate": win_rate,
            "score": score,
        })
        
        if score > best_score:
            best_score = score
            best_params = params
            best_result = suite_results
        
        # Progress
        if (i + 1) % 10 == 0:
            print(f"  Tested {i + 1}/{len(combinations)} combinations...")
    
    # Sort results
    results.sort(key=lambda x: x["score"], reverse=True)
    
    print(f"\n" + "-" * 70)
    print("TOP 5 PARAMETER COMBINATIONS:")
    print("-" * 70)
    
    for i, r in enumerate(results[:5], 1):
        print(f"\n{i}. Score: {r['score']:.4f}")
        print(f"   Return: {r['avg_return']:.1%}, Profitable: {r['profitable_ratio']:.0%}, WR: {r['win_rate']:.0%}")
        print(f"   Params: {r['params']}")
    
    print(f"\n" + "=" * 70)
    print("BEST PARAMETERS:")
    print("=" * 70)
    for key, value in best_params.items():
        print(f"  {key}: {value}")
    
    return {
        "best_params": best_params,
        "best_score": best_score,
        "all_results": results,
    }


def generate_report(
    benchmark_results: Dict,
    validation_results: Optional[Dict] = None,
    optimization_results: Optional[Dict] = None
) -> str:
    """
    Generate a markdown report of all results.
    """
    report = []
    report.append("# Polymarket Bot - Benchmark Report")
    report.append(f"\nGenerated: {datetime.now().isoformat()}")
    
    report.append("\n## Summary")
    summary = benchmark_results["summary"]
    report.append(f"- **Total Scenarios**: {summary['total_scenarios']}")
    report.append(f"- **Total Net P&L**: ${summary['total_net_pnl']}")
    report.append(f"- **Average Return**: {summary['avg_net_return']}")
    report.append(f"- **Total Trades**: {summary['total_trades']}")
    report.append(f"- **Win Rate**: {summary['overall_win_rate']}")
    report.append(f"- **Profitable Scenarios**: {summary['profitable_scenarios']}")
    
    report.append("\n## Cost Analysis")
    report.append(f"- **Total Fees**: ${summary['total_fees']}")
    report.append(f"- **Total Slippage**: ${summary['total_slippage']}")
    
    report.append("\n## Scenario Breakdown")
    report.append("\n### Normal Scenarios")
    normal = benchmark_results["normal_scenarios"]
    report.append(f"- Count: {normal['count']}")
    report.append(f"- Average Return: {normal['avg_return']}")
    report.append(f"- Profitable: {normal['profitable']}")
    
    report.append("\n### Edge Case Scenarios")
    edge = benchmark_results["edge_case_scenarios"]
    report.append(f"- Count: {edge['count']}")
    report.append(f"- Average Return: {edge['avg_return']}")
    report.append(f"- Profitable: {edge['profitable']}")
    
    if validation_results:
        report.append("\n## Walk-Forward Validation")
        report.append(f"- **Average Return**: {validation_results['avg_return_per_scenario']}")
        report.append(f"- **Std Dev**: {validation_results['return_std']}")
        report.append(f"- **Is Robust**: {validation_results['is_robust']}")
    
    if optimization_results:
        report.append("\n## Optimization Results")
        report.append(f"- **Best Score**: {optimization_results['best_score']:.4f}")
        report.append("\n### Best Parameters")
        for key, value in optimization_results['best_params'].items():
            report.append(f"- {key}: {value}")
    
    return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Run Polymarket Bot Benchmarks")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--optimize", "-o", action="store_true", help="Run parameter optimization")
    parser.add_argument("--validate", action="store_true", help="Run walk-forward validation")
    parser.add_argument("--capital", type=float, default=75.0, help="Initial capital")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--risk", choices=["conservative", "moderate", "aggressive"], 
                       default="moderate", help="Risk level")
    parser.add_argument("--report", action="store_true", help="Generate markdown report")
    
    args = parser.parse_args()
    
    # Create strategy
    strategy = create_robust_strategy(capital=args.capital, risk_level=args.risk)
    
    print(f"\nStrategy Configuration ({args.risk}):")
    print(f"  Min raw edge: {strategy.config.min_raw_edge:.0%}")
    print(f"  Min net edge: {strategy.config.min_net_edge:.0%}")
    print(f"  Min confidence: {strategy.config.min_confidence:.0%}")
    print(f"  Max spread: {strategy.config.max_spread:.0%}")
    print(f"  Max position: {strategy.config.max_position_pct:.0%}")
    
    # Run benchmark
    benchmark_results = run_full_benchmark(
        strategy, 
        initial_capital=args.capital,
        seed=args.seed,
        verbose=args.verbose
    )
    
    validation_results = None
    optimization_results = None
    
    # Run validation if requested
    if args.validate:
        validation_results = run_walk_forward_validation(
            strategy,
            initial_capital=args.capital,
            seed=args.seed,
            num_folds=5
        )
    
    # Run optimization if requested
    if args.optimize:
        optimization_results = run_parameter_optimization(
            initial_capital=args.capital,
            seed=args.seed,
            max_combinations=50
        )
    
    # Generate report if requested
    if args.report:
        report = generate_report(
            benchmark_results,
            validation_results,
            optimization_results
        )
        
        report_path = "benchmark_report.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport saved to: {report_path}")
    
    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
