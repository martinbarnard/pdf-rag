import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { LayoutGrid, RefreshCw, X, ChevronDown } from 'lucide-react'
import Spinner from '../components/Spinner'
import ErrorBox from '../components/ErrorBox'

cytoscape.use(fcose)

const NODE_COLOURS: Record<string, string> = {
  Paper:  '#6366f1',
  Author: '#22c55e',
  Topic:  '#f59e0b',
}

interface CyNode { data: { id: string; label: string; type: string } }
interface CyEdge { data: { id: string; source: string; target: string; label: string } }
interface OverviewData { nodes: CyNode[]; edges: CyEdge[] }

type Layout = 'fcose' | 'breadthfirst' | 'circle'
const LAYOUTS: { key: Layout; label: string }[] = [
  { key: 'fcose',        label: 'Force'  },
  { key: 'breadthfirst', label: 'Tree'   },
  { key: 'circle',       label: 'Circle' },
]

const STYLESHEET: cytoscape.StylesheetJson = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'font-size': 10,
      color: '#e5e7eb',
      'text-valign': 'bottom',
      'text-margin-y': 4,
      'text-max-width': '80px',
      'text-wrap': 'ellipsis',
      width: 28,
      height: 28,
      'background-color': '#6b7280',
      'border-width': 0,
    },
  },
  { selector: 'node[type="Paper"]',  style: { 'background-color': '#6366f1' } },
  { selector: 'node[type="Author"]', style: { 'background-color': '#22c55e' } },
  { selector: 'node[type="Topic"]',  style: { 'background-color': '#f59e0b' } },
  { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#ffffff' } },
  {
    selector: 'edge',
    style: {
      'line-color': '#4b5563',
      'target-arrow-color': '#4b5563',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 0.8,
      width: 1.5,
      'curve-style': 'bezier',
    },
  },
]

