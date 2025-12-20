/**
 * Alpha Graph Nodes API Route
 * Fetches node data from fhq_graph schema
 */

import { NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

interface AlphaNode {
  node_id: string
  node_type: string
  label: string
  status: string
}

export async function GET() {
  try {
    // Get all nodes from alpha graph
    const nodes = await queryMany<AlphaNode>(`
      SELECT
        node_id,
        node_type,
        label,
        status
      FROM fhq_graph.nodes
      ORDER BY node_type, label
    `)

    return NextResponse.json(nodes || [], {
      headers: {
        'Cache-Control': 'public, s-maxage=600, stale-while-revalidate=1200',
      },
    })
  } catch (error) {
    console.error('Error fetching alpha nodes:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
