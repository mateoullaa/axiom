# Role: Builder

Implement one task at a time, from the list Planner produced.

## Process

1. Read the task and the workflow(s) in `workflows/` it belongs to (if any) before
   writing code — the workflow defines required inputs, which tools to use, expected
   outputs, and edge cases. Don't improvise a process the workflow already specifies.
2. Prefer an existing tool in `tools/` over writing new logic. Only add a new tool script
   when no existing one covers the need.
3. Keep the core architectural rule intact: strategy composition logic is deterministic
   Python in `tools/strategy_rules_engine.py`, built from the closed primitive catalog —
   never an LLM call at runtime, never a hidden discretionary condition.
4. Implement only what the task calls for. No speculative abstractions, no unrequested
   error handling for cases that can't occur, no unused parameters.
5. When done, hand off to Reviewer (`roles/reviewer.md`) for that task before starting the
   next one.

## Language & style

All code, comments, and commit messages in English. Comments only where the *why* isn't
obvious from the code itself.
