// Fractions (0.123) and percentages (12.3) both arrive from the API: name says which.

export function fractionPct(value, digits = 1) {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function signedFractionPct(value, digits = 2) {
  if (value === null || value === undefined) return '—'
  const pct = value * 100
  return `${pct > 0 ? '+' : ''}${pct.toFixed(digits)}%`
}

export function signedPct(value, digits = 1) {
  if (value === null || value === undefined) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}%`
}

export function num(value, digits = 2) {
  if (value === null || value === undefined) return '—'
  return value.toFixed(digits)
}

export function price(value) {
  if (value === null || value === undefined) return '—'
  return value.toLocaleString('en-US', { maximumFractionDigits: value < 10 ? 4 : 2 })
}

const dateFmt = new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeZone: 'UTC' })
const dateTimeFmt = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'UTC',
})

export function date(unixSeconds, withTime = false) {
  const d = new Date(unixSeconds * 1000)
  return (withTime ? dateTimeFmt : dateFmt).format(d)
}

export function isIntraday(timeframe) {
  return ['5m', '15m', '1h', '4h'].includes(timeframe)
}

// Out-of-sample verdict badge colors.
export const VERDICT_STYLE = {
  pass: 'bg-emerald-400/10 text-emerald-300 ring-emerald-400/40',
  fail: 'bg-red-400/10 text-red-300 ring-red-400/40',
  inconclusive: 'bg-amber-400/10 text-amber-300 ring-amber-400/40',
}
