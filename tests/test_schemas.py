import pytest
from pydantic import ValidationError

from tools.schemas import (
    BacktestMetrics,
    Indicator,
    LintResult,
    Pair,
    PrimitiveRole,
    PrimitiveRule,
    PrimitiveType,
    RiskComponent,
    RiskLevel,
    RuleTimeframe,
    Session,
    StrategyInputs,
    StrategySpec,
    TimeframeProfile,
)


def _valid_rule(role, primitive_type, timeframe):
    return PrimitiveRule(
        indicator=Indicator.EMA,
        role=role,
        primitive_type=primitive_type,
        timeframe=timeframe,
        params={"period": 20.0},
    )


def _valid_spec():
    return StrategySpec(
        inputs=StrategyInputs(
            pair=Pair.BTC_USDT,
            timeframe_profile=TimeframeProfile.SWING,
            indicators=[Indicator.EMA, Indicator.ATR],
            risk_level=RiskLevel.MEDIUM,
        ),
        entry_rules=[_valid_rule(PrimitiveRole.ENTRY, PrimitiveType.EMA_CROSS, RuleTimeframe.EXECUTION)],
        confirmation_rules=[_valid_rule(PrimitiveRole.CONFIRMATION, PrimitiveType.EMA_BIAS, RuleTimeframe.CONFIRMATION)],
        sl_formula=RiskComponent(atr_multiple=1.5),
        tp_formula=RiskComponent(atr_multiple=3.0),
    )


def test_valid_strategy_spec_constructs():
    spec = _valid_spec()
    sheet = spec.to_sheet()
    assert sheet["pair"] == "BTC/USDT"
    assert sheet["stop_loss"]["atr_multiple"] == 1.5
    assert sheet["take_profit"]["atr_multiple"] == 3.0


def test_strategy_spec_requires_sl():
    data = _valid_spec().model_dump()
    del data["sl_formula"]
    with pytest.raises(ValidationError):
        StrategySpec(**data)


def test_strategy_spec_requires_tp():
    data = _valid_spec().model_dump()
    del data["tp_formula"]
    with pytest.raises(ValidationError):
        StrategySpec(**data)


def test_strategy_spec_requires_at_least_one_entry_rule():
    data = _valid_spec().model_dump()
    data["entry_rules"] = []
    with pytest.raises(ValidationError):
        StrategySpec(**data)


def test_strategy_spec_requires_at_least_one_confirmation_rule():
    data = _valid_spec().model_dump()
    data["confirmation_rules"] = []
    with pytest.raises(ValidationError):
        StrategySpec(**data)


def test_out_of_catalog_primitive_type_rejected():
    with pytest.raises(ValidationError):
        PrimitiveRule(
            indicator=Indicator.RSI,
            role=PrimitiveRole.ENTRY,
            primitive_type="not_a_real_primitive",
            timeframe=RuleTimeframe.EXECUTION,
        )


def test_out_of_catalog_indicator_rejected():
    with pytest.raises(ValidationError):
        StrategyInputs(
            pair=Pair.BTC_USDT,
            timeframe_profile=TimeframeProfile.DAILY,
            indicators=["MACD"],
            risk_level=RiskLevel.CONSERVATIVE,
        )


def test_lint_result_and_backtest_metrics_construct():
    lint = LintResult(passed=False, violations=["missing TP"])
    assert lint.violations == ["missing TP"]

    metrics = BacktestMetrics(
        total_trades=10,
        win_rate=0.5,
        profit_factor=1.2,
        expectancy=0.01,
        max_drawdown=0.1,
        equity_curve=[1.0, 1.01, 1.02],
    )
    assert metrics.total_trades == 10
