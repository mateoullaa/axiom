export default function BacktestMetrics({ metrics }) {
  const curve = metrics.equity_curve
  const width = 400
  const height = 100
  const min = Math.min(...curve)
  const max = Math.max(...curve)
  const range = max - min || 1
  const points = curve
    .map((v, i) => {
      const x = (i / (curve.length - 1 || 1)) * width
      const y = height - ((v - min) / range) * height
      return `${x},${y}`
    })
    .join(' ')

  return (
    <section>
      <h2>Backtest metrics</h2>
      <dl>
        <dt>Total trades</dt>
        <dd>{metrics.total_trades}</dd>
        <dt>Win rate</dt>
        <dd>{(metrics.win_rate * 100).toFixed(1)}%</dd>
        <dt>Profit factor</dt>
        <dd>{metrics.profit_factor.toFixed(2)}</dd>
        <dt>Expectancy</dt>
        <dd>{(metrics.expectancy * 100).toFixed(2)}%</dd>
        <dt>Max drawdown</dt>
        <dd>{(metrics.max_drawdown * 100).toFixed(1)}%</dd>
      </dl>

      {curve.length > 1 && (
        <svg width={width} height={height} className="equity-curve">
          <polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      )}

      {metrics.notes.length > 0 && (
        <ul className="notes">
          {metrics.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
