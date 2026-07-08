"""Objectivity/executability gate — implements the checklist in
workflows/validate_strategy.md mechanically against a StrategySpec.

Runs as defense in depth on top of the schema's own type constraints (see
tools/schemas.py): a StrategySpec can only be *constructed* validly through pydantic,
but this module still checks it explicitly, since a spec can be hand-mutated (tests,
future callers using model_copy/model_construct) without going back through the
constructor. Never short-circuits — collects every violation before returning.
"""

import math

from tools.schemas import Indicator, LintResult, PrimitiveType, RuleTimeframe, StrategySpec, TimeframeProfile

ALLOWED_PRIMITIVES_BY_INDICATOR: dict[Indicator, set[PrimitiveType]] = {
    Indicator.RSI: {PrimitiveType.RSI_CROSS_ABOVE, PrimitiveType.RSI_CROSS_BELOW, PrimitiveType.RSI_BIAS},
    Indicator.ADX: {PrimitiveType.ADX_TREND_FILTER},
    Indicator.VWAP: {PrimitiveType.VWAP_CROSS, PrimitiveType.VWAP_BIAS},
    Indicator.EMA: {PrimitiveType.EMA_CROSS, PrimitiveType.EMA_BIAS},
    Indicator.VOLUME: {PrimitiveType.VOLUME_SPIKE_CONFIRMATION},
    Indicator.VOLUME_PROFILE: {PrimitiveType.VOLUME_PROFILE_NEAR_NODE},
    Indicator.ATR: set(),  # ATR is sizing-only; it must never appear as a rule primitive
}

REQUIRED_PARAMS_BY_PRIMITIVE_TYPE: dict[PrimitiveType, set[str]] = {
    PrimitiveType.RSI_CROSS_ABOVE: {"threshold"},
    PrimitiveType.RSI_CROSS_BELOW: {"threshold"},
    PrimitiveType.RSI_BIAS: {"midline"},
    PrimitiveType.ADX_TREND_FILTER: {"threshold"},
    PrimitiveType.VWAP_CROSS: set(),
    PrimitiveType.VWAP_BIAS: set(),
    PrimitiveType.EMA_CROSS: {"fast_period", "slow_period"},
    PrimitiveType.EMA_BIAS: {"period"},
    PrimitiveType.VOLUME_SPIKE_CONFIRMATION: {"multiple"},
    PrimitiveType.VOLUME_PROFILE_NEAR_NODE: {"bin_count", "lookback_bars", "node_distance_pct"},
}


def lint(spec: StrategySpec) -> LintResult:
    violations: list[str] = []
    all_rules = list(spec.entry_rules) + list(spec.confirmation_rules)

    violations += _check_closed_catalog(all_rules)
    violations += _check_required_params(all_rules)
    violations += _check_sl_defined(spec)
    violations += _check_tp_defined(spec)
    violations += _check_confirmation_present(spec)
    violations += _check_session_filter(spec)

    return LintResult(passed=len(violations) == 0, violations=violations)


def _check_closed_catalog(rules) -> list[str]:
    violations = []
    for rule in rules:
        allowed = ALLOWED_PRIMITIVES_BY_INDICATOR.get(rule.indicator, set())
        if rule.primitive_type not in allowed:
            violations.append(
                f"'{rule.primitive_type}' is not a valid primitive for indicator "
                f"'{rule.indicator.value}' (closed catalog violation)"
            )
    return violations


def _check_required_params(rules) -> list[str]:
    violations = []
    for rule in rules:
        required = REQUIRED_PARAMS_BY_PRIMITIVE_TYPE.get(rule.primitive_type, set())
        missing = required - rule.params.keys()
        if missing:
            violations.append(
                f"rule '{rule.primitive_type}' is missing required param(s) {sorted(missing)}"
            )
        for key, value in rule.params.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                violations.append(f"rule '{rule.primitive_type}' has an unbound threshold for '{key}'")
    return violations


def _check_sl_defined(spec: StrategySpec) -> list[str]:
    if spec.sl_formula is None or spec.sl_formula.atr_multiple <= 0:
        return ["stop-loss is not defined (sl_formula missing or atr_multiple <= 0)"]
    return []


def _check_tp_defined(spec: StrategySpec) -> list[str]:
    if spec.tp_formula is None or spec.tp_formula.atr_multiple <= 0:
        return ["take-profit is not defined (tp_formula missing or atr_multiple <= 0)"]
    return []


def _check_confirmation_present(spec: StrategySpec) -> list[str]:
    has_confirmation_tf_rule = any(
        r.timeframe == RuleTimeframe.CONFIRMATION for r in spec.confirmation_rules
    )
    if not has_confirmation_tf_rule:
        return ["no confirmation-timeframe rule present"]
    return []


def _check_session_filter(spec: StrategySpec) -> list[str]:
    is_scalping = spec.inputs.timeframe_profile == TimeframeProfile.SCALPING
    if is_scalping and spec.session_filter is None:
        return ["scalping strategy is missing its required session filter"]
    if not is_scalping and spec.session_filter is not None:
        return [f"session filter present on a non-scalping ({spec.inputs.timeframe_profile.value}) strategy"]
    return []
