"""Wraps backtesting.py and returns exactly the metrics docs/development/workflows/backtest_strategy.md
requires, with the three documented edge cases handled explicitly rather than silently
producing a misleading "perfect" result.

run_report() adds a chronological in-sample / out-of-sample split on top: indicators are
computed once over the full history (they are causal, so nothing leaks backwards), then
each slice is backtested independently.
"""

import math

import pandas as pd
from backtesting import Backtest

from tools.schemas import BacktestMetrics, BacktestReport, Bar, Direction, SampleVerdict, Trade

# Notional backtest cash — not meant to represent real user capital, just large enough
# that at least one whole unit of any supported instrument (including BTC at ~$100k) is
# affordable at the smallest position size. Metrics returned (profit factor, win rate,
# expectancy, drawdown) are all ratio-based, so the absolute cash amount doesn't affect
# them. Deliberately using plain Backtest (not FractionalBacktest) — FractionalBacktest
# rescales only the OHLC columns internally, which would desync self.data.Close from the
# unscaled custom "atr" column tools/indicators.py adds, corrupting the ATR-based SL/TP.
DEFAULT_CASH = 1_000_000
DEFAULT_COMMISSION = 0.001  # 0.1%, a reasonable default retail commission/spread proxy

DEFAULT_IN_SAMPLE_FRACTION = 0.7
# Below this many out-of-sample trades the verdict is "inconclusive", not pass/fail.
MIN_OOS_TRADES = 5


def run_backtest(
    strategy_class,
    combined_df: pd.DataFrame,
    available_range: tuple[str, str] | None = None,
) -> BacktestMetrics:
    metrics, _ = _run(strategy_class, combined_df, available_range)
    return metrics


def run_report(
    strategy_class,
    combined_df: pd.DataFrame,
    available_range: tuple[str, str] | None = None,
    in_sample_fraction: float = DEFAULT_IN_SAMPLE_FRACTION,
) -> BacktestReport:
    full, trades = _run(strategy_class, combined_df, available_range)
    split = int(len(combined_df) * in_sample_fraction)
    in_sample, _ = _run(strategy_class, combined_df.iloc[:split])
    out_of_sample, _ = _run(strategy_class, combined_df.iloc[split:])
    verdict, reason = _oos_verdict(in_sample, out_of_sample)

    return BacktestReport(
        full=full,
        in_sample=in_sample,
        out_of_sample=out_of_sample,
        split_time=_unix(combined_df.index[split]),
        oos_verdict=verdict,
        oos_reason=reason,
        trades=trades,
        bars=[
            Bar(time=_unix(ts), open=o, high=h, low=lo, close=c)
            for ts, o, h, lo, c in zip(
                combined_df.index,
                combined_df["Open"],
                combined_df["High"],
                combined_df["Low"],
                combined_df["Close"],
                strict=True,
            )
        ],
    )


def _run(
    strategy_class,
    combined_df: pd.DataFrame,
    available_range: tuple[str, str] | None = None,
) -> tuple[BacktestMetrics, list[Trade]]:
    bt = Backtest(
        combined_df,
        strategy_class,
        cash=DEFAULT_CASH,
        commission=DEFAULT_COMMISSION,
        exclusive_orders=True,
        # Close a position still open on the last bar so it counts, instead of
        # silently vanishing from the stats (and from each half of the split).
        finalize_trades=True,
    )
    stats = bt.run()

    notes: list[str] = []
    if available_range is not None:
        notes.append(f"data range used: {available_range[0]} to {available_range[1]}")

    total_trades = int(stats["# Trades"])
    equity_curve = stats["_equity_curve"]["Equity"].tolist()
    context = dict(
        return_pct=_num(stats["Return [%]"]),
        buy_hold_return_pct=_num(stats["Buy & Hold Return [%]"]),
        exposure_pct=_num(stats["Exposure Time [%]"]),
    )

    if total_trades == 0:
        notes.append(
            "zero trades generated over the backtest period — treated as a failed "
            "backtest, not a profitable one"
        )
        metrics = BacktestMetrics(
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            max_drawdown=0.0,
            equity_curve=equity_curve,
            notes=notes,
            **context,
        )
        return metrics, []

    trades = stats["_trades"]
    directions = set(trades["Size"] > 0)
    if len(directions) == 1:
        notes.append(f"all trades were {'long' if True in directions else 'short'}-only")

    profit_factor = float(stats["Profit Factor"]) if pd.notna(stats["Profit Factor"]) else 0.0

    metrics = BacktestMetrics(
        total_trades=total_trades,
        win_rate=float(stats["Win Rate [%]"]) / 100.0,
        profit_factor=profit_factor,
        expectancy=float(trades["ReturnPct"].mean()),
        max_drawdown=abs(float(stats["Max. Drawdown [%]"])) / 100.0,
        equity_curve=equity_curve,
        cagr_pct=_num(stats["CAGR [%]"]),
        sharpe=_num(stats["Sharpe Ratio"]),
        sortino=_num(stats["Sortino Ratio"]),
        notes=notes,
        **context,
    )
    last_bar = len(combined_df) - 1
    return metrics, [_trade(row, last_bar) for row in trades.itertuples()]


def _has_edge(m: BacktestMetrics) -> bool:
    return m.total_trades > 0 and m.profit_factor > 1 and m.expectancy > 0


def _oos_verdict(ins: BacktestMetrics, oos: BacktestMetrics) -> tuple[SampleVerdict, str]:
    """Pass only when the edge exists in-sample AND survives out-of-sample: a strategy
    that loses in-sample and happens to win the last slice has no edge to confirm."""
    if oos.total_trades < MIN_OOS_TRADES:
        return (
            SampleVerdict.INCONCLUSIVE,
            f"only {oos.total_trades} out-of-sample trade(s); at least {MIN_OOS_TRADES} are "
            "needed before the result means anything",
        )
    if not _has_edge(ins):
        return SampleVerdict.FAIL, "no edge in-sample (profit factor <= 1 or non-positive expectancy)"
    if _has_edge(oos):
        return SampleVerdict.PASS, "profit factor > 1 and positive expectancy in-sample and out-of-sample"
    return SampleVerdict.FAIL, "the in-sample edge does not hold on the out-of-sample period"


def _trade(row, last_bar: int) -> Trade:
    side = Direction.LONG if row.Size > 0 else Direction.SHORT
    sign = 1 if side == Direction.LONG else -1
    if pd.notna(row.SL) and sign * (row.ExitPrice - row.SL) <= 0:
        reason = "stop-loss"
    elif pd.notna(row.TP) and sign * (row.ExitPrice - row.TP) >= 0:
        reason = "take-profit"
    elif row.ExitBar >= last_bar:
        reason = "end of data"
    else:
        reason = "other"
    return Trade(
        entry_time=_unix(row.EntryTime),
        exit_time=_unix(row.ExitTime),
        side=side,
        entry_price=float(row.EntryPrice),
        exit_price=float(row.ExitPrice),
        return_pct=float(row.ReturnPct),
        exit_reason=reason,
    )


def _num(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _unix(ts: pd.Timestamp) -> int:
    return int(pd.Timestamp(ts).timestamp())
