from tools.schemas import (
    Indicator,
    Pair,
    PrimitiveType,
    RiskLevel,
    Session,
    StrategyInputs,
    TimeframeProfile,
)
from tools.strategy_linter import lint
from tools.strategy_rules_engine import compose_strategy


def _valid_spec(**overrides):
    defaults = dict(
        pair=Pair.BTC_USDT,
        timeframe_profile=TimeframeProfile.SCALPING,
        session=Session.LONDON,
        indicators=[Indicator.EMA, Indicator.RSI, Indicator.ADX, Indicator.VOLUME],
        risk_level=RiskLevel.MEDIUM,
    )
    defaults.update(overrides)
    return compose_strategy(StrategyInputs(**defaults))


def test_valid_spec_passes_clean():
    result = lint(_valid_spec())
    assert result.passed is True
    assert result.violations == []


def test_missing_confirmation_rule_fails():
    spec = _valid_spec()
    mutated = spec.model_copy(update={"confirmation_rules": []})
    result = lint(mutated)
    assert result.passed is False
    assert any("confirmation" in v for v in result.violations)


def test_scalping_missing_session_filter_fails():
    spec = _valid_spec()
    mutated = spec.model_copy(update={"session_filter": None})
    result = lint(mutated)
    assert result.passed is False
    assert any("session filter" in v for v in result.violations)


def test_non_scalping_with_session_filter_fails():
    spec = _valid_spec(timeframe_profile=TimeframeProfile.SWING, session=None)
    mutated = spec.model_copy(update={"session_filter": Session.ASIA})
    result = lint(mutated)
    assert result.passed is False
    assert any("session filter" in v for v in result.violations)


def test_sl_atr_multiple_zero_fails():
    spec = _valid_spec()
    mutated_sl = spec.sl_formula.model_copy(update={"atr_multiple": 0.0})
    mutated = spec.model_copy(update={"sl_formula": mutated_sl})
    result = lint(mutated)
    assert result.passed is False
    assert any("stop-loss" in v for v in result.violations)


def test_tp_atr_multiple_zero_fails():
    spec = _valid_spec()
    mutated_tp = spec.tp_formula.model_copy(update={"atr_multiple": 0.0})
    mutated = spec.model_copy(update={"tp_formula": mutated_tp})
    result = lint(mutated)
    assert result.passed is False
    assert any("take-profit" in v for v in result.violations)


def test_out_of_catalog_primitive_for_indicator_fails():
    spec = _valid_spec()
    bad_rule = spec.entry_rules[0].model_copy(update={"primitive_type": PrimitiveType.VOLUME_SPIKE_CONFIRMATION})
    mutated = spec.model_copy(update={"entry_rules": [bad_rule]})
    result = lint(mutated)
    assert result.passed is False
    assert any("closed catalog" in v for v in result.violations)


def test_missing_required_param_fails():
    spec = _valid_spec()
    bad_rule = spec.entry_rules[0].model_copy(update={"params": {}})
    mutated = spec.model_copy(update={"entry_rules": [bad_rule]})
    result = lint(mutated)
    assert result.passed is False
    assert any("missing required param" in v for v in result.violations)


def test_returns_all_violations_not_just_first():
    spec = _valid_spec()
    mutated = spec.model_copy(
        update={
            "confirmation_rules": [],
            "session_filter": None,
            "sl_formula": spec.sl_formula.model_copy(update={"atr_multiple": 0.0}),
        }
    )
    result = lint(mutated)
    assert result.passed is False
    assert len(result.violations) >= 3
