import { useState } from 'react'
import StrategyForm from './components/StrategyForm'
import CodeBlock from './components/CodeBlock'
import { EquityChart, PriceChart } from './components/Charts'
import { KpiGrid, RulesPanel, SampleTable, TradesTable } from './components/Panels'
import { date, isIntraday, VERDICT_STYLE } from './lib/format'

const REPO_URL = 'https://github.com/mateoullaa/axiom'
const TABS = ['Overview', 'Chart', 'Rules', 'Trades', 'Code']
const PROFILE_LABEL = { scalping: 'Scalping', daily: 'Intraday', swing: 'Swing' }

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#0b1220" />
      <path d="M8 24 L16 7 L24 24" fill="none" stroke="#38bdf8" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11.5 17.5 H20.5" stroke="#e2e8f0" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  )
}

function EmptyState() {
  const steps = [
    ['Compose', 'Your picks become rules from a closed catalog of objective primitives. No AI, no discretion.'],
    ['Lint', 'A linter rejects anything that is not fully defined: every threshold bound, stop and target set.'],
    ['Generate', 'The strategy is rendered as a standalone Python file you can run yourself.'],
    ['Backtest', 'That same file is backtested on real market data, then re-checked on an unseen 30% slice.'],
  ]
  return (
    <div className="flex h-full flex-col justify-center gap-8 py-10">
      <div>
        <h2 className="text-2xl font-semibold text-zinc-100">Rules, not predictions.</h2>
        <p className="mt-2 max-w-xl text-zinc-400">
          Pick a market, a timeframe and a few indicators. Axiom builds a strategy you could follow without a single
          judgment call, and shows you how it would have performed.
        </p>
      </div>
      <ol className="grid gap-3 sm:grid-cols-2">
        {steps.map(([title, text], i) => (
          <li key={title} className="rounded-lg bg-zinc-900/60 p-4 ring-1 ring-zinc-800">
            <span className="font-mono text-xs text-sky-400">0{i + 1}</span>
            <div className="mt-1 font-medium text-zinc-200">{title}</div>
            <p className="mt-1 text-sm text-zinc-400">{text}</p>
          </li>
        ))}
      </ol>
    </div>
  )
}

function LoadingState() {
  return (
    <div className="space-y-4" aria-busy="true">
      <p className="text-sm text-zinc-400">
        Fetching market data and backtesting… the first run for a market can take ~20 s; data is cached after that.
      </p>
      <div className="h-14 animate-pulse rounded-lg bg-zinc-900" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i} className="h-20 animate-pulse rounded-lg bg-zinc-900" />
        ))}
      </div>
      <div className="h-80 animate-pulse rounded-lg bg-zinc-900" />
    </div>
  )
}

function Results({ result }) {
  const [tab, setTab] = useState('Overview')
  const { strategy_sheet: sheet, report, code } = result
  const intraday = isIntraday(sheet.execution_timeframe)
  const first = report.bars[0]?.time
  const last = report.bars.at(-1)?.time
  const filename = `axiom_${sheet.pair.replace('/', '').toLowerCase()}_${sheet.timeframe_profile}_${sheet.direction}_${sheet.risk_level}.py`

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">
            {sheet.pair}{' '}
            <span className={sheet.direction === 'long' ? 'text-emerald-300' : 'text-red-300'}>
              {sheet.direction}
            </span>
          </h2>
          <p className="text-sm text-zinc-400">
            {PROFILE_LABEL[sheet.timeframe_profile]} · {sheet.execution_timeframe} entries, {sheet.confirmation_timeframe}{' '}
            confirmation{sheet.session && ` · ${sheet.session} session`} · {sheet.risk_level} risk ·{' '}
            {report.bars.length.toLocaleString()} bars, {date(first)} → {date(last)}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm ring-1 ${VERDICT_STYLE[report.oos_verdict]}`}>
          Out-of-sample: {report.oos_verdict}
        </span>
      </header>

      <nav className="flex gap-1 overflow-x-auto border-b border-zinc-800" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm transition ${
              tab === t ? 'border-sky-400 text-zinc-100' : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {t}
            {t === 'Trades' && <span className="ml-1.5 text-xs text-zinc-500">{report.trades.length}</span>}
          </button>
        ))}
      </nav>

      {tab === 'Overview' && (
        <div className="space-y-5">
          <KpiGrid metrics={report.full} />
          <div className="rounded-lg p-3 ring-1 ring-zinc-800">
            <div className="mb-2 flex items-center justify-between text-xs text-zinc-500">
              <span>Growth of 1 · strategy vs buy &amp; hold (log scale) · drawdown below</span>
            </div>
            <EquityChart report={report} intraday={intraday} />
          </div>
          <SampleTable report={report} />
          {report.full.notes.length > 0 && (
            <ul className="list-inside list-disc text-xs text-zinc-500">
              {report.full.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {tab === 'Chart' && (
        <div className="rounded-lg p-3 ring-1 ring-zinc-800">
          <p className="mb-2 text-xs text-zinc-500">Arrows: entries (numbered) · dots: exits, green when the trade won</p>
          <PriceChart report={report} intraday={intraday} />
        </div>
      )}
      {tab === 'Rules' && <RulesPanel sheet={sheet} />}
      {tab === 'Trades' && <TradesTable trades={report.trades} intraday={intraday} />}
      {tab === 'Code' && <CodeBlock code={code} filename={filename} />}
    </div>
  )
}

export default function App() {
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(payload) {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch('/api/strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const text = await resp.text()
      let body
      try {
        body = JSON.parse(text)
      } catch {
        throw new Error(resp.ok ? 'The server sent an unreadable response.' : `Server error (${resp.status}).`)
      }
      if (!resp.ok) {
        const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg ?? d).join('; ') : body.detail
        throw new Error(detail || `Request failed (${resp.status}).`)
      }
      setResult(body)
    } catch (err) {
      setError(err instanceof TypeError ? 'Cannot reach the API. Is the backend running on port 8000?' : err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-zinc-800/80">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Logo />
            <div>
              <div className="font-semibold tracking-tight text-zinc-100">Axiom</div>
              <div className="text-xs text-zinc-500">Deterministic strategy builder</div>
            </div>
          </div>
          <a href={REPO_URL} className="text-sm text-zinc-400 hover:text-zinc-200" target="_blank" rel="noreferrer">
            GitHub ↗
          </a>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-7xl flex-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="rounded-xl bg-zinc-900/40 p-5 ring-1 ring-zinc-800">
            <StrategyForm onSubmit={handleSubmit} loading={loading} />
          </div>
        </aside>
        <section className="min-w-0">
          {error && (
            <div role="alert" className="mb-4 rounded-lg bg-red-500/10 px-4 py-3 text-sm text-red-200 ring-1 ring-red-500/30">
              {error}
            </div>
          )}
          {loading ? <LoadingState /> : result ? <Results key={result.code} result={result} /> : <EmptyState />}
        </section>
      </main>

      <footer className="border-t border-zinc-800/80 px-4 py-4 text-center text-xs text-zinc-500">
        Educational tool, not financial advice. Data: Binance (BTC/USDT) and Yahoo Finance (SPY, QQQ, GLD as proxies).
        Charts by{' '}
        <a href="https://www.tradingview.com/lightweight-charts/" className="underline hover:text-zinc-300" target="_blank" rel="noreferrer">
          TradingView Lightweight Charts
        </a>
        .
      </footer>
    </div>
  )
}
