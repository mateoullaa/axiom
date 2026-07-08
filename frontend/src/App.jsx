import { useState } from 'react'
import StrategyForm from './components/StrategyForm'
import StrategySheet from './components/StrategySheet'
import CodeBlock from './components/CodeBlock'
import BacktestMetrics from './components/BacktestMetrics'
import './App.css'

function App() {
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(payload) {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const resp = await fetch('/api/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const body = await resp.json()
      if (!resp.ok) {
        const detail = Array.isArray(body.detail) ? body.detail.join('; ') : body.detail
        throw new Error(detail || 'Request failed')
      }
      setResult(body)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>Strategy Creator</h1>
      <StrategyForm onSubmit={handleSubmit} loading={loading} />
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="results">
          <StrategySheet sheet={result.strategy_sheet} />
          <CodeBlock code={result.code} />
          <BacktestMetrics metrics={result.metrics} />
        </div>
      )}
    </div>
  )
}

export default App
