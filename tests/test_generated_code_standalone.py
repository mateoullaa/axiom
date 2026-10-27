"""The exported .py must be standalone and must compute exactly what the app backtests."""

import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from tools.code_generator import generate_code
from tools.indicators import compute_indicators
from tools.schemas import Direction, Indicator, Pair, RiskLevel, Session, StrategyInputs, TimeframeProfile
from tools.strategy_rules_engine import compose_strategy


def _bars(n, freq, seed, start="2024-01-01"):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.8, n))
    spread = np.abs(rng.normal(0, 0.6, n)) + 0.1
    idx = pd.date_range(start=start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "Open": close + rng.normal(0, 0.2, n),
            "High": close + spread,
            "Low": close - spread,
            "Close": close,
            "Volume": rng.uniform(500, 1500, n),
        },
        index=idx,
    )


SPECS = [
    dict(timeframe_profile=TimeframeProfile.DAILY, indicators=[Indicator.EMA, Indicator.RSI, Indicator.ADX]),
    dict(
        timeframe_profile=TimeframeProfile.DAILY,
        indicators=[Indicator.VWAP, Indicator.VOLUME, Indicator.VOLUME_PROFILE],
        direction=Direction.SHORT,
    ),
    dict(timeframe_profile=TimeframeProfile.DAILY, indicators=[Indicator.RSI], direction=Direction.SHORT),
    dict(
        timeframe_profile=TimeframeProfile.SCALPING,
        session=Session.LONDON,
        indicators=[Indicator.EMA, Indicator.VWAP],
    ),
]
FREQS = {TimeframeProfile.DAILY: ("1h", "4h"), TimeframeProfile.SCALPING: ("5min", "15min")}


def _inputs(**overrides):
    defaults = dict(pair=Pair.BTC_USDT, risk_level=RiskLevel.MEDIUM)
    defaults.update(overrides)
    return StrategyInputs(**defaults)


def _load(code):
    namespace = {"__name__": "axiom_generated"}
    exec(compile(code, "<generated>", "exec"), namespace)
    return namespace


@pytest.mark.parametrize("spec_kwargs", SPECS)
def test_generated_compute_signals_matches_tools_indicators(spec_kwargs):
    spec = compose_strategy(_inputs(**spec_kwargs))
    exec_freq, confirm_freq = FREQS[spec.inputs.timeframe_profile]
    exec_df, confirm_df = _bars(600, exec_freq, seed=3), _bars(150, confirm_freq, seed=3)

    generated = _load(generate_code(spec))["compute_signals"](exec_df, confirm_df)
    reference = compute_indicators(exec_df, confirm_df, spec)

    pd.testing.assert_frame_equal(generated[reference.columns], reference)


def test_generated_file_runs_from_the_command_line(tmp_path):
    spec = compose_strategy(_inputs(**SPECS[0]))
    script = tmp_path / "strategy.py"
    script.write_text(generate_code(spec), encoding="utf-8")
    _bars(600, "1h", seed=5).to_csv(tmp_path / "exec.csv")
    _bars(150, "4h", seed=5).to_csv(tmp_path / "confirm.csv")

    # -I: isolated mode, so the script can't import anything from this repo.
    result = subprocess.run(
        [sys.executable, "-I", str(script), "exec.csv", "confirm.csv"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert "Return [%]" in result.stdout
    assert "from tools" not in script.read_text(encoding="utf-8")


def test_short_strategy_sells_with_mirrored_stops():
    code = generate_code(compose_strategy(_inputs(**SPECS[2])))
    assert "self.sell(size=self.position_size, sl=price + sl_distance, tp=price - tp_distance)" in code
    assert "self.buy(" not in code
