import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import cytoscape from 'cytoscape'
import type { Core, NodeSingular } from 'cytoscape'
import fcose from 'cytoscape-fcose'
import { LayoutGrid, RefreshCw, X, ChevronDown, Search, Download, ExternalLink } from 'lucide-react'
import Spinner from '../components/Spinner'
import ErrorBox from '../components/ErrorBox'
import { attachDragNeighbours } from '../utils/cyDragNeighbours'
import { GRAPH_STYLESHEET } from '../utils/cyStylesheet'

cytoscape.use(fcose)

const NODE_COLOURS: Record<string, string> = {
  Paper:  '#6366f1',
  Author: '#22c55e',
  Topic:  '#f59e0b',
  GhostPaper:  '#818cf8',
  GhostAuthor: '#4ade80',
  GhostTopic:  '#fbbf24',
}

interface CyNode { data: { id: string; label: string; type: string; status?: string } }
interface CyEdge { data: { id: string; source: string; target: string; label: string } }
interface OverviewData { nodes: CyNode[]; edges: CyEdge[] }

interface ArxivResult {
  arxiv_id: string
  title: string
  authors: string[]
  abstract: string
  published: string
  categories: string[]
  pdf_url: string
  similarity_score: number
}

// Rich detail fetched from the DB for real nodes
interface NodeDetail {
  // Paper fields
  abstract?: string
  summary?: string
  year?: number
  doi?: string
  arxiv_id?: string
  file_path?: string
  authors?: { id: string; canonical_name: string }[]
  topics?: { id: string; canonical_name: string }[]
  cited_by?: number
  cites?: number
  // Author fields
  papers?: { id: string; title: string; year: number }[]
  coauthors?: { id: string; canonical_name: string; shared: number }[]
  // Topic fields
  related?: { id: string; canonical_name: string; weight: number }[]
}

type Layout = 'fcose' | 'breadthfirst' | 'circle'
const LAYOUTS: { key: Layout; label: string }[] = [
  { key: 'fcose',        label: 'Force'  },
  { key: 'breadthfirst', label: 'Tree'   },
  { key: 'circle',       label: 'Circle' },
]

// Ghost node IDs must not contain colons — cytoscape uses IDs as CSS selectors
// internally and colons are invalid there.
const ghostPaperId  = (arxiv_id: string) => `arxiv__${arxiv_id}`
const ghostAuthorId = (name: string)     => `ghost_author__${name.replace(/\s+/g, '_')}`
const ghostTopicId  = (cat: string)      => `ghost_topic__${cat}`

