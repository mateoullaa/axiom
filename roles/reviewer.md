# Role: Reviewer

Runs at the end of every task Builder completes. Verifies output before allowing the next
task to start.

## Process

1. Confirm the output actually exists (file written, function callable, endpoint
   reachable — whatever the task claimed to produce).
2. Confirm it passes its own tests, if any exist for that piece.
3. Confirm it meets the expected contract/schema for that task (e.g. a tool in `tools/`
   returns the shape the workflow says it should; a generated strategy passes
   `strategy_linter.py`; a backtest result includes the metrics `workflows/backtest_strategy.md`
   requires).

## On failure

Do **not** advance to the next task. Trigger the correction loop:

1. Hand back to Builder with what specifically failed.
2. Builder fixes it.
3. Reviewer re-verifies.
4. Append a lesson to [memory.md](../memory.md) in the fixed format:

   ```
   ## [date] — <short title>
   - What failed:
   - Root cause:
   - Fix:
   - How to avoid it next time:
   ```

5. Only then continue.

## On success

Log a one-line note (what was verified, how) and advance to the next task.
