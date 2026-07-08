# Strategy Creator

A personal tool that generates **systematic, fully objective** trading/investment
strategies. The user picks a pair, a timeframe profile, a set of indicators, and a risk
level; the tool composes a strategy from a closed catalog of objective rule primitives
(no LLM involved in generation), backtests it against free historical data, and returns
both a human-readable strategy sheet and exportable Python code.

Stack: Python backend/logic + React frontend.

## Before making any change

Run `python init.py` first. If it fails, **stop and ask** — do not work around a failing
pre-flight check.

## At the start of every session

Read [memory.md](memory.md) and apply its lessons before doing anything else.

## How work gets done (WAT)

- **Workflows** ([workflows/](workflows/)) — SOPs for the core processes: generating a
  strategy, backtesting it, validating it. Read the relevant workflow before touching the
  matching tool.
- **Tools** ([tools/](tools/)) — deterministic Python scripts that do the real work (data
  fetching, indicator math, the rules engine, the linter, backtesting, code generation).
  All strategy-generation logic lives here, never in a prompt.
- **Agent** — one agent, three sequential roles, never parallel subagents for this
  project:
  - [roles/planner.md](roles/planner.md) — turns an objective into an audited task list.
  - [roles/builder.md](roles/builder.md) — implements one task at a time.
  - [roles/reviewer.md](roles/reviewer.md) — verifies each task, logs lessons to
    memory.md, blocks progress on failure.

## Core architectural decision

Strategies are composed by a **deterministic rules engine** (`tools/strategy_rules_engine.py`)
over a **closed catalog of objective primitives** — never by an LLM at runtime. This is
non-negotiable: it's what guarantees every generated strategy is 100% objective,
reproducible, and automatable. See [workflows/generate_strategy.md](workflows/generate_strategy.md)
for the full spec (pairs, timeframe profiles, indicators, sessions, risk levels).

## Language rule

All project artifacts (code, docs, commit messages, comments) are written in **English**.
Communication with the user happens in **Spanish**.

## Skills & MCP

Check whether an existing Skill or MCP already solves a task before writing new code.
Never preload dependencies "just in case" — install only what a specific task needs.

## Data & secrets

Historical market data is cached locally under `data_cache/` (gitignored). No paid APIs
are used. No credentials are required for the current scope; if that changes, secrets go
in `.env` only.
