# Workflow: Generate Strategy

Canonical spec for turning a user's selections into a fully objective, executable
strategy. This is the single source of truth for pairs, timeframe profiles, indicators,
sessions, and risk levels — other workflows and tools reference this one instead of
duplicating the list.

## Objective

Given a pair, a timeframe profile, a set of indicators, a risk level, and (if scalping) a
session, produce a strategy made entirely of primitives from the closed catalog below —
never a freeform or discretionary condition.

## Required inputs

- **Pair** — one of: `BTC/USDT`, `SP500`, `Nasdaq`, `Gold`.
- **Timeframe profile** — one of:
  - `scalping` — execution 1m–5m, confirmation 15m. Requires a **session**.
  - `daily` — execution 15m–1h, confirmation 4h.
  - `swing` — execution 4h–1D, confirmation 1W.
- **Session** (scalping only) — one of: `Asia`, `London`, `NY AM`, `NY PM`.
- **Indicators** — one or more of: `RSI`, `ADX`, `VWAP`, `EMA`, `ATR`, `Volume Profile`,
  `Volume`.
- **Risk level** — one of: `conservative`, `medium`, `aggressive`.

## Primitive catalog (closed — the rules engine may only compose from this list)

- **RSI** — cross above/below a threshold (entry signal); value above/below 50 on the
  confirmation timeframe (directional bias filter).
- **ADX** — value above a threshold (trend-strength filter; gates whether a
  trend-following entry is allowed at all).
- **VWAP** — price crosses above/below VWAP (entry signal); price above/below VWAP on the
  confirmation timeframe (bias filter).
- **EMA** — fast EMA crosses slow EMA (entry signal); price above/below an EMA (bias
  filter).
- **ATR** — not a signal; used to size `SL = entry ± N × ATR` and `TP = entry ± M × ATR`.
  `N` and `M` are calibrated per risk level (see below).
- **Volume** — current volume exceeds a multiple of its recent average (confirms an entry
  signal from another primitive; never a standalone entry).
- **Volume Profile** — price at/near a high-volume node (support/resistance zone; used as
  a confirmation/entry-zone filter).

A strategy = one or more **entry primitives** (execution timeframe) + one or more
**confirmation primitives** (confirmation timeframe, required — this is what makes
scalping/daily/swing "confirm with" a higher timeframe) + an **ATR-based SL/TP formula** +
a **session filter** (scalping only).

## Risk level → parameters

Risk level controls how the ATR-based SL/TP formula and primitive thresholds are
calibrated, not whether primitives are used — objectivity is the same across all three.
General direction (exact constants are calibrated in `strategy_rules_engine.py` and
validated empirically via `workflows/backtest_strategy.md`, not asserted here):

- **Conservative** — smaller ATR multiple for SL, lower target R:R, stricter confirmation
  (require full agreement across confirmation primitives), smaller position size.
- **Medium** — balanced ATR multiple and R:R, standard confirmation strictness.
- **Aggressive** — larger ATR multiple for SL and TP (wider R:R target), more permissive
  confirmation, larger position size.

## Tools used (in order)

1. `tools/strategy_rules_engine.py` — composes entry + confirmation primitives and the
   SL/TP formula from the inputs above. Pure function of the inputs; no market data
   needed at this stage.
2. `tools/strategy_linter.py` — validates the composed strategy against
   `workflows/validate_strategy.md` before it's shown to the user.
3. `tools/code_generator.py` — renders the validated strategy as a `backtesting.py`
   `Strategy` subclass, exportable as `.py`.

## Expected output

- A strategy sheet: entry rules, confirmation rules, TP, SL, indicators used, timeframe
  profile (with both timeframes), session (if scalping).
- The generated Python code implementing the same logic, ready to hand to
  `workflows/backtest_strategy.md` or export directly.

## Edge cases

- **Indicator selection has no valid primitive combination** for the chosen timeframe
  profile (e.g. only `Volume` selected, which has no standalone entry primitive) — do not
  silently invent a discretionary rule. Reject with a specific message naming which
  indicator(s) need a companion primitive.
- **Scalping selected without a session** — block generation, ask the user to pick one.
- **Fewer than one confirmation primitive available** from the selected indicators for the
  confirmation timeframe — block generation; a strategy without a confirmation rule
  doesn't satisfy the timeframe-profile requirement.
