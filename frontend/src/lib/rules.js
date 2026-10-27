// Plain-English rendering of the closed primitive catalog (tools/schemas.py PrimitiveType).

export function describeRule(rule) {
  const short = rule.direction === 'short'
  const p = rule.params
  switch (rule.primitive_type) {
    case 'ema_cross':
      return `EMA(${p.fast_period}) crosses ${short ? 'below' : 'above'} EMA(${p.slow_period})`
    case 'ema_bias':
      return `Close ${short ? 'below' : 'above'} EMA(${p.period})`
    case 'vwap_cross':
      return `Close crosses ${short ? 'below' : 'above'} the daily VWAP`
    case 'vwap_bias':
      return `Close ${short ? 'below' : 'above'} the daily VWAP`
    case 'rsi_cross_above':
      return `RSI(14) crosses back above ${p.threshold} (out of oversold)`
    case 'rsi_cross_below':
      return `RSI(14) crosses back below ${p.threshold} (out of overbought)`
    case 'rsi_bias':
      return `RSI(14) ${short ? 'below' : 'above'} ${p.midline}`
    case 'adx_trend_filter':
      return `ADX(14) above ${p.threshold}: trend strong enough to trade`
    case 'volume_spike_confirmation':
      return `Volume above ${p.multiple}× its 20-bar average`
    case 'volume_profile_near_node':
      return `Close within ${p.node_distance_pct}% of the ${p.lookback_bars}-bar volume point of control`
    default:
      return rule.primitive_type
  }
}

export function ruleTimeframe(rule, sheet) {
  return rule.timeframe === 'execution' ? sheet.execution_timeframe : sheet.confirmation_timeframe
}
