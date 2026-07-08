# Empirical risk-level calibration (Task 9)

Per `workflows/generate_strategy.md`'s deferral ("exact constants are calibrated in code
and validated via backtest, not asserted here"), this records what was actually run
against real cached market data, and which combo(s) clear the profitability bar
(profit factor > 1, positive expectancy) at each risk level.

## Method

Fetched real BTC/USDT data via `tools/fetch_market_data.py` (Binance), ran the full
chain (`strategy_rules_engine` → `strategy_linter` → `code_generator` → `indicators` →
`backtest_runner`) for several pair/profile/indicator combinations, using the
placeholder `RISK_PARAMS` constants already in `tools/strategy_rules_engine.py`
(no tuning was needed — see Result below).

## Combos tried

| Pair | Profile | Indicators | Risk | Trades | Win rate | Profit factor | Expectancy |
|---|---|---|---|---|---|---|---|
| BTC/USDT | daily (1h/4h) | EMA | conservative | 119 | 42.9% | 0.625 | -0.17% |
| BTC/USDT | daily (1h/4h) | EMA | medium | 110 | 35.5% | 0.795 | -0.15% |
| BTC/USDT | daily (1h/4h) | EMA | aggressive | 93 | 29.0% | 0.957 | -0.04% |
| BTC/USDT | daily (1h/4h) | EMA, ADX | medium | 69 | 33.3% | 0.747 | -0.19% |
| BTC/USDT | daily (1h/4h) | VWAP | medium | 343 | 35.9% | 0.837 | -0.13% |
| BTC/USDT | daily (1h/4h) | RSI | medium | 9 | 22.2% | 0.364 | -0.67% |
| **BTC/USDT** | **swing (1d/1w)** | **EMA** | **conservative** | **13** | **76.9%** | **4.574** | **+2.92%** |
| **BTC/USDT** | **swing (1d/1w)** | **EMA** | **medium** | **13** | **46.2%** | **1.404** | **+1.21%** |
| **BTC/USDT** | **swing (1d/1w)** | **EMA** | **aggressive** | **11** | **45.5%** | **2.091** | **+4.67%** |
| BTC/USDT | swing (1d/1w) | EMA, ADX | medium | 12 | 41.7% | 1.216 | +0.70% |

## Result

**BTC/USDT, swing profile, EMA indicator clears profit factor > 1 and positive
expectancy at all three risk levels**, using the existing `RISK_PARAMS` constants
unchanged. No code changes to `strategy_rules_engine.py` were needed.

The `daily` profile (1h execution / 4h confirmation) did not clear the bar with any
combo tried — hourly BTC/USDT is noisy enough that the EMA-crossover system (and the
alternatives tried: adding an ADX trend filter, VWAP mean-reversion, RSI mean-reversion)
produces a losing edge after commission. This is a legitimate empirical outcome, not a
bug — documented here rather than silently hidden. Worth revisiting post-MVP with a
wider EMA period, an explicit regime filter, or a different primitive combination.

**Caveat:** the swing profile's trade counts (11-13 trades over ~4 years of daily bars)
are small samples. The results are directionally real (large profit factors, not
borderline) but should be read as "this configuration is viable," not as a precise,
statistically robust edge estimate.

## Chosen proof case (feeds Task 13)

**BTC/USDT, swing, indicators=[EMA], risk_level=medium** — profit factor 1.404,
expectancy +1.21% per trade, 13 trades, clears both success-criterion bars without being
the cherry-picked best number (conservative's 4.574 is stronger but medium is the more
representative "typical user" choice).
