import { useMemo, useState } from 'react'
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import 'highlight.js/styles/github-dark.css'

hljs.registerLanguage('python', python)

export default function CodeBlock({ code, filename }) {
  const [copied, setCopied] = useState(false)
  const html = useMemo(() => hljs.highlight(code, { language: 'python' }).value, [code])

  async function handleCopy() {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  function handleDownload() {
    const url = URL.createObjectURL(new Blob([code], { type: 'text/x-python' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-zinc-400">
          Standalone file: indicator math, signals and strategy. It is the exact module the backtest above ran.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleCopy}
            className="rounded-md px-3 py-1.5 text-sm text-zinc-300 ring-1 ring-zinc-700 hover:bg-zinc-800"
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="rounded-md bg-zinc-100 px-3 py-1.5 text-sm font-medium text-zinc-900 hover:bg-white"
          >
            Download {filename}
          </button>
        </div>
      </div>
      <pre className="max-h-[560px] overflow-auto rounded-lg bg-zinc-900 p-4 text-[13px] leading-relaxed ring-1 ring-zinc-800">
        <code className="hljs language-python font-mono" dangerouslySetInnerHTML={{ __html: html }} />
      </pre>
    </div>
  )
}
