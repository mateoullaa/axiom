from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import tools.fetch_market_data as fmd
from tools.schemas import Pair


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(fmd, "CACHE_DIR", tmp_path)
    yield tmp_path


def _bars(start: datetime, n: int, freq: str = "1h") -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(n)],
            "High": [101.0 + i for i in range(n)],
            "Low": [99.0 + i for i in range(n)],
            "Close": [100.5 + i for i in range(n)],
            "Volume": [10.0 + i for i in range(n)],
        },
        index=idx,
    )


def test_first_call_writes_cache(monkeypatch):
    fresh_bars = _bars(datetime.now(timezone.utc) - timedelta(hours=5), 5)
    monkeypatch.setattr(fmd, "_fetch_from_source", lambda pair, tf, since: fresh_bars)

    df = fmd.fetch_ohlcv(Pair.BTC_USDT, "1h", lookback_days=1)

    assert len(df) == 5
    assert fmd._cache_path(Pair.BTC_USDT, "1h").exists()


def test_fresh_cache_makes_zero_network_calls(monkeypatch):
    fresh_bars = _bars(datetime.now(timezone.utc) - timedelta(hours=2), 3)
    monkeypatch.setattr(fmd, "_fetch_from_source", lambda pair, tf, since: fresh_bars)
    fmd.fetch_ohlcv(Pair.BTC_USDT, "1h", lookback_days=1)

    def _explode(*args, **kwargs):
        raise AssertionError("_fetch_from_source should not be called for a fresh cache")

    monkeypatch.setattr(fmd, "_fetch_from_source", _explode)
    df = fmd.fetch_ohlcv(Pair.BTC_USDT, "1h", lookback_days=1)
    assert len(df) == 3


def test_stale_cache_fetches_only_delta_and_appends(monkeypatch):
    old_bars = _bars(datetime.now(timezone.utc) - timedelta(hours=10), 3)
    fmd._save_cache(Pair.BTC_USDT, "1h", old_bars)

    calls = []

    def _delta(pair, tf, since):
        calls.append(since)
        return _bars(since + timedelta(hours=1), 2)

    monkeypatch.setattr(fmd, "_fetch_from_source", _delta)
    df = fmd.fetch_ohlcv(Pair.BTC_USDT, "1h", lookback_days=1)

    assert calls == [old_bars.index[-1]]
    assert len(df) == 5
    assert df.index.is_monotonic_increasing
    assert not df.index.duplicated().any()


def test_resample_4h_from_1h_for_non_btc_pair(monkeypatch):
    hourly = _bars(datetime(2024, 1, 1, tzinfo=timezone.utc), 8, freq="1h")
    monkeypatch.setattr(fmd, "_fetch_from_source", lambda pair, tf, since: hourly)

    df = fmd.fetch_ohlcv(Pair.SP500, "4h", lookback_days=1)

    assert len(df) == 2
    first_bucket = hourly.iloc[0:4]
    assert df.iloc[0]["Open"] == first_bucket.iloc[0]["Open"]
    assert df.iloc[0]["High"] == first_bucket["High"].max()
    assert df.iloc[0]["Low"] == first_bucket["Low"].min()
    assert df.iloc[0]["Close"] == first_bucket.iloc[-1]["Close"]
    assert df.iloc[0]["Volume"] == first_bucket["Volume"].sum()
    assert not fmd._cache_path(Pair.SP500, "4h").exists()  # 4h is never cached directly


def test_unsupported_timeframe_raises():
    with pytest.raises(fmd.DataFetchError):
        fmd.fetch_ohlcv(Pair.BTC_USDT, "3m", lookback_days=1)


def test_get_available_range():
    bars = _bars(datetime(2024, 1, 1, tzinfo=timezone.utc), 4, freq="1D")
    start, end = fmd.get_available_range(bars)
    assert start == bars.index[0].isoformat()
    assert end == bars.index[-1].isoformat()


@pytest.mark.integration
def test_real_binance_fetch():
    df = fmd.fetch_ohlcv(Pair.BTC_USDT, "1h", lookback_days=2)
    assert not df.empty
    assert list(df.columns) == fmd.OHLCV_COLUMNS
