import numpy as np
import pandas as pd
from backtesting import Strategy

from tools.backtest_runner import run_backtest
from tools.code_generator import generate_code
from tools.indicators import compute_indicators
from tools.schemas import BacktestMetrics, Indicator, Pair, RiskLevel, StrategyInputs, TimeframeProfile
from tools.strategy_rules_engine import compose_strategy


def _ohlcv(closes, start, freq):
    idx = pd.date_range(start=start, periods=len(closes), freq=freq, tz="UTC")
    closes = np.asarray(closes)
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes + 0.5,
            "Low": closes - 0.5,
            "Close": closes,
            "Volume": 1000.0,
        },
        index=idx,
    )


def _random_walk(n, seed, start_price=100.0, scale=0.6):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, scale, n)
    return start_price + np.cumsum(steps)


def _exec_strategy_class(code: str, class_name: str = "GeneratedStrategy"):
    namespace: dict = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    return namespace[class_name]


def test_full_chain_produces_sane_metrics():
    inputs = StrategyInputs(
        pair=Pair.BTC_USDT,
        timeframe_profile=TimeframeProfile.DAILY,
        indicators=[Indicator.VWAP],
        risk_level=RiskLevel.MEDIUM,
    )
    spec = compose_strategy(inputs)
    code = generate_code(spec)
    strategy_class = _exec_strategy_class(code)

    exec_closes = _random_walk(400, seed=1)
    confirm_closes = _random_walk(100, seed=1)  # correlated seed keeps series roughly aligned
    exec_df = _ohlcv(exec_closes, "2024-01-01", "1h")
    confirm_df = _ohlcv(confirm_closes, "2024-01-01", "4h")

    combined = compute_indicators(exec_df, confirm_df, spec)
    metrics = run_backtest(strategy_class, combined, available_range=("2024-01-01", "2024-01-17"))

    assert isinstance(metrics, BacktestMetrics)
    assert metrics.total_trades >= 0
    assert 0.0 <= metrics.win_rate <= 1.0
    assert metrics.profit_factor >= 0.0
    assert metrics.max_drawdown >= 0.0
    assert len(metrics.equity_curve) > 0
    assert any("data range used" in n for n in metrics.notes)


def test_zero_trades_hits_explicit_edge_case_path():
    class NeverTrades(Strategy):
        def init(self):
            pass

        def next(self):
            pass  # never buys or sells

    idx = pd.date_range("2024-01-01", periods=50, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {"Open": 100.0, "High": 100.5, "Low": 99.5, "Close": 100.0, "Volume": 10.0},
        index=idx,
    )

    metrics = run_backtest(NeverTrades, df)

    assert metrics.total_trades == 0
    assert metrics.profit_factor == 0.0
    assert metrics.win_rate == 0.0
    assert metrics.max_drawdown == 0.0
    assert any("zero trades" in n for n in metrics.notes)