export default function GraphExplorer() {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  // full overview kept in memory for edge lookups when expanding
  const overviewRef = useRef<OverviewData | null>(null)
  const expandedRef = useRef<Set<string>>(new Set())

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [layout, setLayout] = useState<Layout>('fcose')
  const [selected, setSelected] = useState<{ id: string; type: string; label: string } | null>(null)
  const [expanding, setExpanding] = useState(false)
  const navigate = useNavigate()

  const runLayout = useCallback((cy: Core, name: Layout) => {
    cy.layout({
      name,
      animate: true,
      animationDuration: 400,
      ...(name === 'fcose' ? { quality: 'default', randomize: false } : {}),
    } as cytoscape.LayoutOptions).run()
  }, [])

  // Seed graph with paper nodes only
  useEffect(() => {
    if (!containerRef.current) return
    setLoading(true)

    fetch('/api/graph/overview')
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then((data: OverviewData) => {
        overviewRef.current = data
        expandedRef.current = new Set()

        const paperNodes = data.nodes.filter(n => n.data.type === 'Paper')
        const cy = cytoscape({
          container: containerRef.current!,
          elements: paperNodes,
          style: STYLESHEET,
        })
        cyRef.current = cy

        cy.on('tap', 'node', (evt) => {
          const node = evt.target as NodeSingular
          setSelected({ id: node.id(), type: node.data('type'), label: node.data('label') })
        })
        cy.on('tap', (evt) => { if (evt.target === cy) setSelected(null) })

        runLayout(cy, 'fcose')
        setLoading(false)
      })
      .catch(e => { setError(String(e)); setLoading(false) })

    return () => { cyRef.current?.destroy(); cyRef.current = null }
  }, [runLayout])

  useEffect(() => {
    if (cyRef.current) runLayout(cyRef.current, layout)
  }, [layout, runLayout])

  // Expand a paper node to show its authors + topics (and edges from overview)
  const expandNode = useCallback(async () => {
    if (!selected || !cyRef.current || !overviewRef.current) return
    if (expandedRef.current.has(selected.id)) return  // already expanded

    setExpanding(true)
    try {
      const cy = cyRef.current
      const data = overviewRef.current
      const toAdd: cytoscape.ElementDefinition[] = []

      if (selected.type === 'Paper') {
        // Add connected Authors and Topics from the pre-loaded overview
        const connectedEdges = data.edges.filter(
          e => e.data.source === selected.id || e.data.target === selected.id
        )
        for (const edge of connectedEdges) {
          const neighbourId = edge.data.source === selected.id ? edge.data.target : edge.data.source
          const neighbourNode = data.nodes.find(n => n.data.id === neighbourId)
          if (neighbourNode && !cy.getElementById(neighbourId).length)
            toAdd.push({ data: neighbourNode.data })
          if (!cy.getElementById(edge.data.id).length)
            toAdd.push({ data: edge.data })
        }
      } else {
        // For Author/Topic nodes: pull in their papers from the overview edges
        const connectedEdges = data.edges.filter(
          e => e.data.source === selected.id || e.data.target === selected.id
        )
        for (const edge of connectedEdges) {
          const neighbourId = edge.data.source === selected.id ? edge.data.target : edge.data.source
          const neighbourNode = data.nodes.find(n => n.data.id === neighbourId)
          if (neighbourNode && !cy.getElementById(neighbourId).length)
            toAdd.push({ data: neighbourNode.data })
          if (!cy.getElementById(edge.data.id).length)
            toAdd.push({ data: edge.data })
        }
      }

      if (toAdd.length) {
        cy.add(toAdd)
        runLayout(cy, layout)
      }
      expandedRef.current.add(selected.id)
    } finally {
      setExpanding(false)
    }
  }, [selected, layout, runLayout])

  const goToDetail = useCallback(() => {
    if (!selected) return
    if (selected.type === 'Author') navigate(`/authors/${selected.id}`)
    if (selected.type === 'Topic')  navigate(`/topics/${selected.id}`)
    if (selected.type === 'Paper')  navigate(`/papers?id=${selected.id}`)
  }, [selected, navigate])

  const isExpanded = selected ? expandedRef.current.has(selected.id) : false

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-gray-900 border-b border-gray-800 shrink-0">
        <div className="flex gap-1">
          {LAYOUTS.map(l => (
            <button key={l.key} onClick={() => setLayout(l.key)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${layout === l.key ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}>
              {l.label}
            </button>
          ))}
        </div>
        <div className="w-px h-5 bg-gray-700" />
        <span className="text-xs text-gray-500">Click a paper to expand its authors & topics</span>
        <div className="ml-auto">
          <button onClick={() => cyRef.current?.fit(undefined, 40)} title="Fit"
            className="p-1.5 rounded bg-gray-800 text-gray-400 hover:bg-gray-700">
            <LayoutGrid size={14} />
          </button>
        </div>
      </div>

      {/* Canvas + panel */}
      <div className="flex flex-1 overflow-hidden relative">
        {loading && (
          <div className="absolute inset-0 z-10 bg-gray-950/80 flex items-center justify-center">
            <Spinner label="Loading graph…" />
          </div>
        )}
        {error && <ErrorBox message={error} />}
        <div ref={containerRef} className="flex-1 bg-gray-950" />

        {selected && (
          <div className="w-64 shrink-0 bg-gray-900 border-l border-gray-800 p-4 flex flex-col gap-3 overflow-y-auto">
            <div className="flex items-start justify-between">
              <div>
                <span className="inline-block px-2 py-0.5 rounded text-xs font-medium mb-1"
                  style={{ background: (NODE_COLOURS[selected.type] ?? '#6b7280') + '33', color: NODE_COLOURS[selected.type] ?? '#e5e7eb' }}>
                  {selected.type}
                </span>
                <p className="text-sm font-medium text-gray-100 leading-snug">{selected.label}</p>
              </div>
              <button onClick={() => setSelected(null)} className="text-gray-600 hover:text-gray-300"><X size={14} /></button>
            </div>

            {/* Expand neighbours */}
            {!isExpanded && (
              <button onClick={expandNode} disabled={expanding}
                className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-sm text-gray-200 transition-colors">
                {expanding ? <RefreshCw size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                Expand neighbours
              </button>
            )}
            {isExpanded && (
              <p className="text-xs text-gray-600 text-center">Neighbours shown</p>
            )}

            {/* Open detail view */}
            <button onClick={goToDetail}
              className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 text-sm text-white transition-colors">
              Open detail view →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
