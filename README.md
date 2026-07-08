# Strategy Creator

**A full-stack tool that generates 100% systematic, backtested trading strategies —
deterministically, with zero AI in the runtime loop.**

You pick a pair, a timeframe profile, a handful of indicators, and a risk level. The
backend composes an objective, rule-based strategy from a closed catalog of primitives,
mechanically verifies it can't contain any discretionary logic, renders it as standalone
Python you can run yourself, and backtests it against real market data — all before it
ever reaches your screen.

## Why this project

Most "AI strategy generator" demos ask an LLM to freestyle trading rules at request time.
That's fast to build and impossible to trust: the same prompt can yield a different
strategy tomorrow, and nothing stops the model from inventing a condition like "if the
chart looks bullish." A strategy that isn't 100% mechanical can't be automated, audited,
or reasoned about mathematically.

This project takes the opposite bet: **push all reasoning into deterministic code, and
keep it out of the runtime path entirely.**

- Every strategy is built by composing a fixed, closed catalog of objective primitives
  (e.g. *"RSI crosses above 30"*, *"ADX > threshold"*, *"SL = entry − N × ATR"*) — never
  free-form conditions.
- A linter mechanically checks every generated strategy against that catalog before it's
  shown to the user: closed-catalog compliance, TP/SL always defined, a confirmation rule
  from a higher timeframe always present, no unbound thresholds.
- The same inputs always produce the exact same strategy — byte-identical generated code,
  every time.
- Every risk-level parameter (SL/TP sizing, entry thresholds) is empirically validated
  against real historical data, not just asserted — see [Results](#results) below.

The result reads less like a chatbot demo and more like a small compiler: **inputs →
closed-catalog IR → validated → codegen → backtest**, with a human-readable strategy
sheet at every step of the way.

## How it works

```
┌────────────┐   POST /api/strategy    ┌──────────────────────────────────────────┐
│  React UI  │ ───────────────────────▶│              FastAPI backend              │
│  (Vite)    │◀─────────────────────── │  (thin orchestration, zero business logic) │
└────────────┘   sheet + code + metrics└──────────────────────────────────────────┘
                                                        │
                                                        ▼
        ┌─────────────────────────────────────────────────────────────────────┐
        │ 1. compose_strategy()   closed-catalog primitives → StrategySpec     │
        │ 2. lint()               mechanically reject anything non-objective   │
        │ 3. generate_code()      render a standalone backtesting.py Strategy  │
        │ 4. fetch_ohlcv()        Binance / yfinance, local parquet cache      │
        │ 5. compute_indicators() hand-rolled RSI/EMA/ADX/ATR/VWAP/Vol.Profile │
        │ 6. run_backtest()       real profit factor, win rate, drawdown       │
        └─────────────────────────────────────────────────────────────────────┘
```

Each numbered step is an independently testable, single-purpose module under
[`tools/`](tools/) — no step trusts the one before it blindly (the code generator
re-lints before rendering; the strategy linter re-checks the catalog even though the
type system already constrains it). See [`CLAUDE.md`](CLAUDE.md) and
[`workflows/`](workflows/) for the full design rationale.

## Engineering highlights

- **Look-ahead-bias-safe by construction.** Confirmation-timeframe signals are shifted
  forward by a full bar period before being merged into the execution timeframe, so a
  4h bar's value only becomes visible to 1h rows *after* it has actually closed —
  covered by a dedicated regression test, not just asserted in a docstring.
- **Correctness-by-construction, not by convention.** Every enum in the data contract
  (`tools/schemas.py`) is a real `Enum`, so an out-of-catalog primitive type is a
  `ValidationError` at construction time, not a runtime surprise three layers down.
- **No hidden dependencies.** RSI, ADX, ATR, EMA, VWAP, and a rolling Volume Profile are
  all hand-rolled in plain pandas/numpy — no TA-Lib (C-library install pain on Windows),
  no black-box indicator library. Every formula is auditable in one file.
- **62 tests**, including unit coverage for every pipeline stage, a look-ahead-bias
  regression, an objectivity-linter test per rejection rule, and one full end-to-end
  integration test that scripts a real strategy through the entire pipeline and asserts
  all four project success criteria in a single run.
- **Empirically validated, not just asserted.** Risk-level parameters were tuned against
  real cached market data until a working combo cleared profit factor > 1 with positive
  expectancy at every risk tier — the failed attempts are documented alongside the
  winning one in [`docs/calibration_notes.md`](docs/calibration_notes.md), not hidden.

## Results

Backtested against real BTC/USDT data (Binance), swing profile (1D execution / 1W
confirmation), single-EMA strategy:

| Risk level   | Trades | Win rate | Profit factor | Expectancy/trade | Max drawdown |
|--------------|:------:|:--------:|:--------------:|:-----------------:|:-------------:|
| Conservative |   13   |  76.9%   |     4.57       |      +2.92%        |     6.7%      |
| Medium       |   13   |  46.2%   |     1.40       |      +1.21%        |    24.1%      |
| Aggressive   |   11   |  45.5%   |     2.09       |      +4.67%        |    28.5%      |

Full methodology, including the combinations that *didn't* clear the bar, is in
[`docs/calibration_notes.md`](docs/calibration_notes.md).

## Tech stack

| Layer               | Choice                                                          |
|----------------------|------------------------------------------------------------------|
| Rules engine / linter / codegen | Python, Pydantic v2 (closed-catalog enums as the enforcement mechanism) |
| Indicators           | Hand-rolled pandas/numpy (Wilder-smoothed RSI/ATR/ADX, session-anchored VWAP, rolling Volume Profile) |
| Data                 | Binance REST API (crypto) + yfinance ETF proxies (SPY/QQQ/GLD for equities/gold), local Parquet cache with incremental refresh |
| Backtesting          | [`backtesting.py`](https://kernc.github.io/backtesting.py/) |
| Backend              | FastAPI |
| Frontend             | React + Vite |
| Testing              | pytest (62 tests: unit, integration, look-ahead-bias regression, end-to-end) |

## Getting started

**Backend**

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt

python init.py                  # pre-flight structure/test check
pytest                          # 59 tests, network-dependent ones excluded by default
pytest -m integration           # the 3 tests that hit real Binance/yfinance data

uvicorn backend.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev                     # proxies /api/* to localhost:8000
```

## Project structure

```
tools/                  Deterministic pipeline — the actual product logic
  schemas.py               Shared data contract (Pydantic models, closed-catalog enums)
  strategy_rules_engine.py Composes a StrategySpec from user inputs
  strategy_linter.py       Mechanically enforces objectivity/executability
  code_generator.py        Renders a standalone backtesting.py Strategy
  fetch_market_data.py     Binance/yfinance + Parquet caching, incremental refresh
  indicators.py            Hand-rolled indicator math + look-ahead-safe signal merging
  backtest_runner.py       Wraps backtesting.py, returns objective metrics
backend/main.py          Thin FastAPI orchestration layer
frontend/                React + Vite UI
tests/                   62 tests mirroring the pipeline, 1:1 with tools/
workflows/                Design-spec docs — the source of truth each tool implements
docs/calibration_notes.md Empirical risk-parameter validation, methodology + results
```

## Disclaimer

This is a personal engineering project exploring systematic strategy generation and
backtesting. Nothing here is financial advice, and a backtest — however rigorously
computed — is not a guarantee of future performance.
