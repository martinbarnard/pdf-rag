/**
 * Drag behaviour for Cytoscape:
 *
 * During drag  — connected nodes are pulled along with spring tension (hop falloff).
 * After drag   — run a local fcose sub-layout on the dragged node + its immediate
 *               neighbourhood so they settle without overlapping, while the rest
 *               of the graph stays put.
 */
import type { Core, NodeSingular } from 'cytoscape'

const TENSION  = 0.6   // fraction of delta passed to each successive hop
const MAX_DEPTH = 2    // hops to drag-pull (keep low so distant nodes are stable)

type Snap = { x: number; y: number; factor: number }

function buildSnapMap(_cy: Core, root: NodeSingular, maxDepth: number, tension: number): Map<string, Snap> {
  const map = new Map<string, Snap>()
  const visited = new Set<string>([root.id()])
  let frontier: NodeSingular[] = [root]
  let factor = tension

  for (let depth = 1; depth <= maxDepth; depth++) {
    const next: NodeSingular[] = []
    for (const node of frontier) {
      node.neighborhood('node').forEach((n: NodeSingular) => {
        if (!visited.has(n.id())) {
          visited.add(n.id())
          map.set(n.id(), { ...n.position(), factor })
          next.push(n)
        }
      })
    }
    frontier = next
    factor *= tension
    if (!frontier.length) break
  }
  return map
}

export function attachDragNeighbours(cy: Core): () => void {
  let snapMap: Map<string, Snap> = new Map()
  let grabPos: { x: number; y: number } | null = null
  let settleTimer: ReturnType<typeof setTimeout> | null = null

  function onGrab(evt: cytoscape.EventObject) {
    if (settleTimer) { clearTimeout(settleTimer); settleTimer = null }
    // Unlock everything — a previous settle may have left nodes locked
    cy.nodes().unlock()
    const node = evt.target as NodeSingular
    grabPos = { ...node.position() }
    snapMap = buildSnapMap(cy, node, MAX_DEPTH, TENSION)
  }

  function onDrag(evt: cytoscape.EventObject) {
    if (!grabPos || !snapMap.size) return
    const cur = (evt.target as NodeSingular).position()
    const dx = cur.x - grabPos.x
    const dy = cur.y - grabPos.y
    snapMap.forEach((snap, id) => {
      const n = cy.getElementById(id)
      // Skip nodes that are grabbed (multi-select) or locked
      if (n.length && !n.grabbed() && !n.locked()) {
        n.position({ x: snap.x + dx * snap.factor, y: snap.y + dy * snap.factor })
      }
    })
  }

  function onFree(evt: cytoscape.EventObject) {
    const droppedNode = evt.target as NodeSingular
    snapMap = new Map()
    grabPos = null

    // After a short pause, run a local sub-layout on the dropped node and its
    // 1-hop neighbourhood so they settle and stop overlapping.
    settleTimer = setTimeout(() => {
      settleTimer = null
      const hood = droppedNode.closedNeighborhood()  // node + its edges + neighbours
      const subNodes = hood.nodes()
      if (subNodes.length < 2) return

      // Lock all nodes OUTSIDE the neighbourhood so they don't move
      cy.nodes().not(subNodes).lock()
      try {
        subNodes.layout({
          name: 'fcose',
          animate: true,
          animationDuration: 350,
          quality: 'proof',
          randomize: false,
          nodeDimensionsIncludeLabels: true,
          nodeRepulsion: 12000,
          idealEdgeLength: 100,
          edgeElasticity: 0.35,
          gravity: 0.1,
          numIter: 2500,
          // Keep the dragged node as an anchor so the sub-graph doesn't drift
          fixedNodeConstraint: [
            { nodeId: droppedNode.id(), position: droppedNode.position() },
          ],
        } as cytoscape.LayoutOptions).run()
      } finally {
        // Unlock after animation completes
        setTimeout(() => cy.nodes().unlock(), 400)
      }
    }, 150)
  }

  cy.on('grab', 'node', onGrab)
  cy.on('drag', 'node', onDrag)
  cy.on('free', 'node', onFree)

  return () => {
    if (settleTimer) clearTimeout(settleTimer)
    cy.off('grab', 'node', onGrab)
    cy.off('drag', 'node', onDrag)
    cy.off('free', 'node', onFree)
  }
}
