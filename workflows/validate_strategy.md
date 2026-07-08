# Workflow: Validate Strategy

The objectivity/executability gate. Runs after generation, before a strategy is ever
shown to the user or handed to the backtest workflow.

## Objective

Mechanically guarantee that a generated strategy is 100% objective and automatable — the
project's core, non-negotiable requirement — instead of trusting that the rules engine
"behaved."

## Required inputs

The composed strategy object from `tools/strategy_rules_engine.py` (before it's rendered
to Python code).

## Tool used

`tools/strategy_linter.py` — runs the checklist below and returns pass/fail plus a list
of specific violations. Never partially passes; any violation blocks the strategy.

## Checklist enforced

- **Closed catalog only** — every entry, confirmation, and exit rule must be one of the
  primitives listed in `workflows/generate_strategy.md`. Anything else is a violation by
  definition.
- **TP always defined** — a strategy with no explicit take-profit rule fails.
- **SL always defined** — a strategy with no explicit stop-loss rule fails.
- **Confirmation rule present** — at least one confirmation-timeframe primitive must gate
  entries (see `workflows/generate_strategy.md`'s timeframe-profile requirement).
- **Session filter present when required** — scalping strategies must carry a session
  filter; non-scalping strategies must not (there's nothing to filter).
- **No unbound thresholds** — every primitive with a numeric parameter (RSI threshold, ADX
  threshold, ATR multiple, volume multiple) must have a concrete value, not a placeholder.

## On failure

Do not show the strategy to the user and do not proceed to
`workflows/backtest_strategy.md`. Return the specific violation(s) to the rules engine
step of `workflows/generate_strategy.md` so Builder can fix the composition logic —
this is a bug in the rules engine, not something to patch by hand on the individual
strategy.
