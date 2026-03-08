import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import Spinner from '../components/Spinner'
import ErrorBox from '../components/ErrorBox'
import { FileText, ChevronRight, User, Tag, Quote, BookOpen, FileSearch, ChevronDown, ChevronUp, Download, ChevronLeft as PrevIcon, ChevronRight as NextIcon } from 'lucide-react'
import * as pdfjsLib from 'pdfjs-dist'

// Point the worker at the bundled worker copy served from /app/assets/
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface PaperSummary {
  id: string
  label: string
  type: string
  year: number
  doi: string
}

interface PaperDetail {
  id: string
  title: string
  abstract: string
  year: number
  doi: string
  file_path: string
  authors: Array<{ id: string; canonical_name: string }>
  topics: Array<{ id: string; canonical_name: string }>
  cited_by: number
  cites: number
}

interface OverviewData {
  nodes: Array<{ data: PaperSummary & { type: string } }>
}

function Chip({ label, colour, onClick }: { label: string; colour: 'green' | 'amber' | 'indigo'; onClick?: () => void }) {
  const cls = {
    green:  'bg-green-950 text-green-300 border border-green-900',
    amber:  'bg-amber-950 text-amber-300 border border-amber-900',
    indigo: 'bg-indigo-950 text-indigo-300 border border-indigo-900',
  }[colour]
  if (onClick)
    return <button onClick={onClick} className={`px-2 py-0.5 rounded text-xs ${cls} hover:brightness-125 transition-all cursor-pointer`}>{label}</button>
  return <span className={`px-2 py-0.5 rounded text-xs ${cls}`}>{label}</span>
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="flex items-center gap-1.5 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
        {icon}{title}
      </h3>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  )
}

