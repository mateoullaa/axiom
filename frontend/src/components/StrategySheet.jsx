export default function StrategySheet({ sheet }) {
  return (
    <section>
      <h2>Strategy sheet</h2>
      <dl>
        <dt>Pair</dt>
        <dd>{sheet.pair}</dd>
        <dt>Timeframe profile</dt>
        <dd>{sheet.timeframe_profile}</dd>
        {sheet.session && (
          <>
            <dt>Session</dt>
            <dd>{sheet.session}</dd>
          </>
        )}
        <dt>Risk level</dt>
        <dd>{sheet.risk_level}</dd>
        <dt>Stop loss</dt>
        <dd>{sheet.stop_loss.atr_multiple}&times; ATR</dd>
        <dt>Take profit</dt>
        <dd>{sheet.take_profit.atr_multiple}&times; ATR</dd>
      </dl>

      <h3>Entry rules</h3>
      <ul>
        {sheet.entry_rules.map((rule, i) => (
          <li key={i}>
            {rule.indicator} — {rule.primitive_type} ({rule.timeframe})
          </li>
        ))}
      </ul>

      <h3>Confirmation rules</h3>
      <ul>
        {sheet.confirmation_rules.map((rule, i) => (
          <li key={i}>
            {rule.indicator} — {rule.primitive_type} ({rule.timeframe})
          </li>
        ))}
      </ul>
    </section>
  )
}
