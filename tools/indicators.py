"""Hand-rolled indicator math and per-rule signal computation.

No TA-Lib (C-library install friction on Windows), no pandas-ta dependency — every
formula here is plain pandas/numpy, fully auditable, matching the project's "no hidden
logic" requirement (see CLAUDE.md and the approved implementation plan).

compute_indicators() turns a StrategySpec's primitive rules into boolean signal columns
(named via PrimitiveRule.signal_column) on the execution-timeframe dataframe, merges in
confirmation-timeframe rules via a shift-then-forward-fill that only exposes a
confirmation bar's value once it has actually closed (look-ahead-safe by construction —
see _merge_confirmation), and always adds a raw ATR column plus a session-filter column
when the strategy requires one.
"""

import numpy as np
import pandas as pd

from tools.schemas import (
    ATR_COLUMN,
    SESSION_COLUMN,
    TIMEFRAME_DURATION,
    TIMEFRAME_PROFILE_MAP,
    PrimitiveRule,
    PrimitiveType,
    RuleTimeframe,
    Session,
    StrategySpec,
)

RSI_PERIOD = 14
ATR_PERIOD = 14
ADX_PERIOD = 14
VOLUME_SPIKE_LOOKBACK = 20

# Standard UTC session windows (start inclusive, end exclusive) — locked in during planning.
SESSION_WINDOWS_UTC: dict[Session, tuple[int, int]] = {
    Session.ASIA: (0, 8),
    Session.LONDON: (8, 16),
    Session.NY_AM: (13, 16),
    Session.NY_PM: (16, 21),
}


def compute_indicators(exec_df: pd.DataFrame, confirm_df: pd.DataFrame, spec: StrategySpec) -> pd.DataFrame:
    result = exec_df.copy()
    result[ATR_COLUMN] = _atr(exec_df, ATR_PERIOD)

    confirm_timeframe = TIMEFRAME_PROFILE_MAP[spec.inputs.timeframe_profile][1]
    for rule in list(spec.entry_rules) + list(spec.confirmation_rules):
        if rule.timeframe == RuleTimeframe.EXECUTION:
            signal = _compute_signal(exec_df, rule).reindex(exec_df.index).fillna(False).astype(bool)
        else:
            raw_signal = _compute_signal(confirm_df, rule)
            signal = _merge_confirmation(exec_df.index, raw_signal, confirm_timeframe)
        result[rule.signal_column] = signal

    if spec.session_filter is not None:
        result[SESSION_COLUMN] = _session_filter(exec_df, spec.session_filter)

    return result


def _compute_signal(df: pd.DataFrame, rule: PrimitiveRule) -> pd.Series:
    p = rule.params
    dispatch = {
        PrimitiveType.EMA_CROSS: lambda: _ema_cross_above(df, p["fast_period"], p["slow_period"]),
        PrimitiveType.EMA_BIAS: lambda: _ema_bias_bullish(df, p["period"]),
        PrimitiveType.VWAP_CROSS: lambda: _vwap_cross_above(df),
        PrimitiveType.VWAP_BIAS: lambda: _vwap_bias_bullish(df),
        PrimitiveType.RSI_CROSS_ABOVE: lambda: _rsi_cross_above(df, p["threshold"]),
        PrimitiveType.RSI_CROSS_BELOW: lambda: _rsi_cross_below(df, p["threshold"]),
        PrimitiveType.RSI_BIAS: lambda: _rsi(df["Close"]) > p["midline"],
        PrimitiveType.ADX_TREND_FILTER: lambda: _adx(df, ADX_PERIOD) > p["threshold"],
        PrimitiveType.VOLUME_SPIKE_CONFIRMATION: lambda: _volume_spike(df, p["multiple"]),
        PrimitiveType.VOLUME_PROFILE_NEAR_NODE: lambda: _volume_profile_near_node(
            df, p["bin_count"], p["lookback_bars"], p["node_distance_pct"]
        ),
    }
    if rule.primitive_type not in dispatch:
        raise ValueError(f"no indicator implementation for primitive_type '{rule.primitive_type}'")
    return dispatch[rule.primitive_type]()


