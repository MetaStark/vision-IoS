/**
 * Macro Features API Route
 * Fetches feature registry and series data from fhq_macro schema
 */

import { NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

interface MacroFeature {
  feature_id: string
  feature_name: string
  description: string
  cluster: string
  status: string
  frequency: string
}

interface MacroSeries {
  feature_id: string
  records: number
  from_date: string
  to_date: string
}

export async function GET() {
  try {
    // Get all features from registry
    const features = await queryMany<MacroFeature>(`
      SELECT
        feature_id,
        feature_name,
        description,
        cluster,
        status,
        frequency
      FROM fhq_macro.feature_registry
      ORDER BY cluster, feature_name
    `)

    // Get series statistics for each feature
    const series = await queryMany<MacroSeries>(`
      SELECT
        feature_id,
        COUNT(*) as records,
        MIN(timestamp)::text as from_date,
        MAX(timestamp)::text as to_date
      FROM fhq_macro.canonical_series
      GROUP BY feature_id
      ORDER BY feature_id
    `)

    return NextResponse.json(
      { features: features || [], series: series || [] },
      {
        headers: {
          'Cache-Control': 'public, s-maxage=600, stale-while-revalidate=1200',
        },
      }
    )
  } catch (error) {
    console.error('Error fetching macro features:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
