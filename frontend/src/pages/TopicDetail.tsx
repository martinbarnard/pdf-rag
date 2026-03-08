import { useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { useApi } from '../hooks/useApi'
import Spinner from '../components/Spinner'
import ErrorBox from '../components/ErrorBox'
import { Tag, ArrowLeft, FileText } from 'lucide-react'

cytoscape.use(fcose)

interface Paper { id: string; title?: string; label?: string }
interface Related { id: string; canonical_name: string; weight: number }

const COLOURS = { paper: '#6366f1', topic: '#f59e0b', current: '#e11d48' }

export default function TopicDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  const { data: meta } = useApi<{ id: string; canonical_name: string }>(
    id ? `/api/topics/${id}` : '', [id]
  )
  const { data: papers, loading: lpap, error: epap } = useApi<Paper[]>(
    id ? `/api/topics/${id}/papers` : '', [id]
  )
  const { data: related, loading: lrel } = useApi<Related[]>(
    id ? `/api/topics/${id}/related` : '', [id]
  )

  const topicLabel = meta?.canonical_name ?? id ?? ''

  const buildGraph = useCallback(() => {
    if (!containerRef.current || !papers || !related || !meta) return
    cyRef.current?.destroy()

    const nodes: cytoscape.ElementDefinition[] = []
    const edges: cytoscape.ElementDefinition[] = []

    // Central topic node
    nodes.push({ data: { id: id!, label: topicLabel, nodeType: 'current' } })

    for (const p of papers) {
      const label = p.title ?? p.label ?? p.id
      if (!nodes.find(n => n.data.id === p.id))
        nodes.push({ data: { id: p.id, label, nodeType: 'paper' } })
      edges.push({ data: { id: `tp-${id}-${p.id}`, source: id!, target: p.id } })
    }

    for (const r of related) {
      if (!nodes.find(n => n.data.id === r.id))
        nodes.push({ data: { id: r.id, label: r.canonical_name, nodeType: 'topic' } })
      edges.push({ data: { id: `rt-${id}-${r.id}`, source: id!, target: r.id } })
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'font-size': 10,
            color: '#e5e7eb',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'text-max-width': '90px',
            'text-wrap': 'ellipsis',
            width: 26,
            height: 26,
            'background-color': '#6b7280',
            'border-width': 0,
          },
        },
        { selector: 'node[nodeType="current"]', style: { 'background-color': COLOURS.current, width: 36, height: 36, 'font-size': 12 } },
        { selector: 'node[nodeType="paper"]',   style: { 'background-color': COLOURS.paper } },
        { selector: 'node[nodeType="topic"]',   style: { 'background-color': COLOURS.topic } },
        { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#ffffff' } },
        {
          selector: 'edge',
          style: {
            'line-color': '#374151',
            'target-arrow-color': '#374151',
            'target-arrow-shape': 'triangle',
            'arrow-scale': 0.7,
            width: 1.2,
            'curve-style': 'bezier',
          },
        },
      ] as cytoscape.StylesheetJson,
    })

    cy.layout({ name: 'fcose', animate: true, animationDuration: 400 } as cytoscape.LayoutOptions).run()

    cy.on('tap', 'node', (evt) => {
      const node = evt.target as NodeSingular
      const ntype = node.data('nodeType')
      if (ntype === 'paper') navigate(`/papers?id=${node.id()}`)
      if (ntype === 'topic' && node.id() !== id) navigate(`/topics/${node.id()}`)
    })

    cyRef.current = cy
  }, [papers, related, meta, id, topicLabel, navigate])

  useEffect(() => {
    buildGraph()
    return () => { cyRef.current?.destroy(); cyRef.current = null }
  }, [buildGraph])

  const loading = lpap || lrel

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-900 border-b border-gray-800 shrink-0">
        <Link to="/topics" className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-100 transition-colors">
          <ArrowLeft size={13} /> Topics
        </Link>
        <div className="w-px h-4 bg-gray-700" />
        <Tag size={13} className="text-amber-400" />
        <span className="text-sm font-medium text-gray-200 truncate max-w-xs">{topicLabel}</span>
        {papers && (
          <span className="ml-auto text-xs text-gray-500">
            {papers.length} paper{papers.length !== 1 ? 's' : ''}{related && related.length > 0 ? ` · ${related.length} related topics` : ''}
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
        {!loading && papers?.length === 0 && related?.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-600">
            <div className="text-center">
              <FileText size={36} className="mx-auto mb-2 opacity-30" />
              <p className="text-sm">No connected nodes found for this topic.</p>
            </div>
          </div>
        )}
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  )
}
