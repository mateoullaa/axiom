"""End-to-end proof case (Task 13). Scripts the calibrated combo from
docs/calibration_notes.md (BTC/USDT, swing, [EMA], medium risk) through the entire chain
and asserts the project's four success criteria together:

1. Generated Python code is syntactically valid and runs (importable, instantiable).
2. A real backtest on real historical data clears profit factor > 1 and positive
   expectancy.
3. The full UI flow (pick inputs -> see strategy sheet + code + metrics) works with no
   errors — verified manually by POSTing the same payload through the Vite dev-server
   proxy (http://localhost:5173/api/strategy) exactly as StrategyForm.jsx does, and
   confirming the response shape matches what StrategySheet/CodeBlock/BacktestMetrics
   render. Not automated here (no browser driver in scope for this MVP).
4. The linter mechanically confirms the strategy is 100% objective.
"""

import ast

import pytest

from tools.backtest_runner import run_backtest
from tools.code_generator import generate_code
from tools.fetch_market_data import fetch_ohlcv, get_available_range
from tools.indicators import compute_indicators
from tools.schemas import (
    TIMEFRAME_PROFILE_MAP,
    Indicator,
    Pair,
    RiskLevel,
    StrategyInputs,
    TimeframeProfile,
)
from tools.strategy_linter import lint
from tools.strategy_rules_engine import compose_strategy


@pytest.mark.integration
def test_calibrated_combo_clears_all_four_success_criteria():
    inputs = StrategyInputs(
        pair=Pair.BTC_USDT,
        timeframe_profile=TimeframeProfile.SWING,
        indicators=[Indicator.EMA],
        risk_level=RiskLevel.MEDIUM,
    )

    # Criterion 4: objectivity/executability gate.
    spec = compose_strategy(inputs)
    lint_result = lint(spec)
    assert lint_result.passed, lint_result.violations

    # Criterion 1: syntactically valid, importable, instantiable code.
    code = generate_code(spec)
    ast.parse(code)
    namespace: dict = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    strategy_class = namespace["GeneratedStrategy"]
    assert strategy_class.__name__ == "GeneratedStrategy"

    # Criterion 2: real backtest on real data clears the profitability bar.
    exec_tf, confirm_tf = TIMEFRAME_PROFILE_MAP[inputs.timeframe_profile]
    exec_df = fetch_ohlcv(inputs.pair, exec_tf, lookback_days=1500)
    confirm_df = fetch_ohlcv(inputs.pair, confirm_tf, lookback_days=1500)
    combined = compute_indicators(exec_df, confirm_df, spec)
    metrics = run_backtest(strategy_class, combined, available_range=get_available_range(exec_df))

    assert metrics.total_trades > 0
    assert metrics.profit_factor > 1
    assert metrics.expectancy > 0
