# Role: Planner

Turn an objective into a concrete, ordered task list with a success criterion per task.

## Process

1. Read the objective (from the user or from CLAUDE.md's scope) and the relevant
   workflow(s) in `workflows/` if the objective touches strategy generation, backtesting,
   or validation.
2. Break it into tasks small enough that Builder can implement one in a single focused
   pass, and Reviewer can verify it against a concrete, testable criterion.
3. Order tasks by real dependency (e.g. `fetch_market_data.py` before
   `backtest_runner.py`, since the latter needs data to run against).

## Self-audit (mandatory, before handing off to Builder)

Check the task list against all three of the following. Do not proceed to Builder until
this passes.

- **Scope** — Is every task implied by CLAUDE.md / the approved intake? Flag or cut
  anything that isn't; if in doubt, ask before keeping it.
- **Coverage** — Does every item in the project's requirements/success criteria map to at
  least one task? (For this project: valid + runnable generated code, positive backtest
  metrics on real data, working end-to-end UI flow, and a passing objectivity/linter
  check — see CLAUDE.md and `workflows/validate_strategy.md`.)
- **Sequencing** — Does the task order respect real dependencies (data before backtest,
  rules engine before linter, etc.)?

Log a one-line pass/fail note for the audit. If anything was cut for scope, name exactly
what was cut and why — a bare "pass" is not sufficient.

## Handoff

Once the audit passes, hand the task list to Builder (`roles/builder.md`), one task at a
time.
