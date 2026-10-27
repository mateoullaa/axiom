"""Deterministic strategy composition engine.

Pure function of StrategyInputs -> StrategySpec, no I/O, no market data, no randomness.
Composes only from the closed primitive catalog documented in
docs/development/workflows/generate_strategy.md — this module IS that catalog's implementation, so any
change to what's composable belongs here and in that doc together.

Each strategy trades one side, chosen by the user (StrategyInputs.direction): one
primary entry signal + confirmation bias filters, all evaluated for that side. Short
strategies use the mirrored primitive (cross below, bias below, overbought instead of
oversold); non-directional primitives (ADX, Volume, Volume Profile) are side-agnostic.
"""

from tools.schemas import (
    Direction,
    Indicator,
    Pair,
    PrimitiveRole,
    PrimitiveRule,
    PrimitiveType,
    RiskComponent,
    RiskLevel,
    RuleTimeframe,
    Session,
    StrategyInputs,
    StrategySpec,
    TimeframeProfile,
)

# Entry-capable indicators, in the fixed priority order used to pick ONE primary entry
# signal when several are selected. Order is arbitrary but must stay deterministic.
ENTRY_PRIORITY = [Indicator.EMA, Indicator.VWAP, Indicator.RSI]

# Confirmation-capable indicators (confirmation timeframe, required — see
# docs/development/workflows/generate_strategy.md). Volume / Volume Profile are handled separately below:
# they only ever supplement this list, they never satisfy the requirement on their own.
CONFIRMATION_CAPABLE = [Indicator.EMA, Indicator.VWAP, Indicator.RSI, Indicator.ADX]

FAST_EMA_PERIOD = 12.0
SLOW_EMA_PERIOD = 26.0
CONFIRM_EMA_PERIOD = 50.0
RSI_CONFIRM_MIDLINE = 50.0
VOLUME_PROFILE_BIN_COUNT = 24.0
VOLUME_PROFILE_LOOKBACK_BARS = 200.0
VOLUME_PROFILE_NODE_DISTANCE_PCT = 0.5

# Constants per risk level, validated against real backtests (docs/calibration_notes.md).
# position_size is the fraction of equity committed per trade (backtesting.py `size`).
RISK_PARAMS = {
    RiskLevel.CONSERVATIVE: {
        "sl_atr_multiple": 1.0,
        "tp_atr_multiple": 1.5,
        "adx_threshold": 25.0,
        "rsi_oversold": 35.0,
        "volume_spike_multiple": 2.0,
        "position_size": 0.25,
    },
    RiskLevel.MEDIUM: {
        "sl_atr_multiple": 1.5,
        "tp_atr_multiple": 3.0,
        "adx_threshold": 20.0,
        "rsi_oversold": 30.0,
        "volume_spike_multiple": 1.5,
        "position_size": 0.5,
    },
    RiskLevel.AGGRESSIVE: {
        "sl_atr_multiple": 2.0,
        "tp_atr_multiple": 6.0,
        "adx_threshold": 15.0,
        "rsi_oversold": 25.0,
        "volume_spike_multiple": 1.2,
        "position_size": 0.95,
    },
}


class StrategyCompositionError(Exception):
    """Raised when the selected inputs can't form a valid, objective strategy."""


# Pairs whose data source (US-listed ETFs) has no bars outside US market hours.
US_SESSION_ONLY_PAIRS = {Pair.SP500, Pair.NASDAQ, Pair.GOLD}

# VWAP resets every UTC day, so it only means something on intraday bars.
VWAP_UNSUPPORTED_PROFILES = {TimeframeProfile.SWING}


def compose_strategy(inputs: StrategyInputs) -> StrategySpec:
    _validate_session(inputs)
    _validate_indicator_fit(inputs)
    entry_rules = _build_entry_rules(inputs)
    confirmation_rules = _build_confirmation_rules(inputs)
    params = RISK_PARAMS[inputs.risk_level]
    session_filter = (
        inputs.session if inputs.timeframe_profile == TimeframeProfile.SCALPING else None
    )
    return StrategySpec(
        inputs=inputs,
        entry_rules=entry_rules,
        confirmation_rules=confirmation_rules,
        sl_formula=RiskComponent(atr_multiple=params["sl_atr_multiple"]),
        tp_formula=RiskComponent(atr_multiple=params["tp_atr_multiple"]),
        position_size=params["position_size"],
        session_filter=session_filter,
    )


def _validate_session(inputs: StrategyInputs) -> None:
    if inputs.timeframe_profile == TimeframeProfile.SCALPING and inputs.session is None:
        raise StrategyCompositionError(
            "scalping requires a session (Asia, London, NY AM, or NY PM) — none was provided"
        )
    if inputs.timeframe_profile != TimeframeProfile.SCALPING and inputs.session is not None:
        raise StrategyCompositionError(
            f"session filter only applies to scalping, not {inputs.timeframe_profile.value}"
        )
    if inputs.session == Session.ASIA and inputs.pair in US_SESSION_ONLY_PAIRS:
        raise StrategyCompositionError(
            f"{inputs.pair.value} is traded through a US-listed ETF, which has no bars during "
            "the Asia session — pick London, NY AM or NY PM"
        )


def _validate_indicator_fit(inputs: StrategyInputs) -> None:
    if Indicator.VWAP in inputs.indicators and inputs.timeframe_profile in VWAP_UNSUPPORTED_PROFILES:
        raise StrategyCompositionError(
            "VWAP is session-anchored (it resets every UTC day), so it has no meaning on "
            f"{inputs.timeframe_profile.value} bars — use it with scalping or daily, or pick "
            "EMA/RSI instead"
        )