def _merge_confirmation(exec_index: pd.DatetimeIndex, confirm_series: pd.Series, confirm_timeframe: str) -> pd.Series:
    """Shift confirm-TF values forward by one bar duration — so a confirm bar's value only
    becomes visible to exec-TF rows once that bar has actually closed — then forward-fill
    onto the execution index."""
    offset = TIMEFRAME_DURATION[confirm_timeframe]
    shifted = confirm_series.copy()
    shifted.index = shifted.index + offset
    combined_index = exec_index.union(shifted.index)
    aligned = shifted.reindex(combined_index).sort_index().ffill()
    return aligned.reindex(exec_index).fillna(False).astype(bool)


def _session_filter(df: pd.DataFrame, session: Session) -> pd.Series:
    start_hour, end_hour = SESSION_WINDOWS_UTC[session]
    hours = df.index.tz_convert("UTC").hour
    return pd.Series((hours >= start_hour) & (hours < end_hour), index=df.index)


# --- Raw indicator math -------------------------------------------------------------


def _ema(series: pd.Series, period: float) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=int(period)).mean()


def _rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)


def _atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    tr = _true_range(df)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _adx(df: pd.DataFrame, period: int = ADX_PERIOD) -> pd.Series:
    high, low = df["High"], df["Low"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)

    atr = _atr(df, period)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def _vwap(df: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP: resets at the start of each UTC calendar day."""
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    tpv = typical_price * df["Volume"]
    day = df.index.tz_convert("UTC").normalize()
    cum_tpv = tpv.groupby(day).cumsum()
    cum_vol = df["Volume"].groupby(day).cumsum()
    return cum_tpv / cum_vol


def _volume_spike(df: pd.DataFrame, multiple: float, lookback: int = VOLUME_SPIKE_LOOKBACK) -> pd.Series:
    avg_volume = df["Volume"].rolling(window=lookback, min_periods=lookback).mean()
    return df["Volume"] > (avg_volume * multiple)


def _volume_profile_near_node(df: pd.DataFrame, bin_count: float, lookback_bars: float, node_distance_pct: float) -> pd.Series:
    """Rolling volume-profile point-of-control proximity check. For each bar, builds a
    price-binned volume histogram over the trailing `lookback_bars` window (inclusive of
    the current bar — no future data used) and flags whether the bar's close is within
    `node_distance_pct` percent of the highest-volume bin's midpoint."""
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    volume = df["Volume"].to_numpy()
    n = len(df)
    bins = int(bin_count)
    window = int(lookback_bars)
    result = np.zeros(n, dtype=bool)

    for i in range(n):
        start = max(0, i - window + 1)
        window_low = low[start : i + 1].min()
        window_high = high[start : i + 1].max()
        if window_high <= window_low:
            continue
        bin_edges = np.linspace(window_low, window_high, bins + 1)
        bin_idx = np.clip(np.digitize(close[start : i + 1], bin_edges) - 1, 0, bins - 1)
        vol_per_bin = np.zeros(bins)
        np.add.at(vol_per_bin, bin_idx, volume[start : i + 1])
        node_bin = vol_per_bin.argmax()
        node_price = (bin_edges[node_bin] + bin_edges[node_bin + 1]) / 2
        if node_price == 0:
            continue
        distance_pct = abs(close[i] - node_price) / node_price * 100
        result[i] = distance_pct <= node_distance_pct

    return pd.Series(result, index=df.index)


# --- Entry-primitive signals (execution timeframe) -----------------------------------


def _ema_cross_above(df: pd.DataFrame, fast_period: float, slow_period: float) -> pd.Series:
    fast = _ema(df["Close"], fast_period)
    slow = _ema(df["Close"], slow_period)
    return (fast > slow) & (fast.shift(1) <= slow.shift(1))


def _vwap_cross_above(df: pd.DataFrame) -> pd.Series:
    vwap = _vwap(df)
    close = df["Close"]
    return (close > vwap) & (close.shift(1) <= vwap.shift(1))


def _rsi_cross_above(df: pd.DataFrame, threshold: float) -> pd.Series:
    rsi = _rsi(df["Close"])
    return (rsi > threshold) & (rsi.shift(1) <= threshold)


def _rsi_cross_below(df: pd.DataFrame, threshold: float) -> pd.Series:
    rsi = _rsi(df["Close"])
    return (rsi < threshold) & (rsi.shift(1) >= threshold)


# --- Confirmation-primitive signals (bias, evaluated wherever they're dispatched) ----


def _ema_bias_bullish(df: pd.DataFrame, period: float) -> pd.Series:
    ema = _ema(df["Close"], period)
    return df["Close"] > ema


def _vwap_bias_bullish(df: pd.DataFrame) -> pd.Series:
    return df["Close"] > _vwap(df)
