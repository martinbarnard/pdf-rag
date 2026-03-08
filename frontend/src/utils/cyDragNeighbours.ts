/**
 * Drag behaviour for Cytoscape:
 *
 * During drag  — connected nodes are pulled by dampened springs.
 *               Each neighbour has a velocity that is attracted toward
 *               its target position (dragged node offset × hop factor)
 *               and damped each tick so it converges without oscillating.
 * After drag   — run a local fcose sub-layout on the dragged node + its
 *               immediate neighbourhood so they settle without overlapping,
 *               while the rest of the graph stays put.
 */
import type { Core, NodeSingular } from 'cytoscape'

// Spring constants
const SPRING_K   = 0.18   // attraction strength toward target per tick (0–1)
const DAMPING    = 0.75   // velocity multiplier each tick (< 1 = damped)
const HOP_FACTOR = 0.7    // target-offset fraction per hop (1-hop gets 70%, 2-hop 49%)
const MAX_DEPTH  = 2      // hops to include in spring system

type SpringState = {
  /** Target position this frame (updated each drag event) */
  targetX: number
  targetY: number
  /** Accumulated velocity */
  vx: number
  vy: number
  /** Fraction of dragged-node offset applied to this neighbour's target */
  factor: number
  /** Snap position at grab time */
  originX: number
  originY: number
}

function buildSpringMap(root: NodeSingular, maxDepth: number, hopFactor: number): Map<string, SpringState> {
  const map = new Map<string, SpringState>()
  const visited = new Set<string>([root.id()])
  let frontier: NodeSingular[] = [root]
  let factor = hopFactor

  for (let depth = 1; depth <= maxDepth; depth++) {
    const next: NodeSingular[] = []
    for (const node of frontier) {
      node.neighborhood('node').forEach((n: NodeSingular) => {
        if (!visited.has(n.id())) {
          visited.add(n.id())
          const pos = n.position()
          map.set(n.id(), {
            targetX: pos.x, targetY: pos.y,
            vx: 0, vy: 0,
            factor,
            originX: pos.x, originY: pos.y,
          })
          next.push(n)
        }
      })
    }
    frontier = next
    factor *= hopFactor
    if (!frontier.length) break
  }
  return map
}

export function attachDragNeighbours(cy: Core): () => void {
  let springs: Map<string, SpringState> = new Map()
  let grabPos: { x: number; y: number } | null = null
  let rafId: number | null = null
  let settleTimer: ReturnType<typeof setTimeout> | null = null

  function cancelRaf() {
    if (rafId !== null) { cancelAnimationFrame(rafId); rafId = null }
  }

  /** rAF loop: step each spring toward its current target */
  function tick() {
    rafId = null
    if (!springs.size) return

    let anyActive = false
    springs.forEach((s, id) => {
      const n = cy.getElementById(id)
      if (!n.length || n.grabbed() || n.locked()) return

      const cur = n.position()
      const fx = (s.targetX - cur.x) * SPRING_K
      const fy = (s.targetY - cur.y) * SPRING_K
      s.vx = (s.vx + fx) * DAMPING
      s.vy = (s.vy + fy) * DAMPING

      if (Math.abs(s.vx) > 0.01 || Math.abs(s.vy) > 0.01) {
        n.position({ x: cur.x + s.vx, y: cur.y + s.vy })
        anyActive = true
      }
    })

    if (anyActive) {
      rafId = requestAnimationFrame(tick)
    }
  }

  function onGrab(evt: cytoscape.EventObject) {
    cancelRaf()
    if (settleTimer) { clearTimeout(settleTimer); settleTimer = null }
    // Unlock everything — a previous settle may have left nodes locked
    cy.nodes().unlock()
    const node = evt.target as NodeSingular
    grabPos = { ...node.position() }
    springs = buildSpringMap(node, MAX_DEPTH, HOP_FACTOR)
    rafId = requestAnimationFrame(tick)
  }

  function onDrag(evt: cytoscape.EventObject) {
    if (!grabPos || !springs.size) return
    const cur = (evt.target as NodeSingular).position()
    const dx = cur.x - grabPos.x
    const dy = cur.y - grabPos.y
    // Update each spring's target — the tick loop converges toward it
    springs.forEach((s) => {
      s.targetX = s.originX + dx * s.factor
      s.targetY = s.originY + dy * s.factor
    })
    // Ensure tick loop is running
    if (rafId === null) rafId = requestAnimationFrame(tick)
  }

  function onFree(evt: cytoscape.EventObject) {
    cancelRaf()
    const droppedNode = evt.target as NodeSingular
    springs = new Map()
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
    cancelRaf()
    if (settleTimer) clearTimeout(settleTimer)
    cy.off('grab', 'node', onGrab)
    cy.off('drag', 'node', onDrag)
    cy.off('free', 'node', onFree)
  }
}
