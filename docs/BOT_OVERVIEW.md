# Polymarket Bot: Plain‑English Guide

This bot scans Polymarket prediction markets, looks for small mispricings, and places small trades to capture those edges. It focuses on low‑cost signals from public data (news, Reddit, trends) plus order‑book microstructure from Polymarket itself.

## What the Bot Does (In Simple Terms)

1) **Collects data**
   - Live market prices and order books from Polymarket
   - News from RSS feeds
   - Reddit posts for sentiment
   - Google Trends for search interest (optional)

2) **Scores sentiment**
   - Detects whether recent text is bullish or bearish
   - Uses VADER/TextBlob if installed, otherwise a keyword fallback

3) **Finds edges**
   - Looks for mismatches between sentiment and market price
   - Checks for breaking news catalysts
   - Detects unusual volume spikes
   - Uses order book spread/inefficiency signals

4) **Sizes trades safely**
   - Uses a Kelly‑style sizing rule
   - Caps trade size by account risk limits
   - Avoids trading if the edge is too small

5) **Manages risk**
   - Limits total open exposure
   - Enforces stop‑loss and take‑profit thresholds
   - Avoids trading in illiquid markets

## Key Safety Rules

- **Minimum trade size**: $3
- **Open exposure cap**: 75% of available cash
- **Risk limits**: Max drawdown, max daily loss, max positions
- **Edge threshold**: Avoids trades unless a minimum edge is detected

## Performance Tests (Simulated)

The project includes a backtesting engine that simulates trading on generated markets. The results below are from repeated 30‑day tests using a simple sentiment‑divergence strategy with strict sizing and a $75 starting bankroll.

### Multi‑Seed Backtest Summary (5 runs)

| Seed | Final Capital | Total Return | Max Drawdown | Sharpe |
|------|---------------|--------------|--------------|--------|
| 1 | $42.31 | -43.6% | 43.6% | -5.87 |
| 2 | $68.55 | -8.6% | 29.3% | -1.17 |
| 3 | $65.75 | -12.3% | 42.2% | -3.29 |
| 4 | $40.29 | -46.3% | 54.7% | -10.82 |
| 5 | $45.72 | -39.0% | 53.9% | -8.76 |

**Interpretation:** The current simple backtest strategy is not yet stable. Results are negative across most seeds. Real‑world performance is expected to differ, but the simulation suggests the strategy needs refinement before live trading.

## Data Visualizations (ASCII)

These are text charts based on one sample backtest run to illustrate how equity, drawdown, and trade returns behaved.

### Equity Curve (Sample Run)
```
2025-12-19 | ############################## 75.00
2025-12-20 | ############################## 75.00
2025-12-22 | ############################## 75.00
2025-12-24 | ############################## 75.00
2025-12-26 | ############################## 75.00
2025-12-28 | ############                   66.73
2025-12-30 | #                              60.77
2026-01-01 | ####################           70.43
2026-01-03 | ####                           62.83
2026-01-05 | #                              60.71
2026-01-07 | #                              60.71
2026-01-09 | #                              60.71
```

### Drawdown (Sample Run)
```
2025-12-19 |                                0.00%
2025-12-20 |                                0.00%
2025-12-22 |                                0.00%
2025-12-24 |                                0.00%
2025-12-26 |                                0.00%
2025-12-28 | #################              11.03%
2025-12-30 | #############################  18.98%
2026-01-01 | #########                      6.10%
2026-01-03 | #########################      16.23%
2026-01-05 | ############################## 19.05%
2026-01-07 | ############################## 19.05%
2026-01-09 | ############################## 19.05%
```

### Trade Return Distribution (Sample Run)
```
<= -10%      |                                0
-10% to 0%   |                                0
0% to 10%    |                                0
10% to 25%   |                                0
> 25%        | ############################## 5
```

## Important Notes

- These tests are **simulated**. They don’t reflect real market slippage or fees.
- The current backtest uses **synthetic markets**, not Polymarket history.
- The strategy shown here is intentionally simple and meant for verification.

If you want, we can: 
- Add a more realistic market simulator (with spreads/fees)
- Implement multi‑market micro‑edge strategies for HFT‑style testing
- Build a full reporting dashboard with real charts
