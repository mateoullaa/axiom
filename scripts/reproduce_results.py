"""Regenerate the README results table on a fixed historical window.

Runs the exact pipeline the API runs (rules engine -> linter -> generated module ->
backtest report) for a fixed set of strategies, with signals computed on the full
fetched history and the backtest trimmed to WINDOW, so anyone can reproduce the numbers
on a fresh clone. Needs network access (Binance for BTC/USDT, Yahoo Finance for the ETFs).

Usage:
    python scripts/reproduce_results.py
"""

import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.backtest_runner import run_report  # noqa: E402
from tools.code_generator import generate_code  # noqa: E402
from tools.fetch_market_data import fetch_ohlcv  # noqa: E402
from tools.schemas import TIMEFRAME_PROFILE_MAP, StrategyInputs  # noqa: E402
from tools.strategy_rules_engine import compose_strategy  # noqa: E402

WINDOW = ("2019-01-01", "2026-07-01")
# Extra history before WINDOW so the weekly EMA confirmation is warmed up on day one.
FETCH_DAYS = 3400

CASES = [
    dict(pair="BTC/USDT", timeframe_profile="swing", indicators=["EMA"], risk_level="conservative"),
    dict(pair="BTC/USDT", timeframe_profile="swing", indicators=["EMA"], risk_level="medium"),
    dict(pair="BTC/USDT", timeframe_profile="swing", indicators=["EMA"], risk_level="aggressive"),
    dict(pair="BTC/USDT", timeframe_profile="swing", indicators=["EMA"], risk_level="medium", direction="short"),
    dict(pair="SP500", timeframe_profile="swing", indicators=["EMA"], risk_level="medium"),
    dict(pair="Gold", timeframe_profile="swing", indicators=["EMA"], risk_level="medium"),
]


def run_case(case: dict) -> dict:
    inputs = StrategyInputs(**case)
    spec = compose_strategy(inputs)
    namespace: dict = {"__name__": "axiom_generated"}
    exec(compile(generate_code(spec), "<generated>", "exec"), namespace)

    exec_tf, confirm_tf = TIMEFRAME_PROFILE_MAP[inputs.timeframe_profile]
    exec_df = fetch_ohlcv(inputs.pair, exec_tf, lookback_days=FETCH_DAYS)
    confirm_df = fetch_ohlcv(inputs.pair, confirm_tf, lookback_days=FETCH_DAYS)
    combined = namespace["compute_signals"](exec_df, confirm_df)
    start, end = (pd.Timestamp(d, tz="UTC") for d in WINDOW)
    combined = combined[(combined.index >= start) & (combined.index < end)]

    report = run_report(namespace["GeneratedStrategy"], combined)
    return {"inputs": inputs, "report": report}


def _pct(value: float | None, scale: float = 1.0) -> str:
    return "n/a" if value is None else f"{value * scale:+.1f}%"


def to_markdown(rows: list[dict]) -> str:
    lines = [
        "| Strategy | Trades | Win rate | Profit factor | Expectancy / trade | Max DD | Return | Buy & hold "
        "| IS PF | OOS PF (trades) | Out-of-sample |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        i, r = row["inputs"], row["report"]
        f, ins, oos = r.full, r.in_sample, r.out_of_sample
        name = f"{i.pair.value} · {i.timeframe_profile.value} · EMA · {i.risk_level.value} · {i.direction.value}"
        lines.append(
            f"| {name} | {f.total_trades} | {f.win_rate:.0%} | {f.profit_factor:.2f} | "
            f"{_pct(f.expectancy, 100)} | {f.max_drawdown:.1%} | {_pct(f.return_pct)} | "
            f"{_pct(f.buy_hold_return_pct)} | {ins.profit_factor:.2f} | "
            f"{oos.profit_factor:.2f} ({oos.total_trades}) | {r.oos_verdict.value} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    rows = [run_case(case) for case in CASES]
    print(f"Window: {WINDOW[0]} to {WINDOW[1]} (UTC), 70/30 chronological split\n")
    print(to_markdown(rows))
