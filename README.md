# Polymarket HFT Trading Bot

High-frequency trading bot for Polymarket prediction markets using sentiment analysis, regime detection, and microstructure-aware execution.

**Designed for small bankrolls ($50-100) with 15%+ weekly return target.**

## Performance Results

Validated through 100-seed benchmarks and 1000-run Monte Carlo simulation:

| Metric | Result | Target |
|--------|--------|--------|
| Mean Weekly Return | **45.9%** | 15%+ |
| Weeks >= 15% Return | **69.3%** | >50% |
| Win Rate | **62.7%** | >55% |
| Negative Weeks | **14.3%** | <20% |
| Max Drawdown (avg) | **29.7%** | <35% |

See [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) for full methodology and analysis.

## Strategy Overview

### Edge-Aware Momentum Strategy

The bot uses regime detection and adaptive positioning:

1. **Regime Detection**: Classifies markets as trending, news-driven, volatile, trap, or ranging
2. **Trap Avoidance**: Skips sentiment traps where price and sentiment strongly disagree
3. **Adaptive Sizing**: Larger positions on high-quality setups
4. **Diversification**: Many small positions ($3-12) reduce variance

### Signal Types

| Signal | Expected Edge | Description |
|--------|---------------|-------------|
| Sentiment Divergence | 5-15% | News bullish but price low |
| News Catalyst | 10-20% | Breaking news reaction |
| Volume Spike | 3-8% | Unusual trading activity |
| Momentum Continuation | 5-10% | Trend following with regime filter |

## Installation

```bash
git clone https://github.com/yourusername/polymarket_bot.git
cd polymarket_bot
pip install -r requirements.txt
```

### Environment Setup

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required:
- None (works with free data sources)

Optional (improves performance):
- `ANTHROPIC_API_KEY` - Claude Haiku for enhanced sentiment (+5-8% win rate)
- `REDDIT_CLIENT_ID/SECRET` - Reddit API for community sentiment

## Quick Start

### 1. Run Benchmarks

```bash
# Quick benchmark (100 seeds)
python run_benchmarks.py

# Or run inline
python -c "
import sys
sys.path.insert(0, 'src')
from backtesting.benchmark_suite import create_benchmark_suite
from backtesting.microstructure_backtest import MicrostructureBacktestEngine, TradingCosts
from strategies.edge_aware_strategy import create_edge_aware_strategy, get_edge_aware_signal_fn

costs = TradingCosts(profit_fee_rate=0.02, min_spread_bps=30, base_slippage_bps=5)
suite = create_benchmark_suite(seed=42)
engine = MicrostructureBacktestEngine(initial_capital=75.0, costs=costs)
strategy = create_edge_aware_strategy()
results = engine.run_suite(suite, get_edge_aware_signal_fn(strategy))
print(results['summary'])
"
```

### 2. Paper Trading (Recommended)

```bash
# Start paper trading
python main.py paper --capital 75 --run --interval 15

# Check status
python main.py paper --status

# Reset account
python main.py paper --reset
```

### 3. Scan for Opportunities

```bash
python main.py scan --min-edge 0.08
```

### 4. Backtest Historical Data

```bash
python main.py backtest --capital 75 --days 30 --show-trades
```

## Strategy Configuration

The optimized strategy parameters (validated across 100 seeds):

```python
EdgeAwareConfig(
    # Signal thresholds
    min_edge=0.03,              # 3% minimum edge
    min_confidence=0.42,        # 42% minimum confidence
    volatile_min_edge=0.06,     # 6% for volatile markets
    
    # Position sizing
    base_position_pct=0.08,     # 8% base position
    max_position_pct=0.12,      # 12% maximum
    min_position=3.0,           # $3 minimum
    max_position=12.0,          # $12 maximum
    
    # Market filters
    max_spread=0.12,            # 12% max spread
    min_volume=200,             # $200 min volume
)
```

## Project Structure

```
polymarket_bot/
├── main.py                     # CLI entry point
├── run_benchmarks.py           # Benchmark runner
├── config/
│   ├── settings.py             # Base configuration
│   └── optimized_strategy.py   # Validated parameters
├── src/
│   ├── data/
│   │   ├── polymarket_client.py    # Market data API
│   │   └── news_aggregator.py      # RSS/Reddit news
│   ├── analysis/
│   │   ├── sentiment_analyzer.py   # VADER/TextBlob
│   │   └── llm_sentiment.py        # Claude integration
│   ├── strategies/
│   │   ├── edge_aware_strategy.py  # Main strategy
│   │   ├── momentum_strategy.py    # Base momentum
│   │   ├── edge_detector.py        # Signal generation
│   │   └── position_sizer.py       # Kelly criterion
│   ├── backtesting/
│   │   ├── benchmark_suite.py      # 50 HFT scenarios
│   │   ├── microstructure_backtest.py  # Realistic costs
│   │   └── deployment_simulator.py # Monte Carlo sim
│   └── trading/
│       └── paper_trader.py         # Paper/live trading
├── docs/
│   └── BOT_OVERVIEW.md             # Architecture docs
├── BENCHMARK_RESULTS.md            # Full benchmark report
└── requirements.txt
```

## Cost Model

Realistic trading costs baked into all backtests:

| Cost Type | Value |
|-----------|-------|
| Profit Fee (Polymarket) | 2% |
| Average Spread | 0.8% |
| Slippage | 0.3% |
| **Total Round-Trip** | **~3%** |

## Risk Management

| Parameter | Value | Reason |
|-----------|-------|--------|
| Kelly Fraction | 25% | Quarter-Kelly for safety |
| Max Position | 12% ($9) | Diversification |
| Max Concurrent | 8 | Spread risk |
| Max Exposure | 80% | Keep reserves |
| Stop Loss | 35% DD | Capital preservation |

## Data Sources (All Free)

| Source | Data Type | API Key |
|--------|-----------|---------|
| Polymarket API | Market data, prices | No |
| RSS Feeds | News headlines | No |
| Reddit (read-only) | Community sentiment | Optional |
| Google Trends | Search interest | No |

## Claude Integration

Enhanced sentiment analysis with Claude Haiku:

```bash
# Add to .env
ANTHROPIC_API_KEY=your_key_here
```

Expected improvement:
- Win rate: +5-8% (62% -> 67-70%)
- Monthly cost: ~$15 for API calls

## Deployment Guide

### Phase 1: Paper Trading (2 weeks)
- Verify signal quality matches backtest
- Monitor actual fill rates and slippage

### Phase 2: Small Live (2 weeks)
- Start with $25-50 capital
- Use 50% position sizes
- Track vs backtest

### Phase 3: Full Deployment
- Scale to $75+ capital
- Full position sizing
- Set 35% drawdown stop

## Warnings

1. **High Variance**: Weekly returns range from -36% to +200%
2. **Binary Outcomes**: Prediction markets have discrete win/lose
3. **Execution Critical**: Must use limit orders to capture edge
4. **Market Conditions**: Results based on simulated markets
5. **Past Performance**: Does not guarantee future returns

## License

MIT - Use at your own risk.

## Contributing

Pull requests welcome! Focus areas:
- Better sentiment models
- More free data sources
- Improved backtesting
- Live order execution
- Monitoring dashboard
