import pytest
from fastapi.testclient import TestClient

from backend.main import app
from tools.schemas import Indicator, Pair, RiskLevel, TimeframeProfile

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_scalping_without_session_returns_4xx_with_specific_message():
    payload = {
        "pair": Pair.BTC_USDT.value,
        "timeframe_profile": TimeframeProfile.SCALPING.value,
        "indicators": [Indicator.EMA.value],
        "risk_level": RiskLevel.MEDIUM.value,
    }
    resp = client.post("/api/strategy", json=payload)
    assert 400 <= resp.status_code < 500
    assert "session" in resp.json()["detail"].lower()


def test_volume_only_returns_4xx_not_500():
    payload = {
        "pair": Pair.BTC_USDT.value,
        "timeframe_profile": TimeframeProfile.DAILY.value,
        "indicators": [Indicator.VOLUME.value],
        "risk_level": RiskLevel.MEDIUM.value,
    }
    resp = client.post("/api/strategy", json=payload)
    assert 400 <= resp.status_code < 500
    assert "entry primitive" in resp.json()["detail"].lower()


@pytest.mark.integration
def test_calibrated_combo_returns_full_populated_response():
    payload = {
        "pair": Pair.BTC_USDT.value,
        "timeframe_profile": TimeframeProfile.SWING.value,
        "indicators": [Indicator.EMA.value],
        "risk_level": RiskLevel.MEDIUM.value,
    }
    resp = client.post("/api/strategy", json=payload)
    assert resp.status_code == 200

    body = resp.json()
    assert body["strategy_sheet"]["pair"] == "BTC/USDT"
    assert "GeneratedStrategy" in body["code"]
    assert body["metrics"]["profit_factor"] > 1
    assert body["metrics"]["expectancy"] > 0
