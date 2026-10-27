import pandas as pd
import pytest

from tools import indicators as ind
from tools.schemas import (
    Direction,
    Indicator,
    Pair,
    PrimitiveType,
    RiskLevel,
    Session,
    StrategyInputs,
    TimeframeProfile,
)
from tools.strategy_linter import lint
from tools.strategy_rules_engine import RISK_PARAMS, StrategyCompositionError, compose_strategy


def _inputs(**overrides):
    defaults = dict(
        pair=Pair.BTC_USDT,
        timeframe_profile=TimeframeProfile.DAILY,
        indicators=[Indicator.EMA],
        risk_level=RiskLevel.MEDIUM,
    )
    defaults.update(overrides)
    return StrategyInputs(**defaults)


def test_direction_defaults_to_long():
    spec = compose_strategy(_inputs())
    assert spec.inputs.direction == Direction.LONG
    assert all(r.direction == Direction.LONG for r in spec.entry_rules + spec.confirmation_rules)


def test_short_rules_carry_short_direction_and_distinct_columns():
    long_spec = compose_strategy(_inputs(indicators=[Indicator.EMA, Indicator.ADX]))
    short_spec = compose_strategy(_inputs(indicators=[Indicator.EMA, Indicator.ADX], direction=Direction.SHORT))
    assert all(r.direction == Direction.SHORT for r in short_spec.entry_rules + short_spec.confirmation_rules)
    assert all(r.signal_column.endswith("_short") for r in short_spec.entry_rules)
    assert {r.signal_column for r in long_spec.entry_rules}.isdisjoint(
        {r.signal_column for r in short_spec.entry_rules}
    )
    assert lint(short_spec).passed


@pytest.mark.parametrize("risk", list(RiskLevel))
def test_short_rsi_entry_uses_the_mirrored_overbought_level(risk):
    spec = compose_strategy(_inputs(indicators=[Indicator.RSI], risk_level=risk, direction=Direction.SHORT))
    entry = spec.entry_rules[0]
    assert entry.primitive_type == PrimitiveType.RSI_CROSS_BELOW
    assert entry.params["threshold"] == 100 - RISK_PARAMS[risk]["rsi_oversold"]


def test_position_size_grows_with_risk_level():
    sizes = [compose_strategy(_inputs(risk_level=r)).position_size for r in RiskLevel]
    assert sizes == sorted(sizes)
    assert all(0 < s < 1 for s in sizes)


def test_vwap_is_rejected_on_swing_bars():
    with pytest.raises(StrategyCompositionError, match="VWAP"):
        compose_strategy(_inputs(timeframe_profile=TimeframeProfile.SWING, indicators=[Indicator.VWAP]))


@pytest.mark.parametrize("pair", [Pair.SP500, Pair.NASDAQ, Pair.GOLD])
def test_us_etf_pairs_reject_the_asia_session(pair):
    with pytest.raises(StrategyCompositionError, match="Asia"):
        compose_strategy(_inputs(pair=pair, timeframe_profile=TimeframeProfile.SCALPING, session=Session.ASIA))


def test_linter_flags_a_rule_on_the_wrong_side():
    spec = compose_strategy(_inputs())
    flipped = spec.entry_rules[0].model_copy(update={"direction": Direction.SHORT})
    result = lint(spec.model_copy(update={"entry_rules": [flipped]}))
    assert not result.passed
    assert any("strategy trades long" in v for v in result.violations)


@pytest.mark.parametrize("size", [0.0, 1.0, 1.5])
def test_linter_flags_position_size_outside_unit_interval(size):
    spec = compose_strategy(_inputs()).model_copy(update={"position_size": size})
    assert any("position size" in v for v in lint(spec).violations)


def test_short_signals_mirror_long_signals():
    closes = [10.0] * 30 + [11.0, 12.0, 13.0, 14.0, 15.0] + [14.0, 12.0, 10.0, 8.0, 6.0, 4.0]
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="1h", tz="UTC")
    df = pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes, "Volume": 1.0}, index=idx)

    up = ind._ema_cross_above(df, 3, 6)
    down = ind._ema_cross_below(df, 3, 6)
    assert up.sum() == 1 and down.sum() == 1
    assert up.idxmax() < down.idxmax()
    assert not (ind._ema_bias_bullish(df, 5) & ind._ema_bias_bearish(df, 5)).any()
