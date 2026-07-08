"""Shared data contract for the strategy generation pipeline.

Every tool (rules engine, linter, code generator, backtest runner) and the FastAPI layer
import these models instead of inventing their own shapes. Enums are the mechanism that
makes the "closed catalog" architectural rule (see CLAUDE.md) machine-enforced: a
primitive_type or indicator that isn't in these enums cannot be constructed at all.
"""

from enum import Enum

import pandas as pd
from pydantic import BaseModel, Field


class Pair(str, Enum):
    BTC_USDT = "BTC/USDT"
    SP500 = "SP500"
    NASDAQ = "Nasdaq"
    GOLD = "Gold"


class TimeframeProfile(str, Enum):
    SCALPING = "scalping"
    DAILY = "daily"
    SWING = "swing"


# Concrete (execution, confirmation) timeframe pair per profile — a specific pick from
# each documented range in workflows/generate_strategy.md (e.g. scalping's "1m-5m" range
# -> "5m"), made explicit here so every tool derives it from one source of truth.
TIMEFRAME_PROFILE_MAP: dict[TimeframeProfile, tuple[str, str]] = {
    TimeframeProfile.SCALPING: ("5m", "15m"),
    TimeframeProfile.DAILY: ("1h", "4h"),
    TimeframeProfile.SWING: ("1d", "1w"),
}

# Duration of a single bar for each canonical timeframe string used across the project.
TIMEFRAME_DURATION: dict[str, pd.Timedelta] = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
    "1w": pd.Timedelta(days=7),
}


class Session(str, Enum):
    ASIA = "Asia"
    LONDON = "London"
    NY_AM = "NY AM"
    NY_PM = "NY PM"


class Indicator(str, Enum):
    RSI = "RSI"
    ADX = "ADX"
    VWAP = "VWAP"
    EMA = "EMA"
    ATR = "ATR"
    VOLUME_PROFILE = "Volume Profile"
    VOLUME = "Volume"


class RiskLevel(str, Enum):
    CONSERVATIVE = "conservative"
    MEDIUM = "medium"
    AGGRESSIVE = "aggressive"


class StrategyInputs(BaseModel):
    pair: Pair
    timeframe_profile: TimeframeProfile
    session: Session | None = None
    indicators: list[Indicator]
    risk_level: RiskLevel


class PrimitiveRole(str, Enum):
    ENTRY = "entry"
    CONFIRMATION = "confirmation"
    FILTER = "filter"


class RuleTimeframe(str, Enum):
    EXECUTION = "execution"
    CONFIRMATION = "confirmation"


class PrimitiveType(str, Enum):
    RSI_CROSS_ABOVE = "rsi_cross_above"
    RSI_CROSS_BELOW = "rsi_cross_below"
    RSI_BIAS = "rsi_bias"
    ADX_TREND_FILTER = "adx_trend_filter"
    VWAP_CROSS = "vwap_cross"
    VWAP_BIAS = "vwap_bias"
    EMA_CROSS = "ema_cross"
    EMA_BIAS = "ema_bias"
    VOLUME_SPIKE_CONFIRMATION = "volume_spike_confirmation"
    VOLUME_PROFILE_NEAR_NODE = "volume_profile_near_node"


class PrimitiveRule(BaseModel):
    indicator: Indicator
    role: PrimitiveRole
    primitive_type: PrimitiveType
    timeframe: RuleTimeframe
    params: dict[str, float] = Field(default_factory=dict)

    @property
    def signal_column(self) -> str:
        """Deterministic name of the boolean column tools/indicators.py must produce
        for this rule in the combined dataframe. Shared naming contract between
        indicators.py (producer) and code_generator.py (consumer) — change here only."""
        indicator_slug = self.indicator.value.lower().replace(" ", "_")
        return f"sig_{indicator_slug}_{self.primitive_type.value}_{self.timeframe.value}"


# Shared column-naming contract between tools/indicators.py (producer) and
# tools/code_generator.py (consumer) for columns that aren't tied to a single rule.
ATR_COLUMN = "atr"
SESSION_COLUMN = "in_session"


class RiskComponent(BaseModel):
    """ATR-multiple sizing for SL or TP. Direction (add/subtract) is resolved at
    execution time from the trade side, not stored here."""

    atr_multiple: float


class StrategySpec(BaseModel):
    inputs: StrategyInputs
    entry_rules: list[PrimitiveRule] = Field(min_length=1)
    confirmation_rules: list[PrimitiveRule] = Field(min_length=1)
    sl_formula: RiskComponent
    tp_formula: RiskComponent
    session_filter: Session | None = None

    def to_sheet(self) -> dict:
        """Human-readable strategy sheet, per workflows/generate_strategy.md's
        expected output."""
        return {
            "pair": self.inputs.pair.value,
            "timeframe_profile": self.inputs.timeframe_profile.value,
            "session": self.session_filter.value if self.session_filter else None,
            "risk_level": self.inputs.risk_level.value,
            "entry_rules": [r.model_dump() for r in self.entry_rules],
            "confirmation_rules": [r.model_dump() for r in self.confirmation_rules],
            "stop_loss": self.sl_formula.model_dump(),
            "take_profit": self.tp_formula.model_dump(),
        }


class LintResult(BaseModel):
    passed: bool
    violations: list[str] = Field(default_factory=list)


class BacktestMetrics(BaseModel):
    total_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    equity_curve: list[float]
    notes: list[str] = Field(default_factory=list)
