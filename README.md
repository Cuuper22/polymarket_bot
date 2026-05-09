# polymarket_bot

Quantitative trading bot for prediction markets. Regime detection, Kelly criterion sizing, Monte Carlo validation.

> **All results are from simulated market scenarios.** The value is the decision framework, regime detection, position sizing, and validation methodology, not the returns. See [methodology](#validation).
> **Status:** Research and paper-trading project. No live-money performance history; not financial advice.

![Python](https://img.shields.io/badge/python-3.x-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## Why

I wanted to understand how to make decisions when you can't be sure you're right. Not in the abstract - I wanted a domain where being wrong costs you something immediately.

Prediction markets are a clean sandbox for this. Binary outcomes, real-time prices, and the market is full of other people trying to exploit the same signals you are. If your model is miscalibrated, you find out fast.

The core of the system is regime detection - classifying market states as trending, news-driven, volatile, or trap before deciding whether to trade. The "trap" classification is the most important one: when price movement and sentiment contradict each other, the correct action is to do nothing. Knowing when NOT to act turns out to be the hardest part of any autonomous decision system.

Position sizing uses the Kelly criterion - the mathematically optimal bet size given your estimated edge and the odds. Kelly tells you to bet more when you're confident and less when you're not, which sounds obvious until you realize most trading systems use fixed position sizes regardless of conviction. The Kelly fraction is capped (quarter-Kelly by default) because the optimal strategy is only optimal if your edge estimate is correct, and it never is.

Validation is where most trading projects fall apart. It's easy to backtest against historical data and find a strategy that would have worked. It's harder to test against scenarios that haven't happened yet. The benchmark suite runs 50 scenarios (25 normal market conditions + 25 edge cases), and the Monte Carlo simulator runs 1,000 independent deployment simulations with realistic cost modeling - 2% profit fees, 0.8% spread, 0.3% slippage.

All data sources are free. The bot does not need live money to run, only curiosity about how decisions work.

## Architecture

### Signal Pipeline

```
Data Sources                          Analysis
─────────────                         ────────
Polymarket API  → Price data    ─┐
RSS feeds       → News events   ─┤
Reddit (opt.)   → Social signal ─┼──→ Regime Classifier ──→ Position Sizer ──→ Paper Trader
Claude (opt.)   → Strategic     ─┤         │                  (Kelly + caps)
Grok (opt.)     → Sentiment     ─┘         │
                                    ┌──────┴──────┐
                                    │             │
                               [trending]    [TRAP → skip]
                               [news_driven] [volatile → reduce]
                               [mild_trend]  [ranging → skip]
```

The regime classifier is the decision gate. Six states: **trending**, **news_driven**, **mild_trend**, **volatile**, **ranging**, and **trap**. Trap and ranging produce no trades. Volatile reduces position size. The rest trade with confidence-scaled sizing.

Claude (claude_enhanced_strategy.py, 14K) and Grok (grok_analyzer.py, 8K) are optional - they improve sentiment analysis but the bot runs without them. Base sentiment uses VADER + TextBlob.

### Regime Detection

The trap detector is the intellectual centerpiece. When price and sentiment strongly contradict (e.g., sentiment is bearish but price is already very low), the system classifies the market as a trap and does nothing. This sounds simple, but most trading systems don't have a "do nothing" output - they always trade, just with different sizes.

Same principle I'm applying in [jobhunter](https://github.com/Cuuper22/jobhunter): knowing when an autonomous system should NOT act is harder than knowing when it should.

### Position Sizing (Kelly Criterion)

```
f* = (bp - q) / b

b = payout ratio = (1 - price) / price
p = estimated win probability
q = 1 - p
```

Raw Kelly is scaled down (quarter-Kelly default) and capped by maximum position percentage. The `SmallBankrollOptimizer` adjusts parameters based on capital level - tighter limits for smaller accounts.

Multiple validated configurations exist in `config/`: the optimized strategy targets 8-10% weekly with 45-55% position sizing (aggressive), while the benchmark config uses $3-12 positions at 8-12% of capital (conservative).

## Simulation Results

Validated through 100-seed benchmarks and 1,000-run Monte Carlo simulation:

**Benchmark Suite (100 seeds, 50 scenarios each):**

| Metric | Result |
|--------|--------|
| Mean Weekly Return | 23.2% |
| Win Rate | 66.4% |
| 95% Confidence Interval | [14.2%, 33.8%] |

**Monte Carlo Deployment Simulation (1,000 runs):**

| Metric | Result |
|--------|--------|
| Mean Weekly Return | 45.9% |
| Median Weekly Return | 33.1% |
| Std Dev | 56.1% |
| Win Rate | 62.7% |
| Negative Weeks | 14.3% |
| Max Drawdown (avg) | 29.7% |
| Range (5th-95th percentile) | -36.6% to +203.8% |

> **Context:** A 45.9% mean weekly return is not realistic for live trading. The Monte Carlo simulation tests decision logic against synthetic market scenarios with realistic cost modeling. The high variance (std dev 56.1%, range spans -37% to +204%) reflects the nature of the simulation, not expected live performance. The benchmark suite's 23.2% mean with a 95% CI of [14.2%, 33.8%] is the more stable measure - and it's still simulated. No baseline comparison (random entry, buy-and-hold) is included yet, which means these numbers lack context. See [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) for full methodology.

<!-- equity curve visualization to be added -->

## Cost Model

Realistic trading costs baked into all simulations:

| Cost Type | Value |
|-----------|-------|
| Profit Fee (Polymarket) | 2% |
| Average Spread | 0.8% |
| Slippage | 0.3% |
| **Total Round-Trip** | **~3%** |

## Data Sources (All Free)

| Source | Data Type | API Key |
|--------|-----------|---------|
| Polymarket API | Market data, prices | No |
| RSS Feeds | News headlines | No |
| Reddit (read-only) | Community sentiment | Optional |
| Google Trends | Search interest | No |
| Claude API | Enhanced sentiment | Optional (~$15/mo) |
| Grok API | Real-time sentiment | Optional |

## Installation

```bash
git clone https://github.com/Cuuper22/polymarket_bot.git
cd polymarket_bot
pip install -r requirements.txt
```

No API keys required to run benchmarks. Optional keys (Claude, Reddit) improve sentiment analysis.

## Quick Start

```bash
# Run benchmarks (no API keys needed)
python run_benchmarks.py

# Paper trading
python main.py paper --capital 75 --run --interval 15

# Check status
python main.py paper --status

# Scan for opportunities
python main.py scan --min-edge 0.08

# Backtest historical data
python main.py backtest --capital 75 --days 30 --show-trades
```

## Project Structure

```
src/
├── analysis/         # LLM + sentiment (Claude, Grok, VADER/TextBlob)
├── backtesting/      # 7 modules: Monte Carlo, benchmark suites, microstructure
├── data/             # Polymarket API, Reddit, RSS, price tracking
├── strategies/       # 8 strategies including regime detection + edge detection
└── trading/          # Paper trader

config/               # Strategy parameters (aggressive, optimized, base)
docs/                 # Architecture docs (100KB+ of design documentation)
```

Root-level scripts (`paper_trade_runner.py`, `swing_trader.py`, etc.) are entry points and development iterations - the .bat files reference them. The core logic lives in `src/`.

The project includes Windows automation (.bat scripts) and PyInstaller packaging (.spec files) because I actually use this. It is not a portfolio piece that runs once in a notebook. It is built for daily paper-trading experiments on my machine.

## What To Inspect

- `src/strategies/robust_strategy.py` and `src/strategies/edge_detector.py` for regime detection and trade gating.
- `src/strategies/position_sizer.py` for Kelly sizing and risk caps.
- `src/backtesting/benchmark_suite.py` for scenario-based validation.
- `src/backtesting/deployment_simulator.py` for Monte Carlo deployment simulation.
- `BENCHMARK_RESULTS.md` for full results and limitations.

## Risk Management

| Parameter | Value | Reason |
|-----------|-------|--------|
| Kelly Fraction | 25% (quarter-Kelly) | Safety margin on edge estimates |
| Max Position | 15% of capital | Diversification |
| Max Concurrent | 5 positions | Spread risk |
| Max Exposure | 80% | Keep reserves |
| Stop Loss | 35% drawdown | Capital preservation |

## Safe Inspection

Run benchmarks and paper-trading mode first. The repo is useful as a decision-systems project even without a live trading account:

```bash
python run_benchmarks.py
python main.py paper --capital 75 --status
```

## Caveats

**All results are simulated.** The benchmark suite tests decision logic against synthetic market scenarios. Live markets are messier: wider spreads, thinner books, correlated liquidations. This is acknowledged by design. The project's purpose is learning to make decisions under uncertainty, not generating returns.

**Edge estimates are always wrong.** The Kelly criterion section explains why positions are capped. This is not false modesty. It is the central engineering constraint. If your edge estimate were perfect, you would not need Kelly.

**No live trading history.** This has been paper-traded. No real money at risk yet.

**No baseline comparison.** The simulation results don't include a random-entry or buy-and-hold baseline, which means the absolute numbers lack context. The relative value is in the regime detection - trap avoidance and confidence-scaled sizing - not the headline return.

## Related Projects

- **[jobhunter](https://github.com/Cuuper22/jobhunter)** - Same restraint principle: an AI agent that knows when NOT to act
- **[Erdos](https://github.com/Cuuper22/Erdos)** - Decision-making under formal constraints. If polymarket_bot asks "should I trade?", Erdos asks "is this proof valid?"

---

[cuuper22.github.io](https://cuuper22.github.io) · [GitHub](https://github.com/Cuuper22)

## License

MIT. Use at your own risk.
