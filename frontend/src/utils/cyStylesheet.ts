/**
 * Shared Cytoscape stylesheet with icon-based node rendering.
 *
 * Each node type gets:
 *   - A coloured rounded-rectangle background
 *   - An inline SVG icon (white, Lucide-style paths) as background-image
 *
 * Icons are embedded as data URIs so there are no network requests.
 */
import type cytoscape from 'cytoscape'

// ---------------------------------------------------------------------------
// SVG icon helpers
// ---------------------------------------------------------------------------

function svgUri(pathD: string, viewBox = '0 0 24 24'): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${pathD}</svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

// Person / author — simple head + shoulders silhouette
const ICON_AUTHOR = svgUri(
  '<circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>'
)

// File-text / PDF — document with lines
const ICON_PAPER = svgUri(
  '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>' +
  '<polyline points="14 2 14 8 20 8"/>' +
  '<line x1="16" y1="13" x2="8" y2="13"/>' +
  '<line x1="16" y1="17" x2="8" y2="17"/>' +
  '<polyline points="10 9 9 9 8 9"/>'
)

// Tag / topic — price-tag shape
const ICON_TOPIC = svgUri(
  '<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>' +
  '<line x1="7" y1="7" x2="7.01" y2="7"/>'
)

// ---------------------------------------------------------------------------
// Node sizes per type
// ---------------------------------------------------------------------------

const SIZE = { Paper: 36, Author: 32, Topic: 30, default: 28 }

// ---------------------------------------------------------------------------
// Exported stylesheet builder
// ---------------------------------------------------------------------------

export function buildStylesheet(opts?: {
  selectedBorderColor?: string
}): cytoscape.StylesheetJson {
  const selBorder = opts?.selectedBorderColor ?? '#ffffff'

  return [
    // Base — all nodes
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        'font-size': 10,
        color: '#e5e7eb',
        'text-valign': 'bottom',
        'text-margin-y': 6,
        'text-max-width': '90px',
        'text-wrap': 'ellipsis',
        width: SIZE.default,
        height: SIZE.default,
        shape: 'round-rectangle',
        'background-color': '#6b7280',
        'background-image': 'none',
        'background-fit': 'contain',
        'background-clip': 'none',
        'background-image-opacity': 1,
        'background-width': '65%',
        'background-height': '65%',
        'border-width': 0,
        'border-color': selBorder,
      },
    },

    // Paper — indigo, document icon
    {
      selector: 'node[type="Paper"]',
      style: {
        width: SIZE.Paper,
        height: SIZE.Paper,
        'background-color': '#4f46e5',
        'background-image': ICON_PAPER,
      } as cytoscape.Css.Node,
    },

    // Author — green, person icon
    {
      selector: 'node[type="Author"]',
      style: {
        width: SIZE.Author,
        height: SIZE.Author,
        'background-color': '#16a34a',
        'background-image': ICON_AUTHOR,
      } as cytoscape.Css.Node,
    },

    // Topic — amber, tag icon
    {
      selector: 'node[type="Topic"]',
      style: {
        width: SIZE.Topic,
        height: SIZE.Topic,
        'background-color': '#d97706',
        'background-image': ICON_TOPIC,
      } as cytoscape.Css.Node,
    },

    // Selected highlight
    {
      selector: 'node:selected',
      style: {
        'border-width': 3,
        'border-color': selBorder,
      },
    },

    // Edges
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
  ] as cytoscape.StylesheetJson
}

// Default export for the common case
export const GRAPH_STYLESHEET = buildStylesheet()

// ---------------------------------------------------------------------------
// Detail-page stylesheet (TopicDetail / AuthorDetail)
// Uses `nodeType` data attribute: "current" | "paper" | "topic" | "author"
// ---------------------------------------------------------------------------

export function buildDetailStylesheet(colours: {
  current: string
  paper: string
  secondary: string   // topic colour for TopicDetail, author colour for AuthorDetail
  secondaryIcon: string  // which icon to use for the secondary type
}): cytoscape.StylesheetJson {
  const secondaryIcon =
    colours.secondaryIcon === 'author' ? ICON_AUTHOR
    : colours.secondaryIcon === 'topic' ? ICON_TOPIC
    : ICON_PAPER

  return [
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        'font-size': 10,
        color: '#e5e7eb',
        'text-valign': 'bottom',
        'text-margin-y': 6,
        'text-max-width': '90px',
        'text-wrap': 'ellipsis',
        width: 28,
        height: 28,
        shape: 'round-rectangle',
        'background-color': '#6b7280',
        'background-fit': 'contain',
        'background-clip': 'none',
        'background-image-opacity': 1,
        'background-width': '65%',
        'background-height': '65%',
        'border-width': 0,
      },
    },
    // Current (focal) node — larger, glowing ring
    {
      selector: 'node[nodeType="current"]',
      style: {
        width: 40,
        height: 40,
        'font-size': 12,
        'background-color': colours.current,
        'background-image': ICON_PAPER,
        'border-width': 3,
        'border-color': colours.current,
        'border-opacity': 0.5,
      } as cytoscape.Css.Node,
    },
    // Paper nodes
    {
      selector: 'node[nodeType="paper"]',
      style: {
        'background-color': colours.paper,
        'background-image': ICON_PAPER,
      } as cytoscape.Css.Node,
    },
    // Secondary nodes (topic or author depending on the view)
    {
      selector: 'node[nodeType="topic"], node[nodeType="author"]',
      style: {
        'background-color': colours.secondary,
        'background-image': secondaryIcon,
      } as cytoscape.Css.Node,
    },
    // Selected
    {
      selector: 'node:selected',
      style: { 'border-width': 3, 'border-color': '#ffffff' },
    },
    // Edges
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
  ] as cytoscape.StylesheetJson
}
