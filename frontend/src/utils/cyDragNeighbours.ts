/**
 * Attach "drag neighbours" behaviour to a Cytoscape instance.
 *
 * When a node is grabbed, the positions of its direct neighbours are
 * snapshotted. As the node is dragged, neighbours are translated by the
 * same delta so the local cluster moves together.
 *
 * Only direct (1-hop) neighbours move. The layout is NOT re-run after the
 * drag so the user's manual arrangement is preserved.
 */
import type { Core, NodeSingular } from 'cytoscape'

export function attachDragNeighbours(cy: Core): () => void {
  // Snapshot: neighbour id → position at grab time
  let neighbourSnap: Map<string, { x: number; y: number }> = new Map()
  let grabPos: { x: number; y: number } | null = null

  function onGrab(evt: cytoscape.EventObject) {
    const node = evt.target as NodeSingular
    grabPos = { ...node.position() }
    neighbourSnap = new Map()
    node.neighborhood('node').forEach((n: NodeSingular) => {
      neighbourSnap.set(n.id(), { ...n.position() })
    })
  }

  function onDrag(evt: cytoscape.EventObject) {
    if (!grabPos || neighbourSnap.size === 0) return
    const node = evt.target as NodeSingular
    const cur = node.position()
    const dx = cur.x - grabPos.x
    const dy = cur.y - grabPos.y

    neighbourSnap.forEach((snap, id) => {
      const neighbour = cy.getElementById(id)
      if (neighbour.length && !neighbour.grabbed()) {
        neighbour.position({ x: snap.x + dx, y: snap.y + dy })
      }
    })
  }

  function onFree() {
    neighbourSnap = new Map()
    grabPos = null
  }

  cy.on('grab', 'node', onGrab)
  cy.on('drag', 'node', onDrag)
  cy.on('free', 'node', onFree)

  // Return a cleanup function
  return () => {
    cy.off('grab', 'node', onGrab)
    cy.off('drag', 'node', onDrag)
    cy.off('free', 'node', onFree)
  }
}
