"""FastAPI orchestration layer. Thin by design (see CLAUDE.md) — every real computation
happens in tools/; this module only wires the pipeline together and translates domain
errors (StrategyCompositionError, a failing lint) into 4xx responses instead of a
generic 500.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tools.backtest_runner import run_backtest
from tools.code_generator import generate_code
from tools.fetch_market_data import fetch_ohlcv, get_available_range
from tools.indicators import compute_indicators
from tools.schemas import TIMEFRAME_PROFILE_MAP, BacktestMetrics, StrategyInputs
from tools.strategy_linter import lint
from tools.strategy_rules_engine import StrategyCompositionError, compose_strategy

app = FastAPI(title="Strategy Creator API")


class StrategyResponse(BaseModel):
    strategy_sheet: dict
    code: str
    metrics: BacktestMetrics


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/strategy", response_model=StrategyResponse)
def create_strategy(inputs: StrategyInputs) -> StrategyResponse:
    try:
        spec = compose_strategy(inputs)
    except StrategyCompositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    lint_result = lint(spec)
    if not lint_result.passed:
        raise HTTPException(status_code=422, detail=lint_result.violations)

    code = generate_code(spec)

    exec_tf, confirm_tf = TIMEFRAME_PROFILE_MAP[inputs.timeframe_profile]
    exec_df = fetch_ohlcv(inputs.pair, exec_tf)
    confirm_df = fetch_ohlcv(inputs.pair, confirm_tf)
    combined = compute_indicators(exec_df, confirm_df, spec)

    namespace: dict = {}
    exec(compile(code, "<generated>", "exec"), namespace)
    strategy_class = namespace["GeneratedStrategy"]

    metrics = run_backtest(strategy_class, combined, available_range=get_available_range(exec_df))

    return StrategyResponse(strategy_sheet=spec.to_sheet(), code=code, metrics=metrics)
