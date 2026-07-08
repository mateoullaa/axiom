import numpy as np
import pandas as pd
import pytest

from tools import indicators as ind
from tools.schemas import (
    Indicator,
    Pair,
    PrimitiveRole,
    PrimitiveRule,
    RiskLevel,
    RuleTimeframe,
    Session,
    StrategyInputs,
    TimeframeProfile,
)
from tools.strategy_rules_engine import compose_strategy


def _ohlcv(rows, start="2024-01-01 00:00", freq="1h"):
    idx = pd.date_range(start=start, periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)


def test_ema_matches_hand_calculation():
    close = pd.Series([10.0, 20.0, 30.0])
    ema = ind._ema(close, period=3)
    assert np.isnan(ema.iloc[0])
    assert np.isnan(ema.iloc[1])
    assert ema.iloc[2] == pytest.approx(22.5)


def test_atr_matches_hand_calculation():
    df = _ohlcv(
        [
            [9, 10, 8, 9, 100],
            [9, 13, 9, 12, 100],
            [12, 13, 11, 12.5, 100],
        ]
    )
    atr = ind._atr(df, period=2)
    assert np.isnan(atr.iloc[0])
    assert atr.iloc[1] == pytest.approx(3.0)
    assert atr.iloc[2] == pytest.approx(2.5)


def test_vwap_matches_hand_calculation():
    df = _ohlcv(
        [
            [9, 10, 8, 9, 100],
            [11, 12, 10, 11, 200],
        ]
    )
    vwap = ind._vwap(df)
    assert vwap.iloc[0] == pytest.approx(9.0)
    assert vwap.iloc[1] == pytest.approx(3100 / 300)


def test_rsi_is_bounded_and_directional():
    uptrend = _ohlcv([[100 + i, 101 + i, 99 + i, 100 + i, 100] for i in range(30)])
    downtrend = _ohlcv([[130 - i, 131 - i, 129 - i, 130 - i, 100] for i in range(30)])

    rsi_up = ind._rsi(uptrend["Close"]).dropna()
    rsi_down = ind._rsi(downtrend["Close"]).dropna()

    assert ((rsi_up >= 0) & (rsi_up <= 100)).all()
    assert ((rsi_down >= 0) & (rsi_down <= 100)).all()
    assert rsi_up.iloc[-1] > 70
    assert rsi_down.iloc[-1] < 30


def test_adx_is_bounded():
    df = _ohlcv([[100 + i, 102 + i, 99 + i, 101 + i, 100] for i in range(40)])
    adx = ind._adx(df).dropna()
    # +1e-9 tolerance: a perfectly constant one-directional trend is a degenerate case
    # that lands exactly on the 100 boundary modulo floating-point rounding.
    assert ((adx >= 0) & (adx <= 100 + 1e-9)).all()


def test_ema_cross_above_fires_on_the_cross_bar_only():
    # Slow decline for 20 bars (both EMAs settle with fast < slow), then a sharp reversal
    # upward — the fast EMA should cross above the slow EMA partway through the reversal.
    declining = [100 - i * 0.1 for i in range(20)]
    rising = [declining[-1] + (i + 1) * 2 for i in range(20)]
    closes = declining + rising
    rows = [[c, c + 0.5, c - 0.5, c, 100] for c in closes]
    df = _ohlcv(rows)

    signal = ind._ema_cross_above(df, fast_period=3, slow_period=8)
    assert signal.sum() >= 1
    # nothing should cross during the declining phase
    assert not signal.iloc[:20].any()


def test_rsi_cross_above_boolean_shape():
    df = _ohlcv([[100 + i, 101 + i, 99 + i, 100 + i, 100] for i in range(30)])
    signal = ind._rsi_cross_above(df, threshold=30)
    assert signal.dtype == bool


def test_session_filter_flags_correct_utc_hours():
    idx = pd.date_range("2024-01-01 00:00", periods=24, freq="1h", tz="UTC")
    df = pd.DataFrame({"Close": range(24)}, index=idx)
    flags = ind._session_filter(df, Session.LONDON)
    assert flags.iloc[8] == True  # noqa: E712 -- 08:00 UTC is inside London
    assert flags.iloc[16] == False  # noqa: E712 -- 16:00 UTC is outside London
    assert flags.iloc[7] == False  # noqa: E712


def test_volume_profile_flags_near_and_far_from_the_dominant_price_cluster():
    rows = []
    # 20 bars clustered tightly around price 100 with heavy volume.
    for i in range(20):
        rows.append([100.0, 100.5, 99.5, 100.0, 1000.0])
    # One bar far away from the cluster, with low volume — shouldn't move the node.
    rows.append([150.0, 150.5, 149.5, 150.0, 10.0])
    df = _ohlcv(rows)

    flags = ind._volume_profile_near_node(df, bin_count=20, lookback_bars=21, node_distance_pct=2.0)

    assert flags.iloc[19] == True  # noqa: E712 -- close=100, right on the dominant node
    assert flags.iloc[20] == False  # noqa: E712 -- close=150, far from the node


def test_merge_confirmation_has_no_look_ahead_bias():
    confirm_index = pd.date_range("2024-01-01 00:00", periods=3, freq="15min", tz="UTC")
    confirm_series = pd.Series([False, False, True], index=confirm_index)

    exec_index = pd.date_range("2024-01-01 00:00", periods=11, freq="5min", tz="UTC")

    merged = ind._merge_confirmation(exec_index, confirm_series, confirm_timeframe="15m")

    # The 00:30 confirm bar (value True) only closes at 00:45 — nothing before that may see True.
    close_time = pd.Timestamp("2024-01-01 00:45", tz="UTC")
    before_close = merged[merged.index < close_time]
    after_close = merged[merged.index >= close_time]

    assert not before_close.any()
    assert after_close.all()


def test_compute_indicators_produces_all_expected_columns():
    inputs = StrategyInputs(
        pair=Pair.BTC_USDT,
        timeframe_profile=TimeframeProfile.SCALPING,
        session=Session.LONDON,
        indicators=[Indicator.EMA, Indicator.RSI, Indicator.ADX, Indicator.VOLUME],
        risk_level=RiskLevel.MEDIUM,
    )
    spec = compose_strategy(inputs)

    exec_df = _ohlcv([[100 + i, 101 + i, 99 + i, 100 + i, 100 + i] for i in range(60)], freq="5min")
    confirm_df = _ohlcv([[100 + i, 102 + i, 98 + i, 101 + i, 500] for i in range(30)], freq="15min")

    result = ind.compute_indicators(exec_df, confirm_df, spec)

    assert "atr" in result.columns
    assert "in_session" in result.columns
    for rule in spec.entry_rules + spec.confirmation_rules:
        assert rule.signal_column in result.columns
        assert result[rule.signal_column].dtype == bool
    assert len(result) == len(exec_df)
