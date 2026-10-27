import { describeRule, ruleTimeframe } from '../lib/rules'
import { date, fractionPct, num, price, signedFractionPct, signedPct, VERDICT_STYLE } from '../lib/format'

function tone(value, goodWhenAbove = 0) {
  if (value === null || value === undefined) return 'text-zinc-200'
  return value > goodWhenAbove ? 'text-emerald-300' : 'text-red-300'
}

function Kpi({ label, value, sub, className = 'text-zinc-100' }) {
  return (
    <div className="rounded-lg bg-zinc-900/70 p-3 ring-1 ring-zinc-800">
      <div className="text-[11px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold tabular-nums ${className}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-zinc-500">{sub}</div>}
    </div>
  )
}

export function KpiGrid({ metrics }) {
  const m = metrics
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Kpi label="Profit factor" value={num(m.profit_factor)} className={tone(m.profit_factor, 1)} sub="gross win / gross loss" />
      <Kpi label="Expectancy" value={signedFractionPct(m.expectancy)} className={tone(m.expectancy)} sub="average return per trade" />
      <Kpi label="Win rate" value={fractionPct(m.win_rate, 0)} sub={`${m.total_trades} trades`} />
      <Kpi label="Max drawdown" value={fractionPct(m.max_drawdown)} className="text-red-300" />
      <Kpi label="Return" value={signedPct(m.return_pct)} className={tone(m.return_pct)} sub={`buy & hold ${signedPct(m.buy_hold_return_pct)}`} />
      <Kpi label="CAGR" value={signedPct(m.cagr_pct)} />
      <Kpi label="Sharpe" value={num(m.sharpe)} sub={`Sortino ${num(m.sortino)}`} />
      <Kpi label="Exposure" value={m.exposure_pct === null ? '—' : `${m.exposure_pct.toFixed(0)}%`} sub="time in the market" />
    </div>
  )
}

