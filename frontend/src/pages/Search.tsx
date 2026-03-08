import { useState, useRef } from 'react'
import { Search as SearchIcon, Send, FileText, StopCircle } from 'lucide-react'

interface Chunk {
  id: string
  text: string
  section: string
  score: number
}

export default function Search() {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState<string[]>([])
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<(() => void) | null>(null)

  const submit = async () => {
    if (!query.trim() || streaming) return
    setChunks([])
    setAnswer('')
    setSources([])
    setError(null)
    setStreaming(true)

    const url = `/api/ask?query=${encodeURIComponent(query)}&top_k=${topK}`
    const es = new EventSource(url)
    abortRef.current = () => es.close()

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data)
        if (payload.type === 'chunk') {
          setChunks(prev => [...prev, payload.data])
        } else if (payload.type === 'answer_token') {
          setAnswer(prev => prev + payload.data)
        } else if (payload.type === 'done') {
          setSources(payload.sources ?? [])
          setStreaming(false)
          es.close()
        }
      } catch {
        // ignore parse errors
      }
    }

    es.onerror = () => {
      setError('Connection error — is the server running?')
      setStreaming(false)
      es.close()
    }
  }

  const stop = () => {
    abortRef.current?.()
    setStreaming(false)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Query bar */}
      <div className="shrink-0 p-4 border-b border-gray-800 bg-gray-900">
        <div className="flex gap-2 items-center max-w-3xl mx-auto">
          <SearchIcon size={16} className="text-gray-500 shrink-0" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submit()}
            placeholder="Ask a question about your papers…"
            className="flex-1 bg-gray-800 text-gray-100 text-sm rounded px-3 py-2 placeholder-gray-500 outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <select
            value={topK}
            onChange={e => setTopK(Number(e.target.value))}
            className="bg-gray-800 text-gray-400 text-xs rounded px-2 py-2 outline-none"
          >
            {[3, 5, 10, 20].map(k => <option key={k} value={k}>top {k}</option>)}
          </select>
          {streaming ? (
            <button onClick={stop} className="flex items-center gap-1.5 px-3 py-2 rounded bg-red-800 hover:bg-red-700 text-sm text-white">
              <StopCircle size={13} /> Stop
            </button>
          ) : (
            <button onClick={submit} disabled={!query.trim()} className="flex items-center gap-1.5 px-3 py-2 rounded bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-sm text-white transition-colors">
              <Send size={13} /> Ask
            </button>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4 max-w-3xl mx-auto w-full space-y-5">
        {error && (
          <div className="p-3 rounded-lg bg-red-950 border border-red-800 text-red-300 text-sm">{error}</div>
        )}

        {/* Answer */}
        {(answer || streaming) && (
          <div className="rounded-xl bg-gray-900 border border-gray-800 p-4">
            <h3 className="text-xs font-semibold text-indigo-400 uppercase tracking-wider mb-2">Answer</h3>
            <p className="text-sm text-gray-200 leading-relaxed whitespace-pre-wrap">
              {answer}
              {streaming && <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse ml-0.5 align-middle" />}
            </p>
            {sources.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                <p className="text-xs text-gray-500">
                  Sources: {sources.join(' · ')}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Retrieved chunks */}
        {chunks.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Retrieved chunks ({chunks.length})
            </h3>
            <div className="space-y-2">
              {chunks.map((chunk, i) => (
                <div key={chunk.id ?? i} className="rounded-lg bg-gray-900 border border-gray-800 p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1.5">
                      <FileText size={11} className="text-gray-600" />
                      <span className="text-xs text-gray-500">{chunk.section}</span>
                    </div>
                    <span className="text-xs text-gray-600 font-mono">{chunk.score?.toFixed(3)}</span>
                  </div>
                  <p className="text-xs text-gray-300 leading-relaxed line-clamp-4">{chunk.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {!answer && !streaming && chunks.length === 0 && !error && (
          <div className="flex flex-col items-center justify-center h-48 text-gray-600 gap-2">
            <SearchIcon size={32} className="opacity-20" />
            <p className="text-sm">Ask a question to search your document graph</p>
          </div>
        )}
      </div>
    </div>
  )
}
