/**
 * Attach spring-tension drag behaviour to a Cytoscape instance.
 *
 * When a node is dragged, connected nodes are pulled along with it, but with
 * a tension falloff: nodes further away (more hops) move proportionally less.
 *
 *   hop 0 (dragged node) → 100% of delta
 *   hop 1 neighbours     → TENSION^1  (default ~40%)
 *   hop 2 neighbours     → TENSION^2  (~16%)
 *   …up to MAX_DEPTH hops
 *
 * The layout is NOT re-run after drag — manual positions are preserved.
 */
import type { Core, NodeSingular } from 'cytoscape'

const TENSION = 0.4   // fraction of delta passed to each successive hop
const MAX_DEPTH = 3   // how many hops out to influence

type Snap = { x: number; y: number; factor: number }

/** BFS from `root`, returning { nodeId → { snapPos, moveFactor } } up to maxDepth. */
function buildSnapMap(_cy: Core, root: NodeSingular, maxDepth: number, tension: number): Map<string, Snap> {
  const map = new Map<string, Snap>()
  const visited = new Set<string>([root.id()])
  let frontier: NodeSingular[] = [root]
  let factor = tension  // starts at tension for hop-1 neighbours

  for (let depth = 1; depth <= maxDepth; depth++) {
    const nextFrontier: NodeSingular[] = []
    for (const node of frontier) {
      node.neighborhood('node').forEach((n: NodeSingular) => {
        if (!visited.has(n.id())) {
          visited.add(n.id())
          map.set(n.id(), { ...n.position(), factor })
          nextFrontier.push(n)
        }
      })
    }
    frontier = nextFrontier
    factor *= tension
    if (frontier.length === 0) break
  }

  return map
}

export function attachDragNeighbours(cy: Core): () => void {
  let snapMap: Map<string, Snap> = new Map()
  let grabPos: { x: number; y: number } | null = null

  function onGrab(evt: cytoscape.EventObject) {
    const node = evt.target as NodeSingular
    grabPos = { ...node.position() }
    snapMap = buildSnapMap(cy, node, MAX_DEPTH, TENSION)
  }

  function onDrag(evt: cytoscape.EventObject) {
    if (!grabPos || snapMap.size === 0) return
    const cur = (evt.target as NodeSingular).position()
    const dx = cur.x - grabPos.x
    const dy = cur.y - grabPos.y

    snapMap.forEach((snap, id) => {
      const n = cy.getElementById(id)
      if (n.length && !n.grabbed()) {
        n.position({
          x: snap.x + dx * snap.factor,
          y: snap.y + dy * snap.factor,
        })
      }
    })
  }

  function onFree() {
    snapMap = new Map()
    grabPos = null
  }

  cy.on('grab', 'node', onGrab)
  cy.on('drag', 'node', onDrag)
  cy.on('free', 'node', onFree)

  return () => {
    cy.off('grab', 'node', onGrab)
    cy.off('drag', 'node', onDrag)
    cy.off('free', 'node', onFree)
  }
}
