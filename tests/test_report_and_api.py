from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import backend.main as api
import tools.fetch_market_data as fmd
from tools.backtest_runner import MIN_OOS_TRADES, run_report
from tools.code_generator import generate_code
from tools.indicators import compute_indicators
from tools.schemas import Indicator, Pair, RiskLevel, SampleVerdict, StrategyInputs, TimeframeProfile
from tools.strategy_rules_engine import compose_strategy

client = TestClient(api.app)


def _bars(n, freq, seed, start="2024-01-01"):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.8, n))
    spread = np.abs(rng.normal(0, 0.6, n)) + 0.1
    idx = pd.date_range(start=start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {"Open": close, "High": close + spread, "Low": close - spread, "Close": close, "Volume": 1000.0},
        index=idx,
    )


def _spec():
    return compose_strategy(
        StrategyInputs(
            pair=Pair.BTC_USDT,
            timeframe_profile=TimeframeProfile.DAILY,
            indicators=[Indicator.EMA],
            risk_level=RiskLevel.MEDIUM,
        )
    )


def _strategy_class(spec):
    namespace = {"__name__": "axiom_generated"}
    exec(compile(generate_code(spec), "<generated>", "exec"), namespace)
    return namespace["GeneratedStrategy"]


def test_report_splits_chronologically_and_keeps_every_bar():
    spec = _spec()
    combined = compute_indicators(_bars(1200, "1h", 7), _bars(300, "4h", 7), spec)
    report = run_report(_strategy_class(spec), combined)

    assert len(report.bars) == len(combined)
    assert report.split_time == int(combined.index[int(len(combined) * 0.7)].timestamp())
    assert len(report.trades) == report.full.total_trades
    assert all(t.entry_time <= t.exit_time for t in report.trades)
    assert {t.exit_reason for t in report.trades} <= {"stop-loss", "take-profit", "end of data", "other"}


def test_too_few_out_of_sample_trades_is_inconclusive_not_a_pass():
    spec = _spec()
    combined = compute_indicators(_bars(300, "1h", 2), _bars(80, "4h", 2), spec)
    report = run_report(_strategy_class(spec), combined)
    if report.out_of_sample.total_trades < MIN_OOS_TRADES:
        assert report.oos_verdict == SampleVerdict.INCONCLUSIVE


def _payload(**overrides):
    payload = {
        "pair": "BTC/USDT",
        "timeframe_profile": "daily",
        "indicators": ["EMA", "RSI"],
        "risk_level": "medium",
        "direction": "short",
    }
    payload.update(overrides)
    return payload


def test_api_returns_full_report_on_synthetic_data(monkeypatch):
    data = {"1h": _bars(1200, "1h", 11), "4h": _bars(300, "4h", 11)}
    monkeypatch.setattr(api, "fetch_ohlcv", lambda pair, tf: data[tf])

    resp = client.post("/api/strategy", json=_payload())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["strategy_sheet"]["direction"] == "short"
    assert "def compute_signals" in body["code"]
    report = body["report"]
    assert set(report) >= {"full", "in_sample", "out_of_sample", "oos_verdict", "trades", "bars"}
    assert len(report["bars"]) == 1200


def test_market_data_failure_is_a_json_502(monkeypatch):
    def _fail(pair, tf):
        raise fmd.DataFetchError("simulated outage")

    monkeypatch.setattr(api, "fetch_ohlcv", _fail)
    resp = client.post("/api/strategy", json=_payload())
    assert resp.status_code == 502
    assert "simulated outage" in resp.json()["detail"]


def test_too_little_data_is_a_json_422(monkeypatch):
    monkeypatch.setattr(api, "fetch_ohlcv", lambda pair, tf: _bars(20, "1h", 1))
    resp = client.post("/api/strategy", json=_payload())
    assert resp.status_code == 422
    assert "bars available" in resp.json()["detail"]


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(fmd, "CACHE_DIR", tmp_path)


def test_short_cache_is_rebuilt_for_a_longer_window(isolated_cache, monkeypatch):
    now = datetime.now(timezone.utc)
    fmd._save_cache(Pair.BTC_USDT, "1d", _bars(10, "1D", 1, start=now - timedelta(days=10)))
    calls = []

    def _full(pair, tf, since):
        calls.append(since)
        return _bars(400, "1D", 1, start=since)

    monkeypatch.setattr(fmd, "_fetch_from_source", _full)
    df = fmd.fetch_ohlcv(Pair.BTC_USDT, "1d", lookback_days=400)

    assert len(calls) == 1 and calls[0] < now - timedelta(days=399)
    assert len(df) == 400


def test_default_lookback_respects_yfinance_intraday_limits():
    assert fmd.LOOKBACK_DAYS["5m"] < 60 and fmd.LOOKBACK_DAYS["15m"] < 60
    assert fmd.LOOKBACK_DAYS["1h"] < 730


def _metrics(trades, pf, exp):
    from tools.schemas import BacktestMetrics

    return BacktestMetrics(
        total_trades=trades, win_rate=0.5, profit_factor=pf, expectancy=exp, max_drawdown=0.1, equity_curve=[1.0]
    )


def test_oos_win_without_an_in_sample_edge_is_a_fail():
    from tools.backtest_runner import _oos_verdict

    verdict, reason = _oos_verdict(_metrics(10, 0.4, -0.03), _metrics(6, 1.1, 0.01))
    assert verdict == SampleVerdict.FAIL
    assert "in-sample" in reason


def test_edge_in_both_halves_passes():
    from tools.backtest_runner import _oos_verdict

    assert _oos_verdict(_metrics(10, 1.3, 0.01), _metrics(6, 1.1, 0.01))[0] == SampleVerdict.PASS
    assert _oos_verdict(_metrics(10, 1.3, 0.01), _metrics(6, 0.8, -0.01))[0] == SampleVerdict.FAIL


def test_source_with_less_history_than_requested_is_not_refetched_forever(isolated_cache, monkeypatch):
    now = datetime.now(timezone.utc)
    listing_date = now - timedelta(days=100)  # the source has nothing older than this
    calls = []

    def _source(pair, tf, since):
        calls.append(since)
        start = max(since, listing_date)
        return _bars(int((now - start).days), "1D", 1, start=start)

    monkeypatch.setattr(fmd, "_fetch_from_source", _source)
    fmd.fetch_ohlcv(Pair.BTC_USDT, "1d", lookback_days=400)
    fmd.fetch_ohlcv(Pair.BTC_USDT, "1d", lookback_days=400)

    assert len(calls) == 1
