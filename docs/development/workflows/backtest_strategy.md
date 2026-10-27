# Workflow: Backtest Strategy

Runs a generated, already-linted strategy against real historical data and produces the
objective profitability metrics required by the project's success criteria.

## Objective

Given a strategy produced by `docs/development/workflows/generate_strategy.md` and the pair/timeframe
profile it was built for, run a backtest with `backtesting.py` and return metrics that
say whether the strategy is mathematically viable — not just whether it runs.

## Required inputs

- The generated strategy (as a `backtesting.py` `Strategy` subclass from
  `code_generator.py`).
- Pair and timeframe profile (determines which cached dataset to use).

## Tools used (in order)

1. `tools/fetch_market_data.py` — ensures cached OHLCV data for the pair, execution
   timeframe, and confirmation timeframe is present and fresh (see its own docstring for
   the staleness threshold per timeframe). Downloads only the missing delta, not a full
   re-download, when the cache is merely stale.
2. `tools/indicators.py` — computes the indicators the strategy needs on the execution
   timeframe dataframe, and merges the confirmation-timeframe indicator(s) in via
   resample + forward-fill so `backtesting.py` (single-timeframe by design) sees one
   combined dataframe.
3. `tools/backtest_runner.py` — wraps `backtesting.py`, runs the strategy against the
   combined dataframe, returns the metrics below. `run_report()` also backtests the first
   70% and the last 30% of bars separately (chronological split; indicators are computed
   once over the full history, which is safe because they are causal).

The API runs steps 2–3 through the **generated module** (`compute_signals()` + Strategy
class) rather than through `tools/indicators.py` directly, so the exported file is exactly
what was backtested. A test asserts both paths produce identical columns.

## Expected output

At minimum: total trades, win rate, profit factor, expectancy per trade, max drawdown,
and the equity curve; plus return vs buy & hold, CAGR, Sharpe, Sortino, exposure and the
trade list. A strategy is considered to satisfy the project's success criterion
when profit factor > 1 and expectancy per trade is positive over the available history —
`docs/development/workflows/validate_strategy.md` does not check this; only this workflow does.

**Out-of-sample verdict:** `pass` only if the edge (profit factor > 1, positive expectancy)
exists in-sample **and** holds out-of-sample; `fail` otherwise; `inconclusive` when the
out-of-sample slice has fewer than 5 trades. Rule constants are fixed by the catalog, not
fitted per run, so this is a stability check across time, not a parameter-overfitting test.

## Edge cases

- **Zero trades generated** over the backtest period — report this explicitly rather than
  a vacuous "0% drawdown, infinite profit factor"; treat it as a failed backtest, not a
  perfect one.
- **Insufficient historical range** for the requested timeframe (e.g. 1m data typically
  only available for the last ~60 days from free sources) — surface the actual available
  range used, don't silently backtest over a shorter window without saying so.
- **All trades in one direction** — expected, since each strategy trades one side; noted
  in the metrics for context.
- **Position still open on the last bar** — closed at the last close and counted
  (`finalize_trades=True`), instead of silently dropped from the stats.
