/**
 * FINN API Route: Alpha Drift Status
 * Returns alpha drift monitoring alerts (institutional surveillance)
 *
 * Authority: Phase 5 (Alpha Drift Monitor)
 * Data Source: fhq_monitoring.alpha_drift_log
 */

import { NextRequest, NextResponse } from 'next/server'
import { queryOne, queryMany } from '@/lib/db'

export const dynamic = 'force-dynamic'

interface DriftStatus {
  signal_date: string
  listing_id: string

  // Drift detection
  drift_alert_level: 'NORMAL' | 'WARNING' | 'CRITICAL'
  drift_alert_reason: string | null
  low_activity_flag: boolean

  // Direction tracking
  direction_changed: boolean
  prev_direction: string | null
  current_direction: string | null

  // Allocation tracking
  allocation_delta: number | null
  zero_allocation_days: number

  // Recent drift events
  recent_warnings: number
  recent_critical: number

  // FINN interpretation
  finn_interpretation: string
}

interface DriftHistoryItem {
  signal_date: string
  drift_alert_level: string
  drift_alert_reason: string
  allocation_delta: number | null
}

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams
    const listingId = searchParams.get('listing_id') || 'LST_BTC_XCRYPTO'
    const signalDate = searchParams.get('signal_date') // Optional

    // Query latest drift status
    const statusQuery = `
      WITH latest_drift AS (
        SELECT *
        FROM fhq_monitoring.alpha_drift_log
        WHERE listing_id = $1
          ${signalDate ? 'AND check_date = $2' : ''}
        ORDER BY check_date DESC, checked_at DESC
        LIMIT 1
      ),
      recent_alerts AS (
        SELECT
          COUNT(*) FILTER (WHERE drift_alert_level = 'WARNING') AS warning_count,
          COUNT(*) FILTER (WHERE drift_alert_level = 'CRITICAL') AS critical_count
        FROM fhq_monitoring.alpha_drift_log
        WHERE listing_id = $1
          AND check_date >= CURRENT_DATE - INTERVAL '7 days'
      )
      SELECT
        ld.check_date::TEXT AS signal_date,
        ld.listing_id,
        ld.drift_alert_level,
        ld.drift_alert_reason,
        ld.low_activity_flag,
        ld.direction_changed,
        ld.previous_meta_direction AS prev_direction,
        ld.current_meta_direction AS current_direction,
        ld.allocation_delta,
        ld.consecutive_zero_days AS zero_allocation_days,

        ra.warning_count AS recent_warnings,
        ra.critical_count AS recent_critical,

        -- FINN interpretation
        CASE
          WHEN ld.drift_alert_level = 'CRITICAL' THEN
            format(
              'CRITICAL: %s. Multiple drift rules triggered. Recommend immediate strategy review.',
              ld.drift_alert_reason
            )
          WHEN ld.drift_alert_level = 'WARNING' THEN
            format(
              'WARNING: %s. This may indicate strategy drift - worth reviewing manual overrides.',
              ld.drift_alert_reason
            )
          WHEN ld.low_activity_flag = TRUE THEN
            format(
              'Low activity: %s consecutive days with 0%% allocation. All signals blocked by risk gates. Consider reviewing risk parameters.',
              ld.consecutive_zero_days
            )
          ELSE
            'Alpha behavior normal. No drift detected in recent periods.'
        END AS finn_interpretation

      FROM latest_drift ld
      CROSS JOIN recent_alerts ra
    `

    const params = signalDate ? [listingId, signalDate] : [listingId]
    const status = await queryOne<DriftStatus>(statusQuery, params)

    if (!status) {
      // No drift log entry - system may be new or data missing
      return NextResponse.json({
        current_status: {
          signal_date: signalDate || new Date().toISOString().split('T')[0],
          listing_id: listingId,
          drift_alert_level: 'NORMAL',
          drift_alert_reason: null,
          low_activity_flag: false,
          direction_changed: false,
          prev_direction: null,
          current_direction: null,
          allocation_delta: null,
          zero_allocation_days: 0,
          recent_warnings: 0,
          recent_critical: 0,
          finn_interpretation: 'Alpha drift monitoring active. No historical data available yet.'
        },
        drift_history: [],
        summary: {
          total_alerts_30d: 0,
          warnings_30d: 0,
          critical_30d: 0,
          low_activity_periods: 0
        }
      })
    }

    // Get drift history (last 30 days)
    const historyQuery = `
      SELECT
        check_date::TEXT AS signal_date,
        drift_alert_level,
        drift_alert_reason,
        allocation_delta
      FROM fhq_monitoring.alpha_drift_log
      WHERE listing_id = $1
        AND check_date >= CURRENT_DATE - INTERVAL '30 days'
      ORDER BY check_date DESC
      LIMIT 30
    `

    const history = await queryMany<DriftHistoryItem>(historyQuery, [listingId])

    return NextResponse.json({
      current_status: status,
      drift_history: history,
      summary: {
        total_alerts_30d: history.filter(h => h.drift_alert_level !== 'NORMAL').length,
        warnings_30d: history.filter(h => h.drift_alert_level === 'WARNING').length,
        critical_30d: history.filter(h => h.drift_alert_level === 'CRITICAL').length,
        low_activity_periods: history.filter(h =>
          h.drift_alert_reason?.includes('Low activity')
        ).length
      }
    })

  } catch (error) {
    console.error('[FINN API] Drift status error:', error)
    return NextResponse.json(
      {
        error: 'Failed to fetch drift status',
        message: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