function PdfViewer({ paperId, filename }: { paperId: string; filename: string }) {
  const [open, setOpen] = useState(false)
  const [pageNum, setPageNum] = useState(1)
  const [numPages, setNumPages] = useState(0)
  const [rendering, setRendering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const pdfRef = useRef<pdfjsLib.PDFDocumentProxy | null>(null)
  const url = `/api/papers/${paperId}/pdf`

  // Load PDF when opened
  useEffect(() => {
    if (!open) return
    let cancelled = false
    setError(null)
    pdfjsLib.getDocument(url).promise.then(pdf => {
      if (cancelled) return
      pdfRef.current = pdf
      setNumPages(pdf.numPages)
      setPageNum(1)
    }).catch(e => {
      if (!cancelled) setError(String(e.message ?? e))
    })
    return () => { cancelled = true }
  }, [open, url])

  // Render current page whenever pageNum or pdf changes
  useEffect(() => {
    const pdf = pdfRef.current
    const canvas = canvasRef.current
    if (!pdf || !canvas || !open) return
    let cancelled = false
    setRendering(true)
    pdf.getPage(pageNum).then(page => {
      if (cancelled) return
      const viewport = page.getViewport({ scale: 1.5 })
      canvas.width = viewport.width
      canvas.height = viewport.height
      return page.render({ canvasContext: canvas.getContext('2d')!, viewport, canvas }).promise
    }).then(() => {
      if (!cancelled) setRendering(false)
    }).catch(e => {
      if (!cancelled) { setError(String(e.message ?? e)); setRendering(false) }
    })
    return () => { cancelled = true }
  }, [pageNum, numPages, open])

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      {/* Header bar */}
      <div className="flex items-center bg-gray-900 border-b border-gray-800">
        <button
          onClick={() => setOpen(o => !o)}
          className="flex-1 flex items-center justify-between px-4 py-2.5 hover:bg-gray-800 transition-colors text-sm text-gray-300"
        >
          <span className="flex items-center gap-2">
            <FileSearch size={14} className="text-indigo-400" />
            View PDF
          </span>
          {open ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
        </button>
        <a
          href={url}
          download={filename}
          className="flex items-center gap-1.5 px-3 py-2.5 text-xs text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors border-l border-gray-800"
          title="Download PDF"
        >
          <Download size={13} />
          Download
        </a>
      </div>

      {/* PDF canvas */}
      {open && (
        <div className="bg-gray-950">
          {error && <p className="p-4 text-sm text-red-400">{error}</p>}
          {!error && (
            <>
              <div className="overflow-auto" style={{ maxHeight: '70vh' }}>
                <canvas ref={canvasRef} className="mx-auto block" />
                {rendering && (
                  <div className="absolute inset-0 flex items-center justify-center bg-gray-950/60">
                    <Spinner label="Rendering…" />
                  </div>
                )}
              </div>
              {numPages > 1 && (
                <div className="flex items-center justify-center gap-3 py-2 border-t border-gray-800 text-sm text-gray-400">
                  <button
                    onClick={() => setPageNum(p => Math.max(1, p - 1))}
                    disabled={pageNum <= 1}
                    className="p-1 hover:text-gray-100 disabled:opacity-30"
                  >
                    <PrevIcon size={16} />
                  </button>
                  <span>Page {pageNum} of {numPages}</span>
                  <button
                    onClick={() => setPageNum(p => Math.min(numPages, p + 1))}
                    disabled={pageNum >= numPages}
                    className="p-1 hover:text-gray-100 disabled:opacity-30"
                  >
                    <NextIcon size={16} />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function PaperBrowser() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { data: overview, loading, error } = useApi<OverviewData>('/api/graph/overview')
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get('id'))
  const [query, setQuery] = useState('')

  const allPapers = overview
    ? overview.nodes.filter(n => n.data.type === 'Paper').map(n => n.data)
    : []

  const filtered = allPapers.filter(p =>
    p.label.toLowerCase().includes(query.toLowerCase())
  )

  const { data: detail, loading: detailLoading } = useApi<PaperDetail>(
    selectedId ? `/api/papers/${selectedId}` : '',
    [selectedId]
  )

  const isPdf = detail?.file_path?.toLowerCase().endsWith('.pdf') ?? false

  return (
    <div className="flex h-full">
      {/* Paper list */}
      <div className="w-80 shrink-0 border-r border-gray-800 flex flex-col bg-gray-900">
        <div className="p-3 border-b border-gray-800">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search papers…"
            className="w-full bg-gray-800 text-gray-100 text-sm rounded px-3 py-1.5 placeholder-gray-500 outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading && <Spinner label="Loading papers…" />}
          {error && <ErrorBox message={error} />}
          {!loading && filtered.length === 0 && (
            <p className="p-4 text-xs text-gray-500">No papers found.</p>
          )}
          {filtered.map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedId(p.id)}
              className={`w-full text-left px-4 py-3 border-b border-gray-800 hover:bg-gray-800/60 transition-colors ${
                selectedId === p.id ? 'border-l-2 border-l-indigo-500 bg-indigo-950/30' : 'border-l-2 border-l-transparent'
              }`}
            >
              <div className="flex items-start gap-2">
                <FileText size={13} className="text-indigo-400 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-100 leading-snug line-clamp-2">{p.label}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{p.year || '—'}</p>
                </div>
                <ChevronRight size={13} className="text-gray-600 mt-0.5 shrink-0" />
              </div>
            </button>
          ))}
        </div>
        <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-600">
          {filtered.length} paper{filtered.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Detail panel */}
      <div className="flex-1 overflow-y-auto p-6 bg-gray-950">
        {!selectedId ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-gray-600">
              <BookOpen size={40} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">Select a paper to view details</p>
            </div>
          </div>
        ) : detailLoading ? (
          <Spinner label="Loading paper…" />
        ) : detail ? (
          <div className="max-w-2xl space-y-6">
            {/* Header */}
            <div>
              <h2 className="text-lg font-semibold text-gray-100 leading-snug">{detail.title}</h2>
              <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-500">
                {detail.year > 0 && (
                  <span className="flex items-center gap-1">{detail.year}</span>
                )}
                {detail.doi && (
                  <a
                    href={`https://doi.org/${detail.doi}`}
                    target="_blank" rel="noreferrer"
                    className="text-indigo-400 hover:underline"
                  >
                    {detail.doi}
                  </a>
                )}
              </div>
              {/* Citation counts */}
              <div className="flex gap-4 mt-3">
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <Quote size={12} className="text-gray-600" />
                  <span>Cited by <strong className="text-gray-200">{detail.cited_by}</strong></span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-gray-400">
                  <Quote size={12} className="text-gray-600 scale-x-[-1]" />
                  <span>Cites <strong className="text-gray-200">{detail.cites}</strong></span>
                </div>
              </div>
            </div>

            {/* Abstract */}
            {detail.abstract && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Abstract</h3>
                <p className="text-sm text-gray-300 leading-relaxed">{detail.abstract}</p>
              </div>
            )}

            {/* Authors */}
            {detail.authors.length > 0 && (
              <Section icon={<User size={12} />} title="Authors">
                {detail.authors.map(a => (
                  <Chip key={a.id} label={a.canonical_name} colour="green"
                    onClick={() => navigate(`/authors/${a.id}`)} />
                ))}
              </Section>
            )}

            {/* Topics */}
            {detail.topics.length > 0 && (
              <Section icon={<Tag size={12} />} title="Topics">
                {detail.topics.map(t => (
                  <Chip key={t.id} label={t.canonical_name} colour="amber"
                    onClick={() => navigate(`/topics/${t.id}`)} />
                ))}
              </Section>
            )}

            {/* PDF viewer */}
            {isPdf && <PdfViewer paperId={detail.id} filename={detail.file_path.split('/').pop() ?? 'paper.pdf'} />}

            {/* File path */}
            {detail.file_path && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Source file</h3>
                <p className="text-xs text-gray-600 font-mono break-all">{detail.file_path}</p>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}
