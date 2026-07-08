# Workflow: Backtest Strategy

Runs a generated, already-linted strategy against real historical data and produces the
objective profitability metrics required by the project's success criteria.

## Objective

Given a strategy produced by `workflows/generate_strategy.md` and the pair/timeframe
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
   combined dataframe, returns the metrics below.

## Expected output

At minimum: total trades, win rate, profit factor, expectancy per trade, max drawdown,
and the equity curve. A strategy is considered to satisfy the project's success criterion
when profit factor > 1 and expectancy per trade is positive over the available history —
`workflows/validate_strategy.md` does not check this; only this workflow does.

## Edge cases

- **Zero trades generated** over the backtest period — report this explicitly rather than
  a vacuous "0% drawdown, infinite profit factor"; treat it as a failed backtest, not a
  perfect one.
- **Insufficient historical range** for the requested timeframe (e.g. 1m data typically
  only available for the last ~60 days from free sources) — surface the actual available
  range used, don't silently backtest over a shorter window without saying so.
- **All trades in one direction** (e.g. strategy never shorts) — note it; not necessarily
  a failure, but relevant context for the strategy sheet.
