# Memory

Self-healing log of lessons learned. Written by the Reviewer role at the end of a failed
task's correction loop — never by hand. Read this file at the start of every session and
apply every lesson below before starting work.

Each entry follows this exact format:

```
## [date] — <short title>
- What failed:
- Root cause:
- Fix:
- How to avoid it next time:
```

## 2026-07-08 — FractionalBacktest desyncs custom indicator columns

- What failed: `run_backtest` used `backtesting.lib.FractionalBacktest` to support
  BTC/USDT's high unit price, but SL/TP orders came out with nonsensical negative
  prices.
- Root cause: `FractionalBacktest` rescales only the standard OHLC columns internally.
  The custom `atr` column `tools/indicators.py` adds stays at its original (unscaled)
  value, so `self.data.Close` (scaled) and `self.data.atr` (unscaled) end up in
  different unit systems inside the generated strategy's `next()`.
- Fix: use plain `backtesting.Backtest` with a large notional `cash` (1,000,000) instead
  — `Strategy.buy()` already defaults to sizing as a fraction of equity (`size=.9999`),
  which affords a whole BTC unit without needing any internal rescaling.
- How to avoid it next time: never reach for `FractionalBacktest` in this project. If a
  future instrument needs true sub-unit position sizing, increase `DEFAULT_CASH` further
  rather than switching backtest classes, since any custom (non-OHLC) column added by
  `tools/indicators.py` will not be rescaled consistently.

## 2026-07-08 — Vite's newest major version needs a newer Node than this machine has

- What failed: `npm create vite@latest frontend -- --template react` scaffolded Vite 8,
  which defaults to the "rolldown" bundler and requires Node 20.19+/22.12+. `npm run dev`
  crashed with a missing native binding on this machine's Node 20.13.0.
- Root cause: Vite 8's rolldown native binding isn't compatible with Node < 20.19, and
  reinstalling node_modules doesn't fix a genuine Node-version mismatch.
- Fix: pinned `vite` to `^5.4.11` and `@vitejs/plugin-react` to `^4.3.4` in
  `frontend/package.json` (classic Rollup/esbuild bundler, no native-binding
  requirement), then reinstalled.
- How to avoid it next time: don't use `vite@latest` on this machine without checking
  Node compatibility first. Vite 5.x is the safe default here. Known tradeoff: Vite 5's
  esbuild dependency has a moderate dev-server-only vulnerability
  (GHSA-67mh-4wv8-2f99), only patched in Vite 6+; accepted for now since this is a
  local-only personal tool (dev server binds to localhost by default) — revisit if Node
  is ever upgraded.
