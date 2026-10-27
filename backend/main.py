"""FastAPI orchestration layer. Thin by design (see CLAUDE.md) — every real computation
happens in tools/; this module only wires the pipeline together and translates domain
errors into JSON 4xx/5xx responses instead of a generic 500.

The backtest runs the generated module itself (its compute_signals() and Strategy
class), so the code the user downloads is exactly the code that produced the numbers.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tools.backtest_runner import run_report
from tools.code_generator import generate_code
from tools.fetch_market_data import DataFetchError, fetch_ohlcv, get_available_range
from tools.schemas import TIMEFRAME_PROFILE_MAP, BacktestReport, StrategyInputs
from tools.strategy_linter import lint
from tools.strategy_rules_engine import StrategyCompositionError, compose_strategy

app = FastAPI(title="Axiom API", description="Deterministic trading-strategy builder and backtester.")

# Fewer execution bars than this can't warm up the indicators and still leave a test period.
MIN_BARS = 100


class StrategyResponse(BaseModel):
    strategy_sheet: dict
    code: str
    report: BacktestReport


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
        raise HTTPException(status_code=422, detail="; ".join(lint_result.violations))

    code = generate_code(spec)

    exec_tf, confirm_tf = TIMEFRAME_PROFILE_MAP[inputs.timeframe_profile]
    try:
        exec_df = fetch_ohlcv(inputs.pair, exec_tf)
        confirm_df = fetch_ohlcv(inputs.pair, confirm_tf)
    except DataFetchError as exc:
        raise HTTPException(status_code=502, detail=f"market data unavailable: {exc}") from exc
    if len(exec_df) < MIN_BARS:
        raise HTTPException(
            status_code=422,
            detail=f"only {len(exec_df)} {exec_tf} bars available for {inputs.pair.value}; "
            f"at least {MIN_BARS} are needed for a meaningful backtest",
        )

    module = _load_generated(code)
    combined = module["compute_signals"](exec_df, confirm_df)
    report = run_report(module["GeneratedStrategy"], combined, available_range=get_available_range(exec_df))

    return StrategyResponse(strategy_sheet=spec.to_sheet(), code=code, report=report)


def _load_generated(code: str) -> dict:
    namespace: dict = {"__name__": "axiom_generated"}
    exec(compile(code, "<generated>", "exec"), namespace)
    return namespace
