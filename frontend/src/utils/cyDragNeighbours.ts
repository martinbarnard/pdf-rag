/**
 * Drag behaviour for Cytoscape using d3-force velocity Verlet integration:
 *
 * During drag  — a live d3-force simulation runs on the grabbed node's
 *               neighbourhood.  The dragged node is treated as a fixed
 *               "anchor" whose position is updated each drag event; link
 *               forces pull neighbours toward it with spring tension;
 *               charge forces keep them from colliding; velocity decay
 *               damps oscillation.  The Verlet integrator is stable even
 *               at large time-steps.
 *
 * After drag   — run a local fcose sub-layout on the dropped node + its
 *               immediate neighbourhood so they settle without overlapping,
 *               while the rest of the graph stays put.
 */
import type { Core, NodeSingular } from 'cytoscape'
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceX,
  forceY,
  type Simulation,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force'

// Simulation parameters
const LINK_DISTANCE  = 0   // desired link length (0 = use current distance at grab time)
const LINK_STRENGTH  = 0.3 // spring stiffness (0–1)
const CHARGE         = -80 // charge repulsion between neighbours
const VELOCITY_DECAY = 0.4 // fraction of velocity retained each tick (lower = more damping)
const ALPHA_DECAY    = 0   // don't cool down while dragging — reheat on each drag event
const MAX_DEPTH      = 2   // hops to include in the simulation

interface SimNode extends SimulationNodeDatum {
  id: string
  fixed: boolean   // true for the dragged node — its position is set by the drag event
}

interface SimLink extends SimulationLinkDatum<SimNode> {
  source: SimNode
  target: SimNode
}

function buildGraph(
  root: NodeSingular,
  maxDepth: number,
): { nodes: SimNode[]; links: SimLink[]; nodeMap: Map<string, SimNode> } {
  const nodeMap   = new Map<string, SimNode>()
  const links: SimLink[] = []
  const visited   = new Set<string>([root.id()])

  // Root node is fixed (dragged) — its position is driven by the mouse
  const rootPos   = root.position()
  const rootNode: SimNode = { id: root.id(), x: rootPos.x, y: rootPos.y, fixed: true, fx: rootPos.x, fy: rootPos.y }
  nodeMap.set(root.id(), rootNode)

  let frontier: NodeSingular[] = [root]

  for (let depth = 1; depth <= maxDepth; depth++) {
    const next: NodeSingular[] = []
    for (const cyNode of frontier) {
      const simSrc = nodeMap.get(cyNode.id())!
      cyNode.neighborhood('node').forEach((nb: NodeSingular) => {
        if (!visited.has(nb.id())) {
          visited.add(nb.id())
          const pos = nb.position()
          const simNb: SimNode = { id: nb.id(), x: pos.x, y: pos.y, fixed: false }
          nodeMap.set(nb.id(), simNb)
          next.push(nb)
        }
        // Add link if both endpoints are in our set
        const simNb = nodeMap.get(nb.id())
        if (simNb) {
          // Avoid duplicate links
          const already = links.some(l =>
            (l.source.id === simSrc.id && l.target.id === simNb.id) ||
            (l.source.id === simNb.id && l.target.id === simSrc.id)
          )
          if (!already) links.push({ source: simSrc, target: simNb })
        }
      })
    }
    frontier = next
    if (!frontier.length) break
  }

  return { nodes: Array.from(nodeMap.values()), links, nodeMap }
}

