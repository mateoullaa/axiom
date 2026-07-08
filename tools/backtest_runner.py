"""Wraps backtesting.py and returns exactly the metrics workflows/backtest_strategy.md
requires, with the three documented edge cases handled explicitly rather than silently
producing a misleading "perfect" result.
"""

import pandas as pd
from backtesting import Backtest

from tools.schemas import BacktestMetrics

# Notional backtest cash — not meant to represent real user capital, just large enough
# that at least one whole unit of any supported instrument (including BTC at ~$100k) is
# affordable. Metrics returned (profit factor, win rate, expectancy, drawdown) are all
# ratio-based, so the absolute cash amount doesn't affect them. Deliberately using plain
# Backtest (not FractionalBacktest) — FractionalBacktest rescales only the OHLC columns
# internally, which would desync self.data.Close from the unscaled custom "atr" column
# tools/indicators.py adds, corrupting the ATR-based SL/TP formula.
DEFAULT_CASH = 1_000_000
DEFAULT_COMMISSION = 0.001  # 0.1%, a reasonable default retail commission/spread proxy


def run_backtest(
    strategy_class,
    combined_df: pd.DataFrame,
    available_range: tuple[str, str] | None = None,
) -> BacktestMetrics:
    bt = Backtest(
        combined_df,
        strategy_class,
        cash=DEFAULT_CASH,
        commission=DEFAULT_COMMISSION,
        exclusive_orders=True,
    )
    stats = bt.run()

    notes: list[str] = []
    if available_range is not None:
        notes.append(f"data range used: {available_range[0]} to {available_range[1]}")

    total_trades = int(stats["# Trades"])
    equity_curve = stats["_equity_curve"]["Equity"].tolist()

    if total_trades == 0:
        notes.append(
            "zero trades generated over the backtest period — treated as a failed "
            "backtest, not a profitable one"
        )
        return BacktestMetrics(
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            expectancy=0.0,
            max_drawdown=0.0,
            equity_curve=equity_curve,
            notes=notes,
        )

    trades = stats["_trades"]
    directions = set(trades["Size"] > 0)
    if len(directions) == 1:
        notes.append(f"all trades were {'long' if True in directions else 'short'}-only")

    profit_factor = float(stats["Profit Factor"]) if pd.notna(stats["Profit Factor"]) else 0.0

    return BacktestMetrics(
        total_trades=total_trades,
        win_rate=float(stats["Win Rate [%]"]) / 100.0,
        profit_factor=profit_factor,
        expectancy=float(trades["ReturnPct"].mean()),
        max_drawdown=abs(float(stats["Max. Drawdown [%]"])) / 100.0,
        equity_curve=equity_curve,
        notes=notes,
    )