export function SampleTable({ report }) {
  const rows = [
    ['Trades', (m) => m.total_trades],
    ['Win rate', (m) => fractionPct(m.win_rate, 0)],
    ['Profit factor', (m) => num(m.profit_factor)],
    ['Expectancy / trade', (m) => signedFractionPct(m.expectancy)],
    ['Max drawdown', (m) => fractionPct(m.max_drawdown)],
    ['Return', (m) => signedPct(m.return_pct)],
  ]
  const cols = [
    ['In-sample · 70%', report.in_sample],
    ['Out-of-sample · 30%', report.out_of_sample],
  ]
  return (
    <div className="rounded-lg ring-1 ring-zinc-800">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-3">
        <h3 className="text-sm font-medium text-zinc-200">Stability check</h3>
        <span className="text-xs text-zinc-500">out-of-sample starts {date(report.split_time)}</span>
      </div>
      <table className="w-full text-sm tabular-nums">
        <thead>
          <tr className="text-left text-xs text-zinc-500">
            <th className="px-4 py-2 font-normal">Metric</th>
            {cols.map(([label]) => (
              <th key={label} className="px-4 py-2 text-right font-normal">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, get]) => (
            <tr key={label} className="border-t border-zinc-800/60">
              <td className="px-4 py-2 text-zinc-400">{label}</td>
              {cols.map(([col, m]) => (
                <td key={col} className="px-4 py-2 text-right text-zinc-200">{get(m)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-zinc-800 px-4 py-3 text-xs text-zinc-400">
        <span className={`mr-2 rounded px-1.5 py-0.5 font-medium uppercase ring-1 ${VERDICT_STYLE[report.oos_verdict]}`}>
          {report.oos_verdict}
        </span>
        {report.oos_reason}. Rule constants are fixed by the catalog, not fitted per run, so this checks that the edge
        holds across time rather than in one lucky stretch.
      </p>
    </div>
  )
}

function RuleCard({ tag, title, detail, timeframe }) {
  return (
    <li className="flex items-start gap-3 rounded-lg bg-zinc-900/70 p-3 ring-1 ring-zinc-800">
      <span className="mt-0.5 rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-[11px] text-zinc-400">{timeframe}</span>
      <div>
        <div className="text-sm text-zinc-100">{title}</div>
        <div className="text-xs text-zinc-500">
          {tag}
          {detail && ` · ${detail}`}
        </div>
      </div>
    </li>
  )
}

export function RulesPanel({ sheet }) {
  const short = sheet.direction === 'short'
  const sl = sheet.stop_loss.atr_multiple
  const tp = sheet.take_profit.atr_multiple
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-zinc-300">
          {short ? 'Sell short' : 'Buy'} when <span className="text-zinc-500">all of these are true on a closed bar</span>
        </h3>
        <ul className="space-y-2">
          {sheet.entry_rules.map((r) => (
            <RuleCard key={r.primitive_type} tag="entry signal" title={describeRule(r)} timeframe={ruleTimeframe(r, sheet)} />
          ))}
          {sheet.confirmation_rules.map((r) => (
            <RuleCard
              key={r.primitive_type}
              tag={r.role === 'filter' ? 'filter' : 'confirmation'}
              detail={r.timeframe === 'confirmation' ? 'higher timeframe, only once its bar has closed' : null}
              title={describeRule(r)}
              timeframe={ruleTimeframe(r, sheet)}
            />
          ))}
          {sheet.session && (
            <RuleCard tag="session filter" title={`Bar opens inside the ${sheet.session} session (UTC)`} timeframe={sheet.execution_timeframe} />
          )}
        </ul>
      </div>
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-zinc-300">Exit and sizing</h3>
        <ul className="space-y-2">
          <RuleCard tag="stop-loss" title={`${sl} × ATR(14) ${short ? 'above' : 'below'} entry`} timeframe={sheet.execution_timeframe} />
          <RuleCard
            tag="take-profit"
            title={`${tp} × ATR(14) ${short ? 'below' : 'above'} entry`}
            detail={`reward / risk ${num(tp / sl, 1)}`}
            timeframe={sheet.execution_timeframe}
          />
          <RuleCard
            tag="position size"
            title={`${Math.round(sheet.position_size * 100)}% of equity per trade`}
            detail="one position at a time · 0.1% commission"
            timeframe={sheet.risk_level}
          />
        </ul>
      </div>
    </div>
  )
}

export function TradesTable({ trades, intraday }) {
  if (trades.length === 0) {
    return <p className="text-sm text-zinc-400">No trades: the rules never lined up over this period.</p>
  }
  return (
    <div className="max-h-[520px] overflow-auto rounded-lg ring-1 ring-zinc-800">
      <table className="w-full text-sm tabular-nums">
        <thead className="sticky top-0 bg-zinc-900 text-left text-xs text-zinc-500">
          <tr>
            {['#', 'Side', 'Entry', 'Price', 'Exit', 'Price', 'Return', 'Exit reason'].map((h, i) => (
              <th key={i} className={`px-3 py-2 font-normal ${i >= 3 && i !== 4 && i !== 7 ? 'text-right' : ''}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={t.entry_time} className="border-t border-zinc-800/60">
              <td className="px-3 py-1.5 text-zinc-500">{i + 1}</td>
              <td className={`px-3 py-1.5 capitalize ${t.side === 'long' ? 'text-emerald-300' : 'text-red-300'}`}>{t.side}</td>
              <td className="px-3 py-1.5 text-zinc-300">{date(t.entry_time, intraday)}</td>
              <td className="px-3 py-1.5 text-right text-zinc-300">{price(t.entry_price)}</td>
              <td className="px-3 py-1.5 text-zinc-300">{date(t.exit_time, intraday)}</td>
              <td className="px-3 py-1.5 text-right text-zinc-300">{price(t.exit_price)}</td>
              <td className={`px-3 py-1.5 text-right ${t.return_pct > 0 ? 'text-emerald-300' : 'text-red-300'}`}>
                {signedFractionPct(t.return_pct)}
              </td>
              <td className="px-3 py-1.5 text-zinc-400">{t.exit_reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
