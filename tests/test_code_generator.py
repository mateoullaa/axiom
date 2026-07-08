import ast

import pytest
from backtesting import Strategy

from tools.code_generator import UnlintedStrategyError, generate_code
from tools.schemas import Indicator, Pair, RiskLevel, Session, StrategyInputs, TimeframeProfile
from tools.strategy_rules_engine import compose_strategy


def _spec(**overrides):
    defaults = dict(
        pair=Pair.BTC_USDT,
        timeframe_profile=TimeframeProfile.DAILY,
        indicators=[Indicator.EMA, Indicator.RSI],
        risk_level=RiskLevel.MEDIUM,
    )
    defaults.update(overrides)
    return compose_strategy(StrategyInputs(**defaults))


def _exec_strategy_class(code: str, class_name: str = "GeneratedStrategy"):
    namespace: dict = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    return namespace[class_name]


@pytest.mark.parametrize(
    "spec_kwargs",
    [
        dict(timeframe_profile=TimeframeProfile.DAILY, indicators=[Indicator.EMA, Indicator.RSI]),
        dict(
            timeframe_profile=TimeframeProfile.SCALPING,
            session=Session.NY_AM,
            indicators=[Indicator.VWAP, Indicator.ADX, Indicator.VOLUME],
        ),
    ],
)
def test_generated_code_parses_and_defines_strategy_subclass(spec_kwargs):
    spec = _spec(**spec_kwargs)
    code = generate_code(spec)

    ast.parse(code)  # syntactic validity — ties to success criterion #1

    strategy_class = _exec_strategy_class(code)
    assert issubclass(strategy_class, Strategy)
    assert hasattr(strategy_class, "init")
    assert hasattr(strategy_class, "next")


def test_generated_code_references_all_signal_columns():
    spec = _spec(indicators=[Indicator.EMA, Indicator.RSI, Indicator.ADX])
    code = generate_code(spec)
    for rule in spec.entry_rules + spec.confirmation_rules:
        assert rule.signal_column in code


def test_scalping_code_references_session_column():
    spec = _spec(
        timeframe_profile=TimeframeProfile.SCALPING,
        session=Session.LONDON,
        indicators=[Indicator.EMA],
    )
    code = generate_code(spec)
    assert "self.data.in_session" in code


def test_non_scalping_code_does_not_reference_session_column():
    spec = _spec(timeframe_profile=TimeframeProfile.SWING, indicators=[Indicator.EMA])
    code = generate_code(spec)
    assert "self.data.in_session" not in code


def test_deterministic_same_spec_same_code():
    spec = _spec()
    assert generate_code(spec) == generate_code(spec)


def test_refuses_to_generate_for_failing_spec():
    spec = _spec()
    broken = spec.model_copy(update={"confirmation_rules": []})
    with pytest.raises(UnlintedStrategyError):
        generate_code(broken)
