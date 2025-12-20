'use client'

/**
 * Alpha Graph Canvas - D3 Force-Directed Visualization
 * CEO Directive 2026 - Pillar III Implementation
 *
 * Edge Types per Section 4.1:
 * - LEADS: Cyan, solid with particle flow
 * - AMPLIFIES: Green, pulsing
 * - INVERSE: Red, dashed
 * - CORRELATES: Purple, solid
 */

import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { GraphData, GraphNode, GraphEdge } from '@/lib/fcc/alpha-graph-engine'

interface Props {
  data: GraphData
}

const EDGE_COLORS: Record<string, string> = {
  LEADS: '#06B6D4',
  AMPLIFIES: '#22C55E',
  INVERSE: '#EF4444',
  CORRELATES: '#8B5CF6',
}

const NODE_COLORS: Record<string, string> = {
  ASSET: '#3B82F6',
  MACRO: '#F59E0B',
  INDICATOR: '#10B981',
  NEWS_ENTITY: '#8B5CF6',
  REGIME: '#EC4899',
}

export function AlphaGraphCanvas({ data }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const updateDimensions = () => {
      if (svgRef.current?.parentElement) {
        setDimensions({
          width: svgRef.current.parentElement.clientWidth,
          height: svgRef.current.parentElement.clientHeight,
        })
      }
    }
    updateDimensions()
    window.addEventListener('resize', updateDimensions)
    return () => window.removeEventListener('resize', updateDimensions)
  }, [])

  useEffect(() => {
    if (!svgRef.current || dimensions.width === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const { width, height } = dimensions

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform)
      })

    svg.call(zoom)

    // Container for zooming
    const container = svg.append('g')

    // Arrow markers for directed edges
    const defs = svg.append('defs')

    Object.entries(EDGE_COLORS).forEach(([type, color]) => {
      defs.append('marker')
        .attr('id', `arrow-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 25)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('fill', color)
        .attr('d', 'M0,-5L10,0L0,5')
    })

    // Prepare simulation data
    const nodes: (GraphNode & d3.SimulationNodeDatum)[] = data.nodes.map(n => ({ ...n }))
    const nodeIds = new Set(nodes.map(n => n.id))

    // Filter edges to only include those where both source and target exist in nodes
    const edges = data.edges
      .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map(e => ({
        ...e,
        source: e.source,
        target: e.target,
      }))

    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges)
        .id((d: any) => d.id)
        .distance(150)
        .strength((d: any) => Math.min(d.weight || 0.5, 1))
      )
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40))

    // Draw edges
    const link = container.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', d => EDGE_COLORS[d.type] || '#6B7280')
      .attr('stroke-width', d => Math.max(1, (d.weight || 0.5) * 3))
      .attr('stroke-opacity', 0.6)
      .attr('stroke-dasharray', d => d.type === 'INVERSE' ? '5,5' : 'none')
      .attr('marker-end', d => `url(#arrow-${d.type})`)

    // Draw nodes
    const node = container.append('g')
      .attr('class', 'nodes')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('cursor', 'pointer')
      .call(d3.drag<SVGGElement, typeof nodes[0]>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
      )
      .on('click', (event, d) => {
        setSelectedNode(d)
      })
      .on('mouseenter', (event, d) => {
        setHoveredNode(d.id)
        // Highlight connected edges
        link.attr('stroke-opacity', l =>
          (l.source as any).id === d.id || (l.target as any).id === d.id ? 1 : 0.1
        )
      })
      .on('mouseleave', () => {
        setHoveredNode(null)
        link.attr('stroke-opacity', 0.6)
      })

    // Node circles
    node.append('circle')
      .attr('r', d => d.size || 12)
      .attr('fill', d => NODE_COLORS[d.type] || '#6B7280')
      .attr('stroke', '#1E293B')
      .attr('stroke-width', 2)

    // Node labels
    node.append('text')
      .attr('dy', d => (d.size || 12) + 14)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94A3B8')
      .attr('font-size', '10px')
      .attr('font-family', 'monospace')
      .text(d => d.label.length > 20 ? d.label.substring(0, 18) + '...' : d.label)

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as any).x)
        .attr('y1', d => (d.source as any).y)
        .attr('x2', d => (d.target as any).x)
        .attr('y2', d => (d.target as any).y)

      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Cleanup
    return () => {
      simulation.stop()
    }
  }, [data, dimensions])

  return (
    <div className="relative w-full h-full">
      <svg
        ref={svgRef}
        className="w-full h-full bg-slate-950"
        style={{ cursor: 'grab' }}
      />

      {/* Selected Node Panel */}
      {selectedNode && (
        <div className="absolute top-4 right-4 w-80 bg-slate-900/95 backdrop-blur border border-slate-700 rounded-lg p-4 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-white">{selectedNode.label}</h3>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-slate-400 hover:text-white"
            >
              &times;
            </button>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Type</span>
              <span
                className="px-2 py-0.5 rounded text-xs font-mono"
                style={{
                  backgroundColor: NODE_COLORS[selectedNode.type] + '20',
                  color: NODE_COLORS[selectedNode.type],
                }}
              >
                {selectedNode.type}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">ID</span>
              <span className="text-slate-300 font-mono text-xs">{selectedNode.id}</span>
            </div>
            {selectedNode.regime_state && (
              <div className="flex justify-between">
                <span className="text-slate-400">Regime</span>
                <span className="text-amber-400">{selectedNode.regime_state}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-slate-400">Is Macro</span>
              <span className={selectedNode.is_macro ? 'text-green-400' : 'text-slate-500'}>
                {selectedNode.is_macro ? 'Yes' : 'No'}
              </span>
            </div>
          </div>

          {/* Connected Edges */}
          <div className="mt-4 pt-3 border-t border-slate-700">
            <h4 className="text-xs text-slate-500 uppercase tracking-wide mb-2">
              Causal Connections
            </h4>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {data.edges
                .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
                .slice(0, 10)
                .map((edge, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-xs bg-slate-800/50 rounded px-2 py-1"
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: EDGE_COLORS[edge.type] }}
                    />
                    <span className="text-slate-400 truncate flex-1">
                      {edge.source === selectedNode.id ? edge.target : edge.source}
                    </span>
                    <span
                      className="text-xs px-1 rounded"
                      style={{ color: EDGE_COLORS[edge.type] }}
                    >
                      {edge.type}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Hovered Node Tooltip */}
      {hoveredNode && !selectedNode && (
        <div className="absolute bottom-20 left-1/2 -translate-x-1/2 bg-slate-800/90 backdrop-blur px-4 py-2 rounded-lg text-sm">
          <span className="text-white font-mono">{hoveredNode}</span>
          <span className="text-slate-400 ml-2">Click to inspect</span>
        </div>
      )}

      {/* Instructions */}
      <div className="absolute bottom-20 left-4 text-xs text-slate-500">
        <p>Scroll to zoom | Drag to pan | Click node to inspect</p>
      </div>

      {/* Node Type Legend */}
      <div className="absolute top-4 left-4 bg-slate-900/80 backdrop-blur border border-slate-800 rounded-lg p-3">
        <h4 className="text-xs text-slate-500 uppercase tracking-wide mb-2">Node Types</h4>
        <div className="space-y-1">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2 text-xs">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="text-slate-400">{type}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