export function attachDragNeighbours(cy: Core): () => void {
  let sim: Simulation<SimNode, SimLink> | null = null
  let nodeMap: Map<string, SimNode>            = new Map()
  let pendingGraph: { nodes: SimNode[]; links: SimLink[] } | null = null
  let rafId: number | null = null
  let settleTimer: ReturnType<typeof setTimeout> | null = null
  let didDrag = false  // true only when the node actually moved after grab

  function cancelAll() {
    if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null }
    if (sim) { sim.stop(); sim = null }
    nodeMap = new Map()
    pendingGraph = null
  }

  /** Write simulation node positions back into Cytoscape each tick. */
  function syncToCy() {
    nodeMap.forEach((sn, id) => {
      if (sn.fixed) return  // dragged node is positioned by the drag event directly
      const n = cy.getElementById(id)
      if (n.length && !n.grabbed() && !n.locked()) {
        n.position({ x: sn.x ?? 0, y: sn.y ?? 0 })
      }
    })
    rafId = null
  }

  function onGrab(evt: cytoscape.EventObject) {
    cancelAll()
    if (settleTimer) { clearTimeout(settleTimer); settleTimer = null }
    didDrag = false
    cy.nodes().unlock()

    const root = evt.target as NodeSingular
    const { nodes, links, nodeMap: nm } = buildGraph(root, MAX_DEPTH)
    nodeMap = nm

    if (nodes.length >= 2) {
      // Store the graph data but don't start the simulation yet.
      // The sim will be created lazily on the first drag event so that
      // a plain click never triggers neighbour movement.
      pendingGraph = { nodes, links }
    }
  }

  function onDrag(evt: cytoscape.EventObject) {
    didDrag = true

    // Lazily start the simulation on the first real drag event
    if (!sim && pendingGraph) {
      const { nodes, links } = pendingGraph
      pendingGraph = null
      sim = forceSimulation<SimNode, SimLink>(nodes)
        .force('link', forceLink<SimNode, SimLink>(links)
          .id(d => d.id)
          .distance(LINK_DISTANCE)
          .strength(LINK_STRENGTH)
        )
        .force('charge', forceManyBody<SimNode>().strength(CHARGE))
        // Weak centering forces on free nodes prevent them flying off to infinity
        .force('x', forceX<SimNode>(d => (d as SimNode).fixed ? (d.x ?? 0) : (d.x ?? 0)).strength(0.05))
        .force('y', forceY<SimNode>(d => (d as SimNode).fixed ? (d.y ?? 0) : (d.y ?? 0)).strength(0.05))
        .velocityDecay(VELOCITY_DECAY)
        .alphaDecay(ALPHA_DECAY)
        .alpha(0.5)
        .on('tick', () => {
          if (rafId === null) rafId = requestAnimationFrame(syncToCy)
        })
    }

    if (!sim || !nodeMap.size) return
    const cur  = (evt.target as NodeSingular).position()
    const root = nodeMap.get((evt.target as NodeSingular).id())
    if (!root) return

    // Move the anchor — the sim's link forces will pull neighbours toward it
    root.fx = cur.x
    root.fy = cur.y
    root.x  = cur.x
    root.y  = cur.y

    // Reheat so neighbours respond vigorously even on slow drags
    sim.alpha(Math.max(sim.alpha(), 0.3)).restart()
  }

  function onFree(evt: cytoscape.EventObject) {
    cancelAll()
    if (!didDrag) return  // plain click — don't touch any node positions
    const droppedNode = evt.target as NodeSingular

    // After a short pause, run a local sub-layout on the dropped node and its
    // 1-hop neighbourhood so they settle and stop overlapping.
    settleTimer = setTimeout(() => {
      settleTimer = null
      const hood     = droppedNode.closedNeighborhood()
      const subNodes = hood.nodes()
      if (subNodes.length < 2) return

      cy.nodes().not(subNodes).lock()
      try {
        subNodes.layout({
          name: 'fcose',
          animate: true,
          animationDuration: 350,
          fit: false,
          quality: 'proof',
          randomize: false,
          nodeDimensionsIncludeLabels: true,
          nodeRepulsion: 12000,
          idealEdgeLength: 100,
          edgeElasticity: 0.35,
          gravity: 0.1,
          numIter: 2500,
          fixedNodeConstraint: [
            { nodeId: droppedNode.id(), position: droppedNode.position() },
          ],
        } as cytoscape.LayoutOptions).run()
      } finally {
        setTimeout(() => cy.nodes().unlock(), 400)
      }
    }, 150)
  }

  cy.on('grab', 'node', onGrab)
  cy.on('drag', 'node', onDrag)
  cy.on('free', 'node', onFree)

  return () => {
    cancelAll()
    if (settleTimer) clearTimeout(settleTimer)
    cy.off('grab', 'node', onGrab)
    cy.off('drag', 'node', onDrag)
    cy.off('free', 'node', onFree)
  }
}
