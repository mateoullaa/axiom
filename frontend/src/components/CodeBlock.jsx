export default function CodeBlock({ code }) {
  function handleDownload() {
    const blob = new Blob([code], { type: 'text/x-python' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'generated_strategy.py'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section>
      <h2>Generated code</h2>
      <button type="button" onClick={handleDownload}>
        Download .py
      </button>
      <pre className="code-block">
        <code>{code}</code>
      </pre>
    </section>
  )
}
