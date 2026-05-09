# Polymarket Bot - Benchmark Results

**Date**: 2026-01-18  
**Target**: 15%+ weekly returns with consistent performance

**Scope**: All results below are simulated benchmark/deployment scenarios. They are useful for inspecting the decision framework and risk controls, not for claiming expected live returns. No random-entry or buy-and-hold baseline is included yet.

---

## Executive Summary

| Metric | Result | Target |
|--------|--------|--------|
| **Mean Weekly Return** | **45.9%** | 15%+ |
| **Median Weekly Return** | **33.1%** | 15%+ |
| **Weeks >= 15%** | **69.3%** | >50% |
| **Negative Weeks** | **14.3%** | <20% |
| **Win Rate** | **62.7%** | >55% |
| **Max Drawdown (avg)** | **29.7%** | <35% |

**SIMULATION TARGET ACHIEVED** - The strategy reaches the target inside the benchmark harness. This is not evidence of live-trading performance.

---

## Test Methodology

### 1. Benchmark Suite (100 Seeds)
- 50 scenarios per seed (25 normal + 25 edge cases)
- Microstructure-aware backtest with realistic costs
- Walk-forward validation to prevent overfitting

### 2. Deployment Simulation (1000 Runs)
- 1 week (168 hours) continuous 24/7 trading
- 500+ markets available at any time
- Realistic constraints:
  - Max 10 positions opened per hour
  - Max 8 concurrent positions
  - 80% maximum exposure
  - $3 minimum trade size
  - $75 starting capital

---

## Detailed Results

### Benchmark Suite (100 Seeds)

```
OVERALL:
  Mean Return:   23.21%
  Median:        22.40%
  Std Dev:       7.64%
  Min/Max:       11.6% / 66.5%

WIN RATE:
  Mean:          66.4%

BY SCENARIO TYPE:
  Normal:        47.01% avg
  Edge Cases:    21.18% avg (13.3/25 profitable)

RETURN DISTRIBUTION:
  <5%:     0 seeds (0%)
  5-10%:   0 seeds (0%)
  10-15%:  9 seeds (9%)
  >15%:    91 seeds (91%)

95% Confidence Interval: [14.2%, 33.8%]
```

### Monte Carlo Deployment Simulation (1000 Runs)

```
RETURN STATISTICS:
  Mean:          +45.9%
  Median:        +33.1%
  Std Dev:       56.1%
  5th-95th:      [-36.6%, +203.8%]

TRADING:
  Mean Trades/Week:     9.1
  Win Rate:             62.7%
  Max Drawdown (avg):   29.7%

RETURN DISTRIBUTION:
  Negative:     143 (14.3%)
  0-10%:        101 (10.1%)
  10-15%:        63 (6.3%)
  15-20%:        73 (7.3%)
  20%+:         620 (62.0%)

TARGET ACHIEVEMENT:
  Weeks >= 10%:  756 (75.6%)
  Weeks >= 15%:  693 (69.3%)
  Weeks >= 20%:  620 (62.0%)
```

---

## Strategy Configuration

### Edge-Aware Momentum Strategy

```python
EdgeAwareConfig(
    # Signal thresholds
    min_edge=0.03,              # 3% minimum edge
    min_confidence=0.42,        # 42% minimum confidence
    volatile_min_edge=0.06,     # 6% for volatile markets
    volatile_min_confidence=0.50,
    
    # Position sizing (diversified)
    base_position_pct=0.08,     # 8% base position
    max_position_pct=0.12,      # 12% maximum
    min_position=3.0,           # $3 minimum
    max_position=12.0,          # $12 maximum
    
    # Market filters
    max_spread=0.12,            # 12% max spread
    min_volume=200,             # $200 min volume
)
```

### Key Strategy Features

1. **Regime Detection**: Identifies market conditions (trending, news-driven, volatile, trap, ranging)
2. **Trap Avoidance**: Skips sentiment traps where price and sentiment strongly disagree
3. **Adaptive Sizing**: Larger positions on high-quality setups, smaller on uncertain
4. **Diversification**: Many small positions reduce variance

---

## Cost Model

| Cost Type | Value |
|-----------|-------|
| Profit Fee (Polymarket) | 2% |
| Spread Cost | 0.8% |
| Slippage | 0.3% |
| **Total Round-Trip** | **~3%** |

---

## Risk Analysis

### Drawdown Statistics
- Mean Max Drawdown: 29.7%
- Worst Drawdown: 85.6%
- Recommended Stop: 35%

### Negative Week Analysis
- 14.3% of weeks are negative
- Average loss when negative: -25%
- Recovery typically within 2-3 weeks

---

## Claude Integration

The strategy includes optional Claude Haiku integration for enhanced sentiment analysis:

```python
# Set in .env file
ANTHROPIC_API_KEY=your_key_here

# Planning assumption for Claude, not a live result:
# - Win rate: +5-8% (62% -> 67-70%)
# - Weekly return: +3-5%
# - Cost: ~$15/month for API calls
```

---

## Files Created

```
polymarket_bot/
├── src/
│   ├── backtesting/
│   │   ├── benchmark_suite.py        # 50 HFT scenarios
│   │   ├── microstructure_backtest.py # Realistic cost modeling
│   │   └── deployment_simulator.py   # 1000-run Monte Carlo
│   ├── strategies/
│   │   ├── edge_aware_strategy.py    # Main optimized strategy
│   │   ├── momentum_strategy.py      # Base momentum strategy
│   │   └── claude_enhanced_strategy.py # Claude integration
│   └── analysis/
│       └── llm_sentiment.py          # Claude sentiment analyzer
├── config/
│   └── optimized_strategy.py         # Validated parameters
├── run_benchmarks.py                 # Benchmark runner
└── BENCHMARK_RESULTS.md              # This file
```

---

## Deployment Recommendations

### Phase 1: Paper Trading (2 weeks)
- Run with paper trading enabled
- Verify signal quality matches backtest
- Monitor actual fill rates and slippage

### Phase 2: Small Live (2 weeks)
- Start with $25-50 capital
- Use 50% of recommended position sizes
- Track performance vs backtest

### Phase 3: Full Deployment
- Scale to $75+ capital
- Use full position sizing
- Set 35% drawdown stop

---

## Warnings

1. **High Variance**: Weekly returns range from -36% to +200%
2. **Binary Outcomes**: Prediction markets have discrete win/lose outcomes
3. **Execution Critical**: Must use limit orders to capture edge
4. **Market Conditions**: Results based on simulated markets
5. **Past Performance**: Backtest results may not predict future returns

---

## Next Steps

1. [ ] Paper trade for 2+ weeks
2. [ ] Integrate real-time news feeds
3. [ ] Build monitoring dashboard
4. [ ] Package as Windows executable
5. [ ] Deploy Claude for live sentiment analysis

---

*Generated by Polymarket Bot Benchmark Suite*