def _build_entry_rules(inputs: StrategyInputs) -> list[PrimitiveRule]:
    for indicator in ENTRY_PRIORITY:
        if indicator in inputs.indicators:
            return [_entry_rule_for(indicator, inputs.risk_level, inputs.direction)]
    selected = [i.value for i in inputs.indicators]
    raise StrategyCompositionError(
        f"no entry primitive available for the selected indicators {selected}; "
        "at least one of EMA, VWAP, or RSI is required to form an entry signal"
    )


def _entry_rule_for(indicator: Indicator, risk_level: RiskLevel, direction: Direction) -> PrimitiveRule:
    if indicator == Indicator.EMA:
        return PrimitiveRule(
            indicator=Indicator.EMA,
            role=PrimitiveRole.ENTRY,
            primitive_type=PrimitiveType.EMA_CROSS,
            timeframe=RuleTimeframe.EXECUTION,
            params={"fast_period": FAST_EMA_PERIOD, "slow_period": SLOW_EMA_PERIOD},
            direction=direction,
        )
    if indicator == Indicator.VWAP:
        return PrimitiveRule(
            indicator=Indicator.VWAP,
            role=PrimitiveRole.ENTRY,
            primitive_type=PrimitiveType.VWAP_CROSS,
            timeframe=RuleTimeframe.EXECUTION,
            params={},
            direction=direction,
        )
    # indicator == Indicator.RSI: long buys the cross back above oversold, short sells
    # the cross back below the mirrored overbought level.
    oversold = RISK_PARAMS[risk_level]["rsi_oversold"]
    if direction == Direction.SHORT:
        primitive_type, threshold = PrimitiveType.RSI_CROSS_BELOW, 100.0 - oversold
    else:
        primitive_type, threshold = PrimitiveType.RSI_CROSS_ABOVE, oversold
    return PrimitiveRule(
        indicator=Indicator.RSI,
        role=PrimitiveRole.ENTRY,
        primitive_type=primitive_type,
        timeframe=RuleTimeframe.EXECUTION,
        params={"threshold": threshold},
        direction=direction,
    )


def _build_confirmation_rules(inputs: StrategyInputs) -> list[PrimitiveRule]:
    params = RISK_PARAMS[inputs.risk_level]
    direction = inputs.direction
    rules: list[PrimitiveRule] = []

    if Indicator.EMA in inputs.indicators:
        rules.append(
            PrimitiveRule(
                indicator=Indicator.EMA,
                role=PrimitiveRole.CONFIRMATION,
                primitive_type=PrimitiveType.EMA_BIAS,
                timeframe=RuleTimeframe.CONFIRMATION,
                params={"period": CONFIRM_EMA_PERIOD},
                direction=direction,
            )
        )
    if Indicator.VWAP in inputs.indicators:
        rules.append(
            PrimitiveRule(
                indicator=Indicator.VWAP,
                role=PrimitiveRole.CONFIRMATION,
                primitive_type=PrimitiveType.VWAP_BIAS,
                timeframe=RuleTimeframe.CONFIRMATION,
                params={},
                direction=direction,
            )
        )
    if Indicator.RSI in inputs.indicators:
        rules.append(
            PrimitiveRule(
                indicator=Indicator.RSI,
                role=PrimitiveRole.CONFIRMATION,
                primitive_type=PrimitiveType.RSI_BIAS,
                timeframe=RuleTimeframe.CONFIRMATION,
                params={"midline": RSI_CONFIRM_MIDLINE},
                direction=direction,
            )
        )
    if Indicator.ADX in inputs.indicators:
        rules.append(
            PrimitiveRule(
                indicator=Indicator.ADX,
                role=PrimitiveRole.FILTER,
                primitive_type=PrimitiveType.ADX_TREND_FILTER,
                timeframe=RuleTimeframe.CONFIRMATION,
                params={"threshold": params["adx_threshold"]},
                direction=direction,
            )
        )

    if not any(r.timeframe == RuleTimeframe.CONFIRMATION for r in rules):
        selected = [i.value for i in inputs.indicators]
        raise StrategyCompositionError(
            f"no confirmation primitive available on the confirmation timeframe for the "
            f"selected indicators {selected}; at least one of EMA, VWAP, RSI, or ADX is required"
        )

    # Supplementary execution-timeframe confirmations. Never standalone (they can't reach
    # here without a real confirmation-timeframe rule already present above).
    if Indicator.VOLUME in inputs.indicators:
        rules.append(
            PrimitiveRule(
                indicator=Indicator.VOLUME,
                role=PrimitiveRole.CONFIRMATION,
                primitive_type=PrimitiveType.VOLUME_SPIKE_CONFIRMATION,
                timeframe=RuleTimeframe.EXECUTION,
                params={"multiple": params["volume_spike_multiple"]},
                direction=direction,
            )
        )
    if Indicator.VOLUME_PROFILE in inputs.indicators:
        rules.append(
            PrimitiveRule(
                indicator=Indicator.VOLUME_PROFILE,
                role=PrimitiveRole.CONFIRMATION,
                primitive_type=PrimitiveType.VOLUME_PROFILE_NEAR_NODE,
                timeframe=RuleTimeframe.EXECUTION,
                params={
                    "bin_count": VOLUME_PROFILE_BIN_COUNT,
                    "lookback_bars": VOLUME_PROFILE_LOOKBACK_BARS,
                    "node_distance_pct": VOLUME_PROFILE_NODE_DISTANCE_PCT,
                },
                direction=direction,
            )
        )

    return rules
