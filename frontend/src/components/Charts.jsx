import { useEffect, useRef } from 'react'
import {
  AreaSeries,
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  LineSeries,
  PriceScaleMode,
} from 'lightweight-charts'

const UP = '#22c55e'
const DOWN = '#ef4444'
const ACCENT = '#38bdf8'
const MUTED = '#a1a1aa'

function baseOptions(intraday) {
  return {
    autoSize: true,
    layout: {
      background: { type: ColorType.Solid, color: 'transparent' },
      textColor: MUTED,
      fontSize: 11,
      attributionLogo: true,
      panes: { separatorColor: '#27272a' },
    },
    grid: {
      vertLines: { color: 'rgba(63,63,70,0.25)' },
      horzLines: { color: 'rgba(63,63,70,0.25)' },
    },
    rightPriceScale: { borderColor: '#3f3f46' },
    // Low minBarSpacing so fitContent() can show thousands of bars at once.
    timeScale: { borderColor: '#3f3f46', timeVisible: intraday, secondsVisible: false, minBarSpacing: 0.05 },
    crosshair: { horzLine: { labelBackgroundColor: '#3f3f46' }, vertLine: { labelBackgroundColor: '#3f3f46' } },
  }
}

function useChart(build, deps) {
  const ref = useRef(null)
  useEffect(() => {
    const chart = createChart(ref.current, build.options)
    build.draw(chart)
    chart.timeScale().fitContent()
    return () => chart.remove()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return ref
}

function splitMarker(time) {
  return { time, position: 'aboveBar', color: ACCENT, shape: 'arrowDown', text: 'out-of-sample →' }
}

// Candles with every entry and exit, plus where the out-of-sample period starts.
export function PriceChart({ report, intraday }) {
  const ref = useChart(
    {
      options: baseOptions(intraday),
      draw(chart) {
        const candles = chart.addSeries(CandlestickSeries, {
          upColor: UP,
          downColor: DOWN,
          borderVisible: false,
          wickUpColor: UP,
          wickDownColor: DOWN,
        })
        candles.setData(report.bars)
        const markers = [splitMarker(report.split_time)]
        report.trades.forEach((t, i) => {
          const long = t.side === 'long'
          const win = t.return_pct > 0
          markers.push({
            time: t.entry_time,
            position: long ? 'belowBar' : 'aboveBar',
            color: long ? UP : DOWN,
            shape: long ? 'arrowUp' : 'arrowDown',
            text: `#${i + 1}`,
          })
          markers.push({
            time: t.exit_time,
            position: long ? 'aboveBar' : 'belowBar',
            color: win ? '#86efac' : '#fca5a5',
            shape: 'circle',
          })
        })
        createSeriesMarkers(
          candles,
          markers.sort((a, b) => a.time - b.time),
        )
      },
    },
    [report],
  )
  return <div ref={ref} className="h-[420px] w-full" />
}

// Growth of 1 for the strategy vs buy & hold (log scale), with drawdown underneath.
export function EquityChart({ report, intraday }) {
  const ref = useChart(
    {
      options: {
        ...baseOptions(intraday),
        rightPriceScale: { borderColor: '#3f3f46', mode: PriceScaleMode.Logarithmic },
      },
      draw(chart) {
        const { bars, full } = report
        const eq0 = full.equity_curve[0]
        const close0 = bars[0].close
        let peak = -Infinity
        const growth = []
        const hold = []
        const drawdown = []
        bars.forEach((bar, i) => {
          const eq = full.equity_curve[i]
          peak = Math.max(peak, eq)
          growth.push({ time: bar.time, value: eq / eq0 })
          hold.push({ time: bar.time, value: bar.close / close0 })
          drawdown.push({ time: bar.time, value: (eq / peak - 1) * 100 })
        })

        const holdSeries = chart.addSeries(LineSeries, {
          color: MUTED,
          lineWidth: 1,
          lineStyle: 2,
          title: 'Buy & hold',
          priceLineVisible: false,
          lastValueVisible: false,
        })
        holdSeries.setData(hold)
        const strategy = chart.addSeries(LineSeries, {
          color: ACCENT,
          lineWidth: 2,
          title: 'Strategy',
          priceLineVisible: false,
        })
        strategy.setData(growth)
        createSeriesMarkers(strategy, [{ ...splitMarker(report.split_time), position: 'inBar' }])

        const dd = chart.addSeries(
          AreaSeries,
          {
            lineColor: DOWN,
            topColor: 'rgba(239,68,68,0.05)',
            bottomColor: 'rgba(239,68,68,0.35)',
            lineWidth: 1,
            title: 'Drawdown %',
            priceLineVisible: false,
            priceFormat: { type: 'custom', formatter: (v) => `${v.toFixed(1)}%` },
          },
          1,
        )
        dd.setData(drawdown)
        dd.priceScale().applyOptions({ mode: PriceScaleMode.Normal })
        chart.panes()[1]?.setHeight(110)
      },
    },
    [report],
  )
  return <div ref={ref} className="h-[400px] w-full" />
}
