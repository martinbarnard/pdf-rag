import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import Spinner from '../components/Spinner'
import ErrorBox from '../components/ErrorBox'
import { FileText, ChevronRight, User, Tag } from 'lucide-react'

interface Paper {
  id: string
  title: string
  year: number
  doi: string
  abstract: string
}

interface PaperDetail {
  authors: Array<{ id: string; canonical_name: string }>
  topics: Array<{ id: string; canonical_name: string }>
  citing: Array<{ id: string; title: string }>
  cited: Array<{ id: string; title: string }>
}

function PaperCard({ paper, onSelect, selected }: {
  paper: Paper
  onSelect: (p: Paper) => void
  selected: boolean
}) {
  return (
    <button
      onClick={() => onSelect(paper)}
      className={`w-full text-left px-4 py-3 border-b border-gray-800 hover:bg-gray-800/50 transition-colors ${
        selected ? 'bg-indigo-950/40 border-l-2 border-l-indigo-500' : ''
      }`}
    >
      <div className="flex items-start gap-2">
        <FileText size={14} className="text-indigo-400 mt-0.5 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-gray-100 leading-snug line-clamp-2">{paper.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">{paper.year || '—'}</p>
        </div>
        <ChevronRight size={13} className="text-gray-600 ml-auto mt-0.5 shrink-0" />
      </div>
    </button>
  )
}

export default function PaperBrowser() {
  const { data: papers, loading, error } = useApi<Paper[]>('/api/graph/overview')
  const [selected, setSelected] = useState<Paper | null>(null)
  const [query, setQuery] = useState('')

  // Extract papers from overview nodes
  const allPapers: Paper[] = papers
    ? (papers as unknown as { nodes: Array<{ data: { id: string; label: string; type: string; year?: number; doi?: string; abstract?: string } }> })
        .nodes
        .filter(n => n.data.type === 'Paper')
        .map(n => ({
          id: n.data.id,
          title: n.data.label,
          year: n.data.year ?? 0,
          doi: n.data.doi ?? '',
          abstract: n.data.abstract ?? '',
        }))
    : []

  const filtered = allPapers.filter(p =>
    p.title.toLowerCase().includes(query.toLowerCase())
  )

  const { data: detail } = useApi<PaperDetail>(
    selected ? `/api/graph/overview` : '',
    [selected?.id]
  )

  return (
    <div className="flex h-full">
      {/* List */}
      <div className="w-80 shrink-0 border-r border-gray-800 flex flex-col">
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
          {filtered.length === 0 && !loading && (
            <p className="p-4 text-xs text-gray-500">No papers found.</p>
          )}
          {filtered.map(p => (
            <PaperCard
              key={p.id}
              paper={p}
              onSelect={setSelected}
              selected={selected?.id === p.id}
            />
          ))}
        </div>
      </div>

      {/* Detail */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selected ? (
          <div className="flex h-full items-center justify-center text-gray-600 text-sm">
            Select a paper to view details
          </div>
        ) : (
          <div className="max-w-2xl space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-gray-100 leading-snug">{selected.title}</h2>
              <div className="flex gap-3 mt-1.5 text-xs text-gray-500">
                {selected.year > 0 && <span>{selected.year}</span>}
                {selected.doi && <a href={`https://doi.org/${selected.doi}`} target="_blank" rel="noreferrer" className="text-indigo-400 hover:underline">{selected.doi}</a>}
              </div>
            </div>

            {selected.abstract && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Abstract</h3>
                <p className="text-sm text-gray-300 leading-relaxed">{selected.abstract}</p>
              </div>
            )}

            {detail && (
              <>
                <Section icon={<User size={13} />} title="Authors">
                  {(detail as unknown as PaperDetail).authors?.map(a => (
                    <Chip key={a.id} label={a.canonical_name} colour="green" />
                  ))}
                </Section>
                <Section icon={<Tag size={13} />} title="Topics">
                  {(detail as unknown as PaperDetail).topics?.map(t => (
                    <Chip key={t.id} label={t.canonical_name} colour="amber" />
                  ))}
                </Section>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
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

function Chip({ label, colour }: { label: string; colour: 'green' | 'amber' | 'indigo' }) {
  const cls = {
    green:  'bg-green-950 text-green-300 border-green-900',
    amber:  'bg-amber-950 text-amber-300 border-amber-900',
    indigo: 'bg-indigo-950 text-indigo-300 border-indigo-900',
  }[colour]
  return (
    <span className={`px-2 py-0.5 rounded border text-xs ${cls}`}>{label}</span>
  )
}
