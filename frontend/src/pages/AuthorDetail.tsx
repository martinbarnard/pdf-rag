import { useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { useApi } from '../hooks/useApi'
import Spinner from '../components/Spinner'
import ErrorBox from '../components/ErrorBox'
import { User, ArrowLeft, FileText } from 'lucide-react'
import { attachDragNeighbours } from '../utils/cyDragNeighbours'
import { buildDetailStylesheet } from '../utils/cyStylesheet'

cytoscape.use(fcose)

interface Paper { id: string; title?: string; label?: string }
interface Coauthor { id: string; canonical_name: string }

const COLOURS = { paper: '#6366f1', author: '#22c55e', current: '#e11d48' }
const DETAIL_STYLE = buildDetailStylesheet({
  current: COLOURS.current,
  paper: COLOURS.paper,
  secondary: COLOURS.author,
  secondaryIcon: 'author',
})

export default function AuthorDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  const { data: meta } = useApi<{ id: string; canonical_name: string }>(
    id ? `/api/authors/${id}` : '', [id]
  )
  const { data: papers, loading: lpap, error: epap } = useApi<Paper[]>(
    id ? `/api/authors/${id}/papers` : '', [id]
  )
  const { data: coauthors, loading: lco } = useApi<Coauthor[]>(
    id ? `/api/authors/${id}/coauthors` : '', [id]
  )

  const buildGraph = useCallback(() => {
    if (!containerRef.current || !papers || !coauthors || !meta) return
    cyRef.current?.destroy()

    const nodes: cytoscape.ElementDefinition[] = []
    const edges: cytoscape.ElementDefinition[] = []

    // Central author node
    nodes.push({ data: { id: id!, label: meta?.canonical_name ?? id!, nodeType: 'current' } })

    for (const p of papers) {
      const label = p.title ?? p.label ?? p.id
      if (!nodes.find(n => n.data.id === p.id))
        nodes.push({ data: { id: p.id, label, nodeType: 'paper' } })
      edges.push({ data: { id: `ap-${id}-${p.id}`, source: id!, target: p.id } })
    }

    for (const c of coauthors) {
      if (!nodes.find(n => n.data.id === c.id))
        nodes.push({ data: { id: c.id, label: c.canonical_name, nodeType: 'author' } })
      edges.push({ data: { id: `ca-${id}-${c.id}`, source: id!, target: c.id } })
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      style: DETAIL_STYLE,
    })

    cy.layout({ name: 'fcose', animate: true, animationDuration: 400 } as cytoscape.LayoutOptions).run()

    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular
      const ntype = node.data('nodeType')
      if (ntype === 'paper') navigate(`/papers?id=${node.id()}`)
      if (ntype === 'author' && node.id() !== id) navigate(`/authors/${node.id()}`)
    })

    cyRef.current = cy
    attachDragNeighbours(cy)
  }, [papers, coauthors, meta, id, navigate])

  useEffect(() => {
    buildGraph()
    return () => { cyRef.current?.destroy(); cyRef.current = null }
  }, [buildGraph])

  const loading = lpap || lco

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-900 border-b border-gray-800 shrink-0">
        <Link to="/graph" className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-100 transition-colors">
          <ArrowLeft size={13} /> Graph
        </Link>
        <div className="w-px h-4 bg-gray-700" />
        <User size={13} className="text-green-400" />
        <span className="text-sm font-medium text-gray-200 truncate max-w-xs">{meta?.canonical_name ?? id}</span>
        {papers && (
          <span className="ml-auto text-xs text-gray-500">
            {papers.length} paper{papers.length !== 1 ? 's' : ''}{coauthors && coauthors.length > 0 ? ` · ${coauthors.length} co-authors` : ''}
          </span>
        )}
      </div>

      {/* Canvas */}
      <div className="flex-1 relative bg-gray-950">
        {loading && (
          <div className="absolute inset-0 z-10 bg-gray-950/80 flex items-center justify-center">
            <Spinner label="Building graph…" />
          </div>
        )}
        {epap && <ErrorBox message={epap} />}
        {!loading && papers?.length === 0 && coauthors?.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-600">
            <div className="text-center">
              <FileText size={36} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No connected nodes found for this author.</p>
            </div>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  )
}