export default function GraphExplorer() {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef        = useRef<Core | null>(null)
  const overviewRef  = useRef<OverviewData | null>(null)
  const expandedRef  = useRef<Set<string>>(new Set())
  const layoutRef    = useRef<Layout>('fcose')
  // Map ghostPaperId → ArxivResult for the detail panel
  const ghostResultsRef = useRef<Map<string, ArxivResult>>(new Map())

  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState<string | null>(null)
  const [layout,  setLayout]  = useState<Layout>('fcose')
  useEffect(() => { layoutRef.current = layout }, [layout])

  const [selected,     setSelected]     = useState<{ id: string; type: string; label: string } | null>(null)
  const [nodeDetail,   setNodeDetail]   = useState<NodeDetail | null>(null)
  const [detailLoading,setDetailLoading]= useState(false)
  const [ghostDetail,  setGhostDetail]  = useState<ArxivResult | null>(null)
  const [expanding,    setExpanding]    = useState(false)

  // arXiv drawer (toolbar search + related search)
  const [arxivPanelOpen,  setArxivPanelOpen]  = useState(false)
  const [arxivQuery,      setArxivQuery]      = useState('')
  const [arxivSearching,  setArxivSearching]  = useState(false)
  const [arxivResults,    setArxivResults]    = useState<ArxivResult[]>([])
  const [arxivAttribution,setArxivAttribution]= useState('')
  const [arxivError,      setArxivError]      = useState<string | null>(null)

  // arXiv search results shown inline in the node detail panel (for ghost author/topic)
  const [panelArxivResults,  setPanelArxivResults]  = useState<ArxivResult[]>([])
  const [panelArxivSearching,setPanelArxivSearching]= useState(false)

  const [ingestState, setIngestState] = useState<Record<string, 'idle' | 'ingesting' | 'done' | 'error'>>({})

  const navigate = useNavigate()

  const runLayout = useCallback((cy: Core, name: Layout) => {
    cy.layout({
      name,
      animate: true,
      animationDuration: 500,
      ...(name === 'fcose' ? {
        quality: 'proof',
        randomize: false,
        nodeDimensionsIncludeLabels: true,
        nodeRepulsion: 18000,
        idealEdgeLength: 150,
        edgeElasticity: 0.3,
        gravity: 0.2,
        gravityRange: 3.8,
        numIter: 5000,
        tile: true,
        tilingPaddingVertical: 30,
        tilingPaddingHorizontal: 30,
      } : {}),
    } as cytoscape.LayoutOptions).run()
  }, [])

  /**
   * Add elements then run a local sub-layout on the new nodes + their
   * immediate neighbourhood so they slot in without overlapping.
   * Nodes outside the affected set are locked during the animation.
   */
  const addAndSettle = useCallback((
    cy: Core,
    toAdd: cytoscape.ElementDefinition[],
    anchorId: string | null,
  ) => {
    if (!toAdd.length) return

    // Position new nodes near the anchor before adding so they don't all land at (0,0)
    if (anchorId) {
      const anchor = cy.getElementById(anchorId)
      if (anchor.length) {
        const ap = anchor.position()
        const newNodes = toAdd.filter(el => !('source' in el.data))
        const angleStep = (2 * Math.PI) / Math.max(newNodes.length, 1)
        const radius = 120 + newNodes.length * 15
        newNodes.forEach((el, i) => {
          el.position = {
            x: ap.x + radius * Math.cos(i * angleStep),
            y: ap.y + radius * Math.sin(i * angleStep),
          }
        })
      }
    }

    cy.add(toAdd)

    // Collect the affected neighbourhood for the local re-settle
    const newNodeIds = new Set(
      toAdd.filter(el => !('source' in el.data)).map(el => el.data.id as string)
    )
    const affected = cy.collection()
    newNodeIds.forEach(id => {
      const n = cy.getElementById(id)
      if (n.length) affected.merge(n.closedNeighborhood().nodes())
    })
    if (anchorId) {
      const anchor = cy.getElementById(anchorId)
      if (anchor.length) affected.merge(anchor.closedNeighborhood().nodes())
    }

    if (affected.length < 2) {
      runLayout(cy, layoutRef.current)
      return
    }

    cy.nodes().not(affected).lock()
    try {
      affected.layout({
        name: 'fcose',
        animate: true,
        animationDuration: 450,
        fit: false,
        quality: 'proof',
        randomize: false,
        nodeDimensionsIncludeLabels: true,
        nodeRepulsion: 18000,
        idealEdgeLength: 140,
        edgeElasticity: 0.3,
        gravity: 0.15,
        numIter: 3000,
        ...(anchorId ? {
          fixedNodeConstraint: [
            { nodeId: anchorId, position: cy.getElementById(anchorId).position() },
          ],
        } : {}),
      } as cytoscape.LayoutOptions).run()
    } finally {
      setTimeout(() => cy.nodes().unlock(), 500)
    }
  }, [runLayout])

  const addGhostResults = useCallback((results: ArxivResult[], anchorId: string | null = null) => {
    const cy = cyRef.current

    // Always populate the map regardless of whether the graph is ready
    for (const r of results) {
      ghostResultsRef.current.set(ghostPaperId(r.arxiv_id), r)
    }

    if (!cy) return

    const toAdd: cytoscape.ElementDefinition[] = []

    for (const r of results) {
      const paperId = ghostPaperId(r.arxiv_id)

      if (!cy.getElementById(paperId).length) {
        toAdd.push({ data: { id: paperId, label: r.title, type: 'GhostPaper' } })
      }

      for (const author of r.authors.slice(0, 3)) {
        const authorId = ghostAuthorId(author)
        if (!cy.getElementById(authorId).length)
          toAdd.push({ data: { id: authorId, label: author, type: 'GhostAuthor' } })
        const edgeId = `ghost_au__${paperId}__${authorId}`
        if (!cy.getElementById(edgeId).length)
          toAdd.push({ data: { id: edgeId, source: authorId, target: paperId, ghost: 'true' } })
      }

      for (const cat of r.categories.slice(0, 3)) {
        const topicId = ghostTopicId(cat)
        if (!cy.getElementById(topicId).length)
          toAdd.push({ data: { id: topicId, label: cat, type: 'GhostTopic' } })
        const edgeId = `ghost_tp__${paperId}__${topicId}`
        if (!cy.getElementById(edgeId).length)
          toAdd.push({ data: { id: edgeId, source: paperId, target: topicId, ghost: 'true' } })
      }
    }

    if (toAdd.length) {
      addAndSettle(cy, toAdd, anchorId)
    }
  }, [addAndSettle])

  const searchArxiv = useCallback(async (terms: string[], author = '') => {
    setArxivSearching(true)
    setArxivError(null)
    try {
      const resp = await fetch('/api/arxiv/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ terms, author, top_k: 15 }),
      })
      if (!resp.ok) throw new Error(`${resp.status}`)
      const data = await resp.json()
      setArxivResults(data.results)
      setArxivAttribution(data.attribution)
      addGhostResults(data.results)
    } catch (e) {
      setArxivError(String(e))
    } finally {
      setArxivSearching(false)
    }
  }, [addGhostResults])

  const searchRelatedArxiv = useCallback(async (paperId: string) => {
    setArxivSearching(true)
    setArxivError(null)
    setArxivPanelOpen(true)
    try {
      const resp = await fetch(`/api/papers/${paperId}/related-arxiv?strategy=all&top_k=15`)
      if (!resp.ok) throw new Error(`${resp.status}`)
      const data = await resp.json()
      setArxivResults(data.results)
      setArxivAttribution(data.attribution)
      addGhostResults(data.results, paperId)
    } catch (e) {
      setArxivError(String(e))
    } finally {
      setArxivSearching(false)
    }
  }, [addGhostResults])

  /** Fetch DB detail for a real node and populate the panel. */
  const fetchNodeDetail = useCallback(async (id: string, type: string) => {
    setDetailLoading(true)
    setNodeDetail(null)
    try {
      if (type === 'Paper') {
        const r = await fetch(`/api/papers/${encodeURIComponent(id)}`)
        if (r.ok) setNodeDetail(await r.json())
      } else if (type === 'Author') {
        const [papersR, coR] = await Promise.all([
          fetch(`/api/authors/${encodeURIComponent(id)}/papers`),
          fetch(`/api/authors/${encodeURIComponent(id)}/coauthors`),
        ])
        const papers   = papersR.ok   ? await papersR.json()   : []
        const coauthors= coR.ok       ? await coR.json()       : []
        setNodeDetail({ papers, coauthors })
      } else if (type === 'Topic') {
        const [papersR, relR] = await Promise.all([
          fetch(`/api/topics/${encodeURIComponent(id)}/papers`),
          fetch(`/api/topics/${encodeURIComponent(id)}/related`),
        ])
        const papers  = papersR.ok ? await papersR.json() : []
        const related = relR.ok   ? await relR.json()    : []
        setNodeDetail({ papers, related })
      }
    } finally {
      setDetailLoading(false)
    }
  }, [])

  /** arXiv search shown inline in the node detail panel (ghost author/topic tap). */
  const searchPanelArxiv = useCallback(async (terms: string[], author = '') => {
    setPanelArxivSearching(true)
    setPanelArxivResults([])
    try {
      const resp = await fetch('/api/arxiv/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ terms, author, top_k: 10 }),
      })
      if (!resp.ok) throw new Error(`${resp.status}`)
      const data = await resp.json()
      setPanelArxivResults(data.results)
      addGhostResults(data.results)
    } finally {
      setPanelArxivSearching(false)
    }
  }, [addGhostResults])

  const ingestGhost = useCallback(async (arxiv_id: string) => {
    setIngestState(s => ({ ...s, [arxiv_id]: 'ingesting' }))
    try {
      const resp = await fetch('/api/arxiv/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ arxiv_id }),
      })
      if (!resp.ok) throw new Error(`${resp.status}`)
      const { job_id } = await resp.json()

      const poll = async () => {
        const r = await fetch(`/api/ingest/jobs/${job_id}`)
        if (!r.ok) return
        const job = await r.json()
        if (job.status === 'done') {
          setIngestState(s => ({ ...s, [arxiv_id]: 'done' }))
          const cy = cyRef.current
          if (cy && job.paper_id) {
            const ghostId = ghostPaperId(arxiv_id)
            const ghostNode = cy.getElementById(ghostId)
            if (ghostNode.length) {
              cy.remove(cy.edges(`[source = "${ghostId}"]`))
              cy.remove(cy.edges(`[target = "${ghostId}"]`))
              cy.remove(ghostNode)
            }
            const ovResp = await fetch('/api/graph/overview')
            if (ovResp.ok) {
              const newData: OverviewData = await ovResp.json()
              overviewRef.current = newData
              const newPaperNode = newData.nodes.find(n => n.data.id === job.paper_id)
              if (newPaperNode && !cy.getElementById(job.paper_id).length) {
                addAndSettle(cy, [{ data: newPaperNode.data }], null)
              }
            }
          }
        } else if (job.status === 'error') {
          setIngestState(s => ({ ...s, [arxiv_id]: 'error' }))
        } else {
          setTimeout(poll, 1500)
        }
      }
      setTimeout(poll, 1500)
    } catch {
      setIngestState(s => ({ ...s, [arxiv_id]: 'error' }))
    }
  }, [addAndSettle])

  useEffect(() => {
    if (!containerRef.current) return
    setLoading(true)

    fetch('/api/graph/overview')
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then((data: OverviewData) => {
        overviewRef.current = data
        expandedRef.current = new Set()

        // Stub papers from the DB are rendered as GhostPaper nodes on load
        const paperNodes = data.nodes
          .filter(n => n.data.type === 'Paper')
          .map(n => n.data.status === 'stub'
            ? { ...n, data: { ...n.data, type: 'GhostPaper' } }
            : n
          )
        const cy = cytoscape({
          container: containerRef.current!,
          elements: paperNodes,
          style: GRAPH_STYLESHEET,
        })
        cyRef.current = cy
        attachDragNeighbours(cy)

        cy.on('tap', 'node', (evt) => {
          const node = evt.target as NodeSingular
          const id    = node.id()
          const type  = node.data('type') as string
          const label = node.data('label') as string
          setSelected({ id, type, label })
          setNodeDetail(null)
          setGhostDetail(null)
          setPanelArxivResults([])

          if (type === 'GhostPaper') {
            const cached = ghostResultsRef.current.get(id) ?? null
            if (cached) {
              setGhostDetail(cached)
            } else {
              // DB-origin stub: fetch detail lazily from the API
              fetch(`/api/papers/${encodeURIComponent(id)}`)
                .then(r => r.ok ? r.json() : null)
                .then((paper: any) => {
                  if (!paper) return
                  const synthetic: ArxivResult = {
                    arxiv_id: paper.arxiv_id || '',
                    title: paper.title || '',
                    authors: (paper.authors || []).map((a: any) => a.canonical_name || a.name || ''),
                    abstract: paper.abstract || '',
                    published: paper.year ? `${paper.year}-01-01` : '',
                    categories: (paper.topics || []).map((t: any) => t.canonical_name || t.name || ''),
                    pdf_url: paper.arxiv_id ? `https://arxiv.org/pdf/${paper.arxiv_id}` : (paper.file_path || ''),
                    similarity_score: 0,
                  }
                  ghostResultsRef.current.set(id, synthetic)
                  setGhostDetail(synthetic)
                })
                .catch(() => {})
            }
            return
          }

          if (type === 'GhostAuthor') {
            // Strip ghost prefix to get real name, search arXiv inline
            const name = label
            searchPanelArxiv([], name)
            return
          }

          if (type === 'GhostTopic') {
            searchPanelArxiv([label])
            return
          }

          // Real node — fetch detail and auto-expand
          fetchNodeDetail(id, type)

          if (!expandedRef.current.has(id)) {
            const toAdd: cytoscape.ElementDefinition[] = []
            const edges = data.edges.filter(e => e.data.source === id || e.data.target === id)
            for (const edge of edges) {
              const nbId = edge.data.source === id ? edge.data.target : edge.data.source
              const nbNode = data.nodes.find(n => n.data.id === nbId)
              if (nbNode && !cy.getElementById(nbId).length)
                toAdd.push({ data: nbNode.data })
              if (!cy.getElementById(edge.data.id).length)
                toAdd.push({ data: edge.data })
            }
            if (toAdd.length) { addAndSettle(cy, toAdd, id) }
            expandedRef.current.add(id)
          }
        })

        cy.on('tap', (evt) => {
          if (evt.target === cy) {
            setSelected(null)
            setGhostDetail(null)
            setNodeDetail(null)
            setPanelArxivResults([])
          }
        })

        cy.on('cxttap', 'node', (evt) => {
          const node  = evt.target as NodeSingular
          const type  = node.data('type') as string
          const label = node.data('label') as string
          const id    = node.id()

          if (type === 'Topic' || type === 'GhostTopic') {
            setArxivPanelOpen(true)
            setArxivQuery(label)
            searchArxiv([label])
          } else if (type === 'Author' || type === 'GhostAuthor') {
            setArxivPanelOpen(true)
            setArxivQuery(label)
            searchArxiv([], label)
          } else if (type === 'Paper') {
            setArxivPanelOpen(true)
            searchRelatedArxiv(id)
          }
        })

        runLayout(cy, 'fcose')
        setLoading(false)
      })
      .catch(e => { setError(String(e)); setLoading(false) })

    return () => { cyRef.current?.destroy(); cyRef.current = null }
  }, [runLayout, addAndSettle, searchArxiv, searchRelatedArxiv, fetchNodeDetail, searchPanelArxiv])

  useEffect(() => {
    if (cyRef.current) runLayout(cyRef.current, layout)
  }, [layout, runLayout])

  const expandNode = useCallback(async () => {
    if (!selected || !cyRef.current || !overviewRef.current) return
    if (expandedRef.current.has(selected.id)) return
    setExpanding(true)
    try {
      const cy   = cyRef.current
      const data = overviewRef.current
      const toAdd: cytoscape.ElementDefinition[] = []
      const connectedEdges = data.edges.filter(
        e => e.data.source === selected.id || e.data.target === selected.id
      )
      for (const edge of connectedEdges) {
        const nbId = edge.data.source === selected.id ? edge.data.target : edge.data.source
        const nbNode = data.nodes.find(n => n.data.id === nbId)
        if (nbNode && !cy.getElementById(nbId).length)
          toAdd.push({ data: nbNode.data })
        if (!cy.getElementById(edge.data.id).length)
          toAdd.push({ data: edge.data })
      }
      if (toAdd.length) { addAndSettle(cy, toAdd, selected.id) }
      expandedRef.current.add(selected.id)
    } finally {
      setExpanding(false)
    }
  }, [selected, addAndSettle])

  const goToDetail = useCallback(() => {
    if (!selected) return
    if (selected.type === 'Author') navigate(`/authors/${selected.id}`)
    if (selected.type === 'Topic')  navigate(`/topics/${selected.id}`)
    if (selected.type === 'Paper')  navigate(`/papers?id=${selected.id}`)
  }, [selected, navigate])

  const isExpanded = selected ? expandedRef.current.has(selected.id) : false
  const isGhost    = selected?.type?.startsWith('Ghost') ?? false

  // ── Ingest button shared renderer ───────────────────────────────────────────
  const IngestBtn = ({ arxiv_id }: { arxiv_id: string }) => {
    const state = ingestState[arxiv_id] ?? 'idle'
    if (state === 'done')  return <span className="text-xs text-green-400">Ingested ✓</span>
    if (state === 'error') return <span className="text-xs text-red-400">Ingest failed</span>
    return (
      <button
        onClick={() => ingestGhost(arxiv_id)}
        disabled={state === 'ingesting'}
        className="flex items-center gap-1 px-2.5 py-1.5 rounded bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50 text-xs text-white transition-colors">
        {state === 'ingesting'
          ? <><RefreshCw size={11} className="animate-spin" /> Ingesting…</>
          : <><Download size={11} /> Ingest</>}
      </button>
    )
  }

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
        <span className="text-xs text-gray-500">Click node for details · Right-click to search arXiv</span>

        <div className="ml-auto flex items-center gap-2">
          <form onSubmit={e => {
            e.preventDefault()
            if (arxivQuery.trim()) { setArxivPanelOpen(true); searchArxiv(arxivQuery.trim().split(/\s+/)) }
          }} className="flex items-center gap-1">
            <input
              value={arxivQuery}
              onChange={e => setArxivQuery(e.target.value)}
              placeholder="Search arXiv…"
              className="px-2 py-1 rounded bg-gray-800 border border-gray-700 text-xs text-gray-200 placeholder-gray-600 w-36 focus:outline-none focus:border-indigo-500"
            />
            <button type="submit" className="p-1.5 rounded bg-indigo-700 hover:bg-indigo-600 text-white">
              <Search size={13} />
            </button>
          </form>
          <button onClick={() => cyRef.current?.fit(undefined, 40)} title="Fit graph"
            className="p-1.5 rounded bg-gray-800 text-gray-400 hover:bg-gray-700">
            <LayoutGrid size={14} />
          </button>
        </div>
      </div>

      {/* Canvas + panels */}
      <div className="flex flex-1 overflow-hidden relative">
        {loading && (
          <div className="absolute inset-0 z-10 bg-gray-950/80 flex items-center justify-center">
            <Spinner label="Loading graph…" />
          </div>
        )}
        {error && <ErrorBox message={error} />}
        <div ref={containerRef} className="flex-1 bg-gray-950" />

        {/* ── Node detail panel ───────────────────────────────────────── */}
        {selected && (
          <div className="w-72 shrink-0 bg-gray-900 border-l border-gray-800 flex flex-col overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-800 shrink-0 flex items-start justify-between gap-2">
              <div className="min-w-0">
                <span className="inline-block px-2 py-0.5 rounded text-xs font-medium mb-1"
                  style={{ background: (NODE_COLOURS[selected.type] ?? '#6b7280') + '33', color: NODE_COLOURS[selected.type] ?? '#e5e7eb' }}>
                  {isGhost ? `arXiv ${selected.type.replace('Ghost', '')}` : selected.type}
                </span>
                <p className="text-sm font-semibold text-gray-100 leading-snug">{selected.label}</p>
              </div>
              <button onClick={() => { setSelected(null); setGhostDetail(null); setNodeDetail(null); setPanelArxivResults([]) }}
                className="text-gray-600 hover:text-gray-300 shrink-0 mt-0.5"><X size={14} /></button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">

              {/* ── Ghost Paper ── */}
              {selected.type === 'GhostPaper' && (() => {
                const d = ghostDetail ?? ghostResultsRef.current.get(selected.id) ?? null
                if (!d) return (
                  <div className="flex items-center justify-center py-6">
                    <Spinner label="Loading…" />
                  </div>
                )
                const arxivUrl = d.arxiv_id ? `https://arxiv.org/abs/${d.arxiv_id}` : d.pdf_url
                return (
                  <>
                    {d.abstract && (
                      <div>
                        <p className="text-xs font-medium text-gray-400 mb-1">Abstract</p>
                        <p className="text-xs text-gray-300 leading-relaxed">{d.abstract}</p>
                      </div>
                    )}
                    {d.authors.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-400 mb-1">Authors</p>
                        <p className="text-xs text-gray-300">{d.authors.join(', ')}</p>
                      </div>
                    )}
                    {d.categories.length > 0 && (
                      <div>
                        <p className="text-xs font-medium text-gray-400 mb-1">Categories</p>
                        <p className="text-xs text-gray-300">{d.categories.join(', ')}</p>
                      </div>
                    )}
                    {d.published && (
                      <p className="text-xs text-gray-500">{d.published.slice(0, 4)}</p>
                    )}
                    <div className="flex flex-col gap-2 pt-1">
                      <IngestBtn arxiv_id={d.arxiv_id} />
                      {arxivUrl && (
                        <a href={arxivUrl} target="_blank" rel="noreferrer"
                          className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300">
                          <ExternalLink size={11} /> View on arXiv
                        </a>
                      )}
                    </div>
                  </>
                )
              })()}

              {/* ── Ghost Author: inline arXiv search ── */}
              {selected.type === 'GhostAuthor' && (
                <>
                  <p className="text-xs text-gray-400">Papers by this author on arXiv:</p>
                  {panelArxivSearching && <Spinner label="Searching…" />}
                  {panelArxivResults.map(r => (
                    <div key={r.arxiv_id} className="border border-gray-800 rounded p-2.5 flex flex-col gap-1.5">
                      <p className="text-xs font-medium text-gray-100 leading-snug">{r.title}</p>
                      <p className="text-xs text-gray-500">{r.published.slice(0, 4)} · {r.categories.slice(0, 2).join(', ')}</p>
                      <p className="text-xs text-gray-400 line-clamp-2">{r.abstract}</p>
                      <div className="flex items-center gap-2 pt-0.5">
                        <IngestBtn arxiv_id={r.arxiv_id} />
                        <a href={`https://arxiv.org/abs/${r.arxiv_id}`} target="_blank" rel="noreferrer"
                          className="flex items-center gap-0.5 text-xs text-indigo-400 hover:text-indigo-300">
                          <ExternalLink size={10} /> arXiv
                        </a>
                      </div>
                    </div>
                  ))}
                  {!panelArxivSearching && panelArxivResults.length === 0 && (
                    <p className="text-xs text-gray-600 italic">No results</p>
                  )}
                </>
              )}

              {/* ── Ghost Topic: inline arXiv search ── */}
              {selected.type === 'GhostTopic' && (
                <>
                  <p className="text-xs text-gray-400">arXiv papers on this topic:</p>
                  {panelArxivSearching && <Spinner label="Searching…" />}
                  {panelArxivResults.map(r => (
                    <div key={r.arxiv_id} className="border border-gray-800 rounded p-2.5 flex flex-col gap-1.5">
                      <p className="text-xs font-medium text-gray-100 leading-snug">{r.title}</p>
                      <p className="text-xs text-gray-500">
                        {r.authors.slice(0, 2).join(', ')}{r.authors.length > 2 ? ' et al.' : ''} · {r.published.slice(0, 4)}
                      </p>
                      <p className="text-xs text-gray-400 line-clamp-2">{r.abstract}</p>
                      <div className="flex items-center gap-2 pt-0.5">
                        <IngestBtn arxiv_id={r.arxiv_id} />
                        <a href={`https://arxiv.org/abs/${r.arxiv_id}`} target="_blank" rel="noreferrer"
                          className="flex items-center gap-0.5 text-xs text-indigo-400 hover:text-indigo-300">
                          <ExternalLink size={10} /> arXiv
                        </a>
                      </div>
                    </div>
                  ))}
                  {!panelArxivSearching && panelArxivResults.length === 0 && (
                    <p className="text-xs text-gray-600 italic">No results</p>
                  )}
                </>
              )}

              {/* ── Real Paper ── */}
              {selected.type === 'Paper' && (
                <>
                  {detailLoading && <Spinner label="Loading…" />}
                  {nodeDetail && (
                    <>
                      {(nodeDetail.abstract || nodeDetail.summary) && (
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1">Abstract</p>
                          <p className="text-xs text-gray-300 leading-relaxed line-clamp-6">
                            {nodeDetail.abstract || nodeDetail.summary}
                          </p>
                        </div>
                      )}
                      {nodeDetail.authors && nodeDetail.authors.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1">Authors</p>
                          <div className="flex flex-wrap gap-1">
                            {nodeDetail.authors.map(a => (
                              <span key={a.id} className="px-1.5 py-0.5 rounded bg-green-900/40 text-green-300 text-xs">
                                {a.canonical_name}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {nodeDetail.topics && nodeDetail.topics.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1">Topics</p>
                          <div className="flex flex-wrap gap-1">
                            {nodeDetail.topics.map(t => (
                              <span key={t.id} className="px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-300 text-xs">
                                {t.canonical_name}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      <div className="flex gap-4 text-xs text-gray-500">
                        {nodeDetail.year && <span>{nodeDetail.year}</span>}
                        {nodeDetail.cited_by != null && <span>Cited by {nodeDetail.cited_by}</span>}
                        {nodeDetail.cites   != null && <span>Cites {nodeDetail.cites}</span>}
                      </div>
                      {nodeDetail.doi && (
                        <a href={`https://doi.org/${nodeDetail.doi}`} target="_blank" rel="noreferrer"
                          className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300">
                          <ExternalLink size={11} /> DOI
                        </a>
                      )}
                    </>
                  )}
                  <div className="flex flex-col gap-2 pt-1 border-t border-gray-800">
                    {!isExpanded ? (
                      <button onClick={expandNode} disabled={expanding}
                        className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-sm text-gray-200 transition-colors">
                        {expanding ? <RefreshCw size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                        Expand neighbours
                      </button>
                    ) : (
                      <p className="text-xs text-gray-600 text-center">Neighbours shown</p>
                    )}
                    <button
                      onClick={() => { setArxivPanelOpen(true); searchRelatedArxiv(selected.id) }}
                      className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm text-gray-200 transition-colors">
                      <Search size={13} /> Related on arXiv
                    </button>
                    <button onClick={goToDetail}
                      className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 text-sm text-white transition-colors">
                      Open full view →
                    </button>
                  </div>
                </>
              )}

              {/* ── Real Author ── */}
              {selected.type === 'Author' && (
                <>
                  {detailLoading && <Spinner label="Loading…" />}
                  {nodeDetail && (
                    <>
                      {nodeDetail.papers && nodeDetail.papers.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1">Papers ({nodeDetail.papers.length})</p>
                          <div className="flex flex-col gap-1">
                            {nodeDetail.papers.slice(0, 8).map((p: any) => (
                              <p key={p.id} className="text-xs text-gray-300 leading-snug">
                                {p.title || p.id}
                                {p.year ? <span className="text-gray-600 ml-1">({p.year})</span> : null}
                              </p>
                            ))}
                            {nodeDetail.papers.length > 8 && (
                              <p className="text-xs text-gray-600">+{nodeDetail.papers.length - 8} more</p>
                            )}
                          </div>
                        </div>
                      )}
                      {nodeDetail.coauthors && nodeDetail.coauthors.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1">Co-authors</p>
                          <div className="flex flex-wrap gap-1">
                            {nodeDetail.coauthors.slice(0, 10).map((a: any) => (
                              <span key={a.id} className="px-1.5 py-0.5 rounded bg-green-900/40 text-green-300 text-xs">
                                {a.canonical_name}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                  <div className="flex flex-col gap-2 pt-1 border-t border-gray-800">
                    {!isExpanded ? (
                      <button onClick={expandNode} disabled={expanding}
                        className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-sm text-gray-200 transition-colors">
                        {expanding ? <RefreshCw size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                        Expand neighbours
                      </button>
                    ) : (
                      <p className="text-xs text-gray-600 text-center">Neighbours shown</p>
                    )}
                    <button
                      onClick={() => { setArxivPanelOpen(true); setArxivQuery(selected.label); searchArxiv([], selected.label) }}
                      className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm text-gray-200 transition-colors">
                      <Search size={13} /> Search arXiv
                    </button>
                    <button onClick={goToDetail}
                      className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 text-sm text-white transition-colors">
                      Open full view →
                    </button>
                  </div>
                </>
              )}

              {/* ── Real Topic ── */}
              {selected.type === 'Topic' && (
                <>
                  {detailLoading && <Spinner label="Loading…" />}
                  {nodeDetail && (
                    <>
                      {nodeDetail.papers && nodeDetail.papers.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1">Papers ({nodeDetail.papers.length})</p>
                          <div className="flex flex-col gap-1">
                            {nodeDetail.papers.slice(0, 8).map((p: any) => (
                              <p key={p.id} className="text-xs text-gray-300 leading-snug">
                                {p.title || p.id}
                                {p.year ? <span className="text-gray-600 ml-1">({p.year})</span> : null}
                              </p>
                            ))}
                            {nodeDetail.papers.length > 8 && (
                              <p className="text-xs text-gray-600">+{nodeDetail.papers.length - 8} more</p>
                            )}
                          </div>
                        </div>
                      )}
                      {nodeDetail.related && nodeDetail.related.length > 0 && (
                        <div>
                          <p className="text-xs font-medium text-gray-400 mb-1">Related topics</p>
                          <div className="flex flex-wrap gap-1">
                            {nodeDetail.related.slice(0, 10).map((t: any) => (
                              <span key={t.id} className="px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-300 text-xs">
                                {t.canonical_name}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                  <div className="flex flex-col gap-2 pt-1 border-t border-gray-800">
                    {!isExpanded ? (
                      <button onClick={expandNode} disabled={expanding}
                        className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-sm text-gray-200 transition-colors">
                        {expanding ? <RefreshCw size={13} className="animate-spin" /> : <ChevronDown size={13} />}
                        Expand neighbours
                      </button>
                    ) : (
                      <p className="text-xs text-gray-600 text-center">Neighbours shown</p>
                    )}
                    <button
                      onClick={() => { setArxivPanelOpen(true); setArxivQuery(selected.label); searchArxiv([selected.label]) }}
                      className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-gray-700 hover:bg-gray-600 text-sm text-gray-200 transition-colors">
                      <Search size={13} /> Search arXiv
                    </button>
                    <button onClick={goToDetail}
                      className="flex items-center justify-center gap-2 px-3 py-2 rounded bg-indigo-700 hover:bg-indigo-600 text-sm text-white transition-colors">
                      Open full view →
                    </button>
                  </div>
                </>
              )}

            </div>
          </div>
        )}

        {/* ── arXiv results drawer (toolbar search / right-click) ─────── */}
        {arxivPanelOpen && (
          <div className="w-80 shrink-0 bg-gray-900 border-l border-gray-800 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 shrink-0">
              <span className="text-sm font-medium text-gray-200">arXiv results</span>
              <button onClick={() => setArxivPanelOpen(false)} className="text-gray-600 hover:text-gray-300">
                <X size={14} />
              </button>
            </div>

            {arxivSearching && (
              <div className="flex-1 flex items-center justify-center">
                <Spinner label="Searching arXiv…" />
              </div>
            )}
            {arxivError && <div className="p-4"><ErrorBox message={arxivError} /></div>}

            {!arxivSearching && !arxivError && (
              <div className="flex-1 overflow-y-auto divide-y divide-gray-800">
                {arxivResults.length === 0 && (
                  <p className="p-4 text-xs text-gray-500 text-center">No results</p>
                )}
                {arxivResults.map(r => {
                  const state = ingestState[r.arxiv_id] ?? 'idle'
                  return (
                    <div key={r.arxiv_id} className="p-3 flex flex-col gap-1.5">
                      <p className="text-xs font-medium text-gray-100 leading-snug">{r.title}</p>
                      <p className="text-xs text-gray-500">
                        {r.authors.slice(0, 2).join(', ')}{r.authors.length > 2 ? ' et al.' : ''} · {r.published.slice(0, 4)}
                      </p>
                      <p className="text-xs text-gray-400 line-clamp-2">{r.abstract}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {state === 'done' ? (
                          <span className="text-xs text-green-400">Ingested ✓</span>
                        ) : state === 'error' ? (
                          <span className="text-xs text-red-400">Failed</span>
                        ) : (
                          <button
                            onClick={() => ingestGhost(r.arxiv_id)}
                            disabled={state === 'ingesting'}
                            className="flex items-center gap-1 px-2 py-1 rounded bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50 text-xs text-white transition-colors">
                            {state === 'ingesting'
                              ? <><RefreshCw size={10} className="animate-spin" /> Ingesting…</>
                              : <><Download size={10} /> Ingest</>}
                          </button>
                        )}
                        <a href={`https://arxiv.org/abs/${r.arxiv_id}`} target="_blank" rel="noreferrer"
                          className="flex items-center gap-0.5 text-xs text-indigo-400 hover:text-indigo-300">
                          <ExternalLink size={10} /> arXiv
                        </a>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {arxivAttribution && (
              <p className="px-3 py-2 text-xs text-gray-600 border-t border-gray-800 shrink-0">
                {arxivAttribution}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
