import { useState } from 'react'

const PAIRS = ['BTC/USDT', 'SP500', 'Nasdaq', 'Gold']
const ETF_PAIRS = ['SP500', 'Nasdaq', 'Gold']
const PROFILES = [
  { id: 'scalping', label: 'Scalping', tf: '5m · 15m' },
  { id: 'daily', label: 'Intraday', tf: '1h · 4h' },
  { id: 'swing', label: 'Swing', tf: '1d · 1w' },
]
const SESSIONS = ['Asia', 'London', 'NY AM', 'NY PM']
const ENTRY_INDICATORS = ['EMA', 'RSI', 'VWAP']
const FILTER_INDICATORS = ['ADX', 'Volume', 'Volume Profile']
const RISK_LEVELS = [
  { id: 'conservative', hint: 'tight stop, small size' },
  { id: 'medium', hint: 'balanced' },
  { id: 'aggressive', hint: 'wide target, large size' },
]
const ok = { disabled: false }

function Section({ title, hint, children }) {
  return (
    <fieldset className="space-y-2">
      <legend className="flex w-full items-baseline justify-between text-xs font-medium uppercase tracking-wider text-zinc-400">
        {title}
        {hint && <span className="normal-case tracking-normal text-zinc-500">{hint}</span>}
      </legend>
      {children}
    </fieldset>
  )
}

function Segmented({ options, value, onChange, disabled = () => ok, columns }) {
  return (
    <div
      className="grid gap-1 rounded-lg bg-zinc-900 p-1 ring-1 ring-zinc-800"
      style={{ gridTemplateColumns: `repeat(${columns ?? options.length}, minmax(0, 1fr))` }}
    >
      {options.map((opt) => {
        const id = opt.id ?? opt
        const state = disabled(id)
        return (
          <button
            key={id}
            type="button"
            disabled={state.disabled}
            title={state.reason}
            aria-pressed={value === id}
            onClick={() => onChange(id)}
            className={`rounded-md px-2 py-1.5 text-sm transition ${
              value === id
                ? 'bg-zinc-700 text-white shadow'
                : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
            } disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent`}
          >
            {opt.label ?? opt}
            {opt.hint && <span className="block text-[11px] text-zinc-500">{opt.hint}</span>}
          </button>
        )
      })}
    </div>
  )
}

function Chip({ label, active, onClick, disabled, reason }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={reason}
      aria-pressed={active}
      className={`rounded-full px-3 py-1 text-sm ring-1 transition ${
        active
          ? 'bg-sky-400/15 text-sky-300 ring-sky-400/50'
          : 'text-zinc-400 ring-zinc-700 hover:text-zinc-200 hover:ring-zinc-500'
      } disabled:cursor-not-allowed disabled:opacity-30`}
    >
      {label}
    </button>
  )
}

export default function StrategyForm({ onSubmit, loading }) {
  const [pair, setPair] = useState('BTC/USDT')
  const [direction, setDirection] = useState('long')
  const [profile, setProfile] = useState('swing')
  const [session, setSession] = useState('NY AM')
  const [indicators, setIndicators] = useState(['EMA'])
  const [riskLevel, setRiskLevel] = useState('medium')
  const [clientError, setClientError] = useState(null)

  const isScalping = profile === 'scalping'
  const isEtf = ETF_PAIRS.includes(pair)

  function chooseProfile(next) {
    setProfile(next)
    if (next === 'swing') setIndicators((prev) => prev.filter((i) => i !== 'VWAP'))
  }

  function choosePair(next) {
    setPair(next)
    if (ETF_PAIRS.includes(next) && session === 'Asia') setSession('NY AM')
  }

  function toggle(indicator) {
    setIndicators((prev) =>
      prev.includes(indicator) ? prev.filter((i) => i !== indicator) : [...prev, indicator],
    )
  }

  function entryState(indicator) {
    if (indicator === 'VWAP' && profile === 'swing') {
      return { disabled: true, reason: 'VWAP resets daily, so it has no meaning on daily or weekly bars' }
    }
    return ok
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!indicators.some((i) => ENTRY_INDICATORS.includes(i))) {
      setClientError('Pick at least one entry signal: EMA, RSI or VWAP.')
      return
    }
    setClientError(null)
    onSubmit({
      pair,
      direction,
      timeframe_profile: profile,
      session: isScalping ? session : null,
      indicators,
      risk_level: riskLevel,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <Section title="Market">
        <Segmented options={PAIRS} value={pair} onChange={choosePair} columns={2} />
      </Section>

      <Section title="Direction">
        <Segmented
          options={[
            { id: 'long', label: 'Long' },
            { id: 'short', label: 'Short' },
          ]}
          value={direction}
          onChange={setDirection}
        />
      </Section>

      <Section title="Timeframe" hint="execution · confirmation">
        <Segmented
          options={PROFILES.map((p) => ({ ...p, hint: p.tf }))}
          value={profile}
          onChange={chooseProfile}
        />
      </Section>

      {isScalping && (
        <Section title="Session" hint="UTC">
          <Segmented
            options={SESSIONS}
            value={session}
            onChange={setSession}
            columns={2}
            disabled={(s) =>
              s === 'Asia' && isEtf
                ? { disabled: true, reason: 'US-listed ETFs have no bars during the Asia session' }
                : ok
            }
          />
        </Section>
      )}

      <Section title="Entry signal" hint="first selected wins">
        <div className="flex flex-wrap gap-2">
          {ENTRY_INDICATORS.map((ind) => (
            <Chip
              key={ind}
              label={ind}
              active={indicators.includes(ind)}
              onClick={() => toggle(ind)}
              {...entryState(ind)}
            />
          ))}
        </div>
      </Section>

      <Section title="Filters" hint="optional">
        <div className="flex flex-wrap gap-2">
          {FILTER_INDICATORS.map((ind) => (
            <Chip key={ind} label={ind} active={indicators.includes(ind)} onClick={() => toggle(ind)} />
          ))}
        </div>
        <p className="text-xs text-zinc-500">Stops and targets are always sized with ATR(14).</p>
      </Section>

      <Section title="Risk">
        <Segmented
          options={RISK_LEVELS.map((r) => ({ id: r.id, label: r.id[0].toUpperCase() + r.id.slice(1), hint: r.hint }))}
          value={riskLevel}
          onChange={setRiskLevel}
        />
      </Section>

      {clientError && (
        <p role="alert" className="rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-300">
          {clientError}
        </p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-sky-400 px-4 py-2.5 font-semibold text-zinc-950 transition hover:bg-sky-300 disabled:cursor-wait disabled:opacity-60"
      >
        {loading ? 'Backtesting…' : 'Build & backtest'}
      </button>
    </form>
  )
}
