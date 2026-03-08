import { useState, useRef } from 'react'
import { Upload, CheckCircle, XCircle, Loader } from 'lucide-react'

interface IngestResult {
  file: string
  status: 'pending' | 'running' | 'done' | 'error'
  message?: string
  chunk_count?: number
  entity_count?: number
  citation_count?: number
}

export default function IngestUI() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [items, setItems] = useState<IngestResult[]>([])
  const [running, setRunning] = useState(false)
  const [dragging, setDragging] = useState(false)

  const addFiles = (files: FileList | null) => {
    if (!files) return
    const newItems: IngestResult[] = Array.from(files).map(f => ({
      file: f.name,
      status: 'pending',
    }))
    setItems(prev => [...prev, ...newItems])
  }

  const ingestAll = async () => {
    const pending = items.filter(i => i.status === 'pending')
    if (!pending.length) return
    setRunning(true)

    for (const item of pending) {
      setItems(prev => prev.map(i => i.file === item.file ? { ...i, status: 'running' } : i))
      try {
        const fileInput = inputRef.current
        const file = Array.from(fileInput?.files ?? []).find(f => f.name === item.file)
        if (!file) throw new Error('File not found in input')

        const form = new FormData()
        form.append('file', file)

        const res = await fetch('/api/ingest', { method: 'POST', body: form })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `${res.status}`)
        }
        const data = await res.json()
        setItems(prev => prev.map(i =>
          i.file === item.file
            ? { ...i, status: 'done', chunk_count: data.chunk_count, entity_count: data.entity_count, citation_count: data.citation_count }
            : i
        ))
      } catch (e) {
        setItems(prev => prev.map(i =>
          i.file === item.file
            ? { ...i, status: 'error', message: e instanceof Error ? e.message : String(e) }
            : i
        ))
      }
    }
    setRunning(false)
  }

  const clearDone = () => setItems(prev => prev.filter(i => i.status === 'pending' || i.status === 'running'))

  return (
    <div className="h-full flex flex-col p-6 gap-5 overflow-y-auto">
      <div>
        <h2 className="text-base font-semibold text-gray-100">Ingest documents</h2>
        <p className="text-xs text-gray-500 mt-0.5">PDF, DOCX, Markdown, HTML, LaTeX</p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl py-12 cursor-pointer transition-colors ${
          dragging
            ? 'border-indigo-500 bg-indigo-950/30'
            : 'border-gray-700 hover:border-gray-600 bg-gray-900'
        }`}
      >
        <Upload size={28} className="text-gray-500" />
        <p className="text-sm text-gray-400">Drop files here or <span className="text-indigo-400">browse</span></p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.md,.html,.htm,.tex"
          className="hidden"
          onChange={e => addFiles(e.target.files)}
        />
      </div>

      {/* Queue */}
      {items.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Queue ({items.length})</h3>
            <button onClick={clearDone} className="text-xs text-gray-600 hover:text-gray-400">Clear done</button>
          </div>
          {items.map((item, idx) => (
            <div key={idx} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-gray-900 border border-gray-800">
              <StatusIcon status={item.status} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200 truncate">{item.file}</p>
                {item.status === 'done' && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    {item.chunk_count} chunks · {item.entity_count} entities · {item.citation_count} citations
                  </p>
                )}
                {item.status === 'error' && (
                  <p className="text-xs text-red-400 mt-0.5">{item.message}</p>
                )}
              </div>
              <span className={`text-xs font-medium ${statusColour(item.status)}`}>
                {item.status}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={ingestAll}
          disabled={running || !items.some(i => i.status === 'pending')}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-sm text-white font-medium transition-colors"
        >
          {running && <Loader size={13} className="animate-spin" />}
          Ingest all
        </button>
        <button
          onClick={() => setItems([])}
          disabled={running}
          className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-sm text-gray-300 transition-colors"
        >
          Clear queue
        </button>
      </div>
    </div>
  )
}

function StatusIcon({ status }: { status: IngestResult['status'] }) {
  if (status === 'done')    return <CheckCircle size={16} className="text-green-400 shrink-0" />
  if (status === 'error')   return <XCircle size={16} className="text-red-400 shrink-0" />
  if (status === 'running') return <Loader size={16} className="text-indigo-400 animate-spin shrink-0" />
  return <div className="w-4 h-4 rounded-full border border-gray-600 shrink-0" />
}

function statusColour(status: IngestResult['status']) {
  return { pending: 'text-gray-500', running: 'text-indigo-400', done: 'text-green-400', error: 'text-red-400' }[status]
}
