import { useState } from 'react'

const PAIRS = ['BTC/USDT', 'SP500', 'Nasdaq', 'Gold']
const PROFILES = ['scalping', 'daily', 'swing']
const SESSIONS = ['Asia', 'London', 'NY AM', 'NY PM']
const INDICATORS = ['RSI', 'ADX', 'VWAP', 'EMA', 'ATR', 'Volume Profile', 'Volume']
const RISK_LEVELS = ['conservative', 'medium', 'aggressive']

export default function StrategyForm({ onSubmit, loading }) {
  const [pair, setPair] = useState(PAIRS[0])
  const [timeframeProfile, setTimeframeProfile] = useState(PROFILES[0])
  const [session, setSession] = useState(SESSIONS[0])
  const [indicators, setIndicators] = useState(['EMA'])
  const [riskLevel, setRiskLevel] = useState(RISK_LEVELS[1])
  const [clientError, setClientError] = useState(null)

  const isScalping = timeframeProfile === 'scalping'

  function toggleIndicator(indicator) {
    setIndicators((prev) =>
      prev.includes(indicator) ? prev.filter((i) => i !== indicator) : [...prev, indicator]
    )
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (indicators.length === 0) {
      setClientError('Select at least one indicator.')
      return
    }
    setClientError(null)
    onSubmit({
      pair,
      timeframe_profile: timeframeProfile,
      session: isScalping ? session : null,
      indicators,
      risk_level: riskLevel,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="strategy-form">
      <label>
        Pair
        <select value={pair} onChange={(e) => setPair(e.target.value)}>
          {PAIRS.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </label>

      <label>
        Timeframe profile
        <select value={timeframeProfile} onChange={(e) => setTimeframeProfile(e.target.value)}>
          {PROFILES.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </label>

      {isScalping && (
        <label>
          Session
          <select value={session} onChange={(e) => setSession(e.target.value)}>
            {SESSIONS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      )}

      <fieldset>
        <legend>Indicators</legend>
        {INDICATORS.map((ind) => (
          <label key={ind} className="checkbox">
            <input
              type="checkbox"
              checked={indicators.includes(ind)}
              onChange={() => toggleIndicator(ind)}
            />
            {ind}
          </label>
        ))}
      </fieldset>

      <label>
        Risk level
        <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
          {RISK_LEVELS.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
      </label>

      {clientError && <p className="error">{clientError}</p>}

      <button type="submit" disabled={loading}>
        {loading ? 'Generating…' : 'Generate strategy'}
      </button>
    </form>
  )
}
