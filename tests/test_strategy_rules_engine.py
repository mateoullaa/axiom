import pytest

from tools.schemas import Indicator, Pair, RiskLevel, RuleTimeframe, Session, StrategyInputs, TimeframeProfile
from tools.strategy_rules_engine import StrategyCompositionError, compose_strategy


def _inputs(**overrides):
    defaults = dict(
        pair=Pair.BTC_USDT,
        timeframe_profile=TimeframeProfile.DAILY,
        indicators=[Indicator.EMA, Indicator.ATR],
        risk_level=RiskLevel.MEDIUM,
    )
    defaults.update(overrides)
    return StrategyInputs(**defaults)


@pytest.mark.parametrize(
    "profile,session",
    [
        (TimeframeProfile.SCALPING, Session.LONDON),
        (TimeframeProfile.DAILY, None),
        (TimeframeProfile.SWING, None),
    ],
)
def test_valid_combo_per_timeframe_profile(profile, session):
    spec = compose_strategy(_inputs(timeframe_profile=profile, session=session))
    assert len(spec.entry_rules) >= 1
    assert len(spec.confirmation_rules) >= 1
    assert spec.sl_formula.atr_multiple > 0
    assert spec.tp_formula.atr_multiple > 0
    if profile == TimeframeProfile.SCALPING:
        assert spec.session_filter == session
    else:
        assert spec.session_filter is None


def test_volume_only_raises():
    with pytest.raises(StrategyCompositionError):
        compose_strategy(_inputs(indicators=[Indicator.VOLUME]))


def test_atr_only_raises():
    with pytest.raises(StrategyCompositionError):
        compose_strategy(_inputs(indicators=[Indicator.ATR]))


def test_volume_profile_only_raises():
    with pytest.raises(StrategyCompositionError):
        compose_strategy(_inputs(indicators=[Indicator.VOLUME_PROFILE]))


def test_adx_only_raises_no_entry_primitive():
    with pytest.raises(StrategyCompositionError):
        compose_strategy(_inputs(indicators=[Indicator.ADX]))


def test_scalping_without_session_raises():
    with pytest.raises(StrategyCompositionError):
        compose_strategy(
            _inputs(timeframe_profile=TimeframeProfile.SCALPING, session=None)
        )


def test_non_scalping_with_session_raises():
    with pytest.raises(StrategyCompositionError):
        compose_strategy(
            _inputs(timeframe_profile=TimeframeProfile.SWING, session=Session.ASIA)
        )


def test_numeric_params_are_never_none():
    spec = compose_strategy(_inputs())
    for rule in spec.entry_rules + spec.confirmation_rules:
        for value in rule.params.values():
            assert value is not None
            assert isinstance(value, float)


def test_deterministic_same_input_same_output():
    inputs = _inputs(indicators=[Indicator.EMA, Indicator.RSI, Indicator.ADX, Indicator.VOLUME])
    spec_a = compose_strategy(inputs)
    spec_b = compose_strategy(inputs)
    assert spec_a == spec_b


def test_volume_supplements_but_does_not_replace_confirmation_requirement():
    spec = compose_strategy(_inputs(indicators=[Indicator.EMA, Indicator.VOLUME]))
    timeframes = [r.timeframe for r in spec.confirmation_rules]
    assert RuleTimeframe.CONFIRMATION in timeframes
    assert RuleTimeframe.EXECUTION in timeframes


def test_risk_level_changes_sl_tp_multiples():
    conservative = compose_strategy(_inputs(risk_level=RiskLevel.CONSERVATIVE))
    aggressive = compose_strategy(_inputs(risk_level=RiskLevel.AGGRESSIVE))
    assert conservative.sl_formula.atr_multiple < aggressive.sl_formula.atr_multiple
    assert conservative.tp_formula.atr_multiple < aggressive.tp_formula.atr_multiple
