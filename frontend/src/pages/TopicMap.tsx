import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { useApi } from '../hooks/useApi'
import Spinner from '../components/Spinner'
import ErrorBox from '../components/ErrorBox'
import { Tag, ChevronRight } from 'lucide-react'
import { attachDragNeighbours } from '../utils/cyDragNeighbours'
import { GRAPH_STYLESHEET } from '../utils/cyStylesheet'

cytoscape.use(fcose)

interface Topic { id: string; label: string }
interface Related { id: string; canonical_name: string; weight: number }
interface OverviewData {
  nodes: Array<{ data: { id: string; label: string; type: string } }>
  edges: Array<{ data: { id: string; source: string; target: string; label: string } }>
}

const FCOSE_OPTS = {
  name: 'fcose',
  animate: true,
  animationDuration: 400,
  nodeDimensionsIncludeLabels: true,
  nodeRepulsion: 5000,
  idealEdgeLength: 100,
  edgeElasticity: 0.4,
  gravity: 0.25,
} as cytoscape.LayoutOptions

export default function TopicMap() {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const overviewRef = useRef<OverviewData | null>(null)
  const expandedRef = useRef<Set<string>>(new Set())
  const navigate = useNavigate()
  const { data: overview, loading, error } = useApi<OverviewData>('/api/graph/overview')
  const [selected, setSelected] = useState<Topic | null>(null)
  const { data: related } = useApi<Related[]>(
    selected ? `/api/topics/${selected.id}/related` : '',
    [selected?.id]
  )

  useEffect(() => {
    if (!overview || !containerRef.current) return

    overviewRef.current = overview
    expandedRef.current = new Set()

    const topicNodes = overview.nodes.filter(n => n.data.type === 'Topic')
    const topicIds = new Set(topicNodes.map(n => n.data.id))
    const topicEdges = overview.edges.filter(
      e => topicIds.has(e.data.source) && topicIds.has(e.data.target)
    )

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...topicNodes, ...topicEdges],
      style: GRAPH_STYLESHEET,
    })

    cy.layout(FCOSE_OPTS).run()
    attachDragNeighbours(cy)

    cy.on('tap', 'node', evt => {
      const node = evt.target as NodeSingular
      setSelected({ id: node.id(), label: node.data('label') })

      // Auto-expand: add connected papers from overview on first tap
      if (!expandedRef.current.has(node.id()) && overviewRef.current) {
        const data = overviewRef.current
        const toAdd: cytoscape.ElementDefinition[] = []
        const edges = data.edges.filter(
          e => e.data.source === node.id() || e.data.target === node.id()
        )
        for (const edge of edges) {
          const neighbourId = edge.data.source === node.id() ? edge.data.target : edge.data.source
          const neighbourNode = data.nodes.find(n => n.data.id === neighbourId)
          if (neighbourNode && !cy.getElementById(neighbourId).length)
            toAdd.push({ data: neighbourNode.data })
          if (!cy.getElementById(edge.data.id).length)
            toAdd.push({ data: edge.data })
        }
        if (toAdd.length) { cy.add(toAdd); cy.layout(FCOSE_OPTS).run() }
        expandedRef.current.add(node.id())
      }
    })
    cy.on('tap', evt => { if (evt.target === cy) setSelected(null) })

    cyRef.current = cy
    return () => { cy.destroy(); cyRef.current = null }
  }, [overview])

  return (
    <div className="flex h-full">
      <div className="flex-1 relative bg-gray-950">
        {loading && <div className="absolute inset-0 flex items-center justify-center"><Spinner label="Loading topics…" /></div>}
        {error && <ErrorBox message={error} />}
        <div ref={containerRef} className="w-full h-full" />
      </div>

      {selected && (
        <div className="w-60 shrink-0 bg-gray-900 border-l border-gray-800 p-4 overflow-y-auto">
          <div className="flex items-center gap-2 mb-3">
            <Tag size={14} className="text-amber-400" />
            <h3 className="text-sm font-semibold text-gray-100">{selected.label}</h3>
          </div>
          <button
            onClick={() => navigate(`/topics/${selected.id}`)}
            className="w-full mb-3 px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 text-sm text-white transition-colors text-center">
            Open topic graph →
          </button>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Related topics</h4>
          {!related || related.length === 0
            ? <p className="text-xs text-gray-600">No related topics.</p>
            : (
              <ul className="space-y-1">
                {related.map(r => (
                  <li key={r.id} className="flex items-center justify-between text-xs text-gray-300">
                    <span className="flex items-center gap-1.5">
                      <ChevronRight size={11} className="text-gray-600" />
                      {r.canonical_name}
                    </span>
                    <span className="text-gray-600">{r.weight.toFixed(2)}</span>
                  </li>
                ))}
              </ul>
            )
          }
        </div>
      )}
    </div>
  )
}
