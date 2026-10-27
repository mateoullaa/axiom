# Axiom

A tool that generates **systematic, fully objective** trading strategies. The user picks a
pair, a direction, a timeframe profile, a set of indicators, and a risk level; the tool
composes a strategy from a closed catalog of objective rule primitives (no LLM involved in
generation), renders it as a standalone Python file, and backtests that file against free
historical data with an in-sample / out-of-sample split.

Stack: Python (FastAPI) backend/logic + React (Vite, Tailwind, Lightweight Charts) frontend.

## Before making any change

Run `python docs/development/init.py` first. If it fails, **stop and ask** — do not work
around a failing pre-flight check.

## At the start of every session

Read [docs/development/memory.md](docs/development/memory.md) and apply its lessons before
doing anything else.

## How work gets done (WAT)

- **Workflows** ([docs/development/workflows/](docs/development/workflows/)) — SOPs for the
  core processes: generating a strategy, backtesting it, validating it. Read the relevant
  workflow before touching the matching tool.
- **Tools** ([tools/](tools/)) — deterministic Python scripts that do the real work (data
  fetching, indicator math, the rules engine, the linter, backtesting, code generation).
  All strategy-generation logic lives here, never in a prompt.
- **Agent** — one agent, three sequential roles, never parallel subagents for this
  project:
  - [planner](docs/development/roles/planner.md) — turns an objective into an audited task list.
  - [builder](docs/development/roles/builder.md) — implements one task at a time.
  - [reviewer](docs/development/roles/reviewer.md) — verifies each task, logs lessons to
    memory.md, blocks progress on failure.

## Core architectural decision

Strategies are composed by a **deterministic rules engine** (`tools/strategy_rules_engine.py`)
over a **closed catalog of objective primitives** — never by an LLM at runtime. This is
non-negotiable: it's what guarantees every generated strategy is 100% objective,
reproducible, and automatable. See
[docs/development/workflows/generate_strategy.md](docs/development/workflows/generate_strategy.md)
for the full spec (pairs, directions, timeframe profiles, indicators, sessions, risk levels).

The backend backtests the **generated module itself** (its `compute_signals()` and Strategy
class), so the downloadable file is exactly what produced the numbers. Keep it that way:
`tools/indicators.signal_spec()` is the single rule → function mapping both paths use.

## Checks

- Backend: `pytest` (network tests excluded; `pytest -m integration` runs them) and `ruff check .`
- Frontend: `cd frontend && npm run lint && npm run build`
- README results: `python scripts/reproduce_results.py`; screenshots/GIF: `python scripts/capture_assets.py`

## Language rule

All project artifacts (code, docs, commit messages, comments) are written in **English**,
and so is communication with the user.

## Skills & MCP

Check whether an existing Skill or MCP already solves a task before writing new code.
Never preload dependencies "just in case" — install only what a specific task needs.

## Data & secrets

Historical market data is cached locally under `data_cache/` (gitignored). No paid APIs
are used. No credentials are required for the current scope; if that changes, secrets go
in `.env` only.
