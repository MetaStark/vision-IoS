/**
 * Trust Banner Component (Updated FINN V3.0)
 * Global system health indicator - sticky top banner
 * Real data from DB with enhanced lineage exposition
 * MBB-grade: Clear governance fidelity
 *
 * NEW: Cognitive Dissonance Index (CDS) indicator
 */

'use client'

import { useState, useEffect } from 'react'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { cn } from '@/lib/utils/cn'

interface TrustBannerProps {
  gateStatus: 'PASS' | 'FAIL' | 'PARTIAL'
  gatesPassed: number
  gatesTotal: number
  alertCount: number
  adrCompliant: boolean
  dataFreshness: 'FRESH' | 'STALE' | 'OUTDATED'
  // FINN V3.0: CDS / Narrative Shift Risk
  narrativeShiftRisk?: 'LOW' | 'MODERATE' | 'HIGH'
  cdsScore?: number
}

export function TrustBanner({
  gateStatus,
  gatesPassed,
  gatesTotal,
  alertCount,
  adrCompliant,
  dataFreshness,
  narrativeShiftRisk,
  cdsScore,
}: TrustBannerProps) {
  // Use state for time to avoid hydration mismatch
  const [currentTime, setCurrentTime] = useState<string>('')

  useEffect(() => {
    // Set initial time on client
    setCurrentTime(new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }))

    // Update every minute
    const interval = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }))
    }, 60000)

    return () => clearInterval(interval)
  }, [])

  const overallStatus = getOverallStatus(
    gateStatus,
    alertCount,
    adrCompliant,
    dataFreshness,
    narrativeShiftRisk
  )

  return (
    <div className="trust-banner">
      <div className="max-w-[1920px] mx-auto px-6 py-3">
        <div className="flex items-center justify-between">
          {/* Left: Overall status */}
          <div className="flex items-center gap-4">
            {/* System pulse indicator */}
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  'w-2.5 h-2.5 rounded-full',
                  overallStatus === 'healthy' && 'bg-green-500 animate-pulse',
                  overallStatus === 'warning' && 'bg-orange-500 animate-pulse',
                  overallStatus === 'critical' && 'bg-red-500 animate-pulse'
                )}
              />
              <span className="text-sm font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
                System Status
              </span>
            </div>

            {/* Gate status - Enhanced with gates passed/total */}
            <div className="flex items-center gap-2 pl-4" style={{ borderLeft: '1px solid hsl(var(--border))' }}>
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Gates:</span>
              <StatusBadge
                variant={gateStatus === 'PASS' ? 'pass' : gateStatus === 'PARTIAL' ? 'warning' : 'fail'}
                icon={gateStatus === 'PASS' ? '✓' : gateStatus === 'PARTIAL' ? '⚠' : '✗'}
              >
                {gatesPassed}/{gatesTotal}
              </StatusBadge>
              <span
                className="data-lineage-indicator"
                title="Source: fhq_validation.v_gate_a_summary"
              >
                i
              </span>
            </div>

            {/* Alert count */}
            {alertCount > 0 && (
              <div className="flex items-center gap-2 pl-4" style={{ borderLeft: '1px solid hsl(var(--border))' }}>
                <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Alerts:</span>
                <StatusBadge variant="warning" icon="⚠">
                  {alertCount} Active
                </StatusBadge>
                <span
                  className="data-lineage-indicator"
                  title="Source: fhq_monitoring.v_drift_alert_history + fhq_vendors.v_ingestion_health_24h"
                >
                  i
                </span>
              </div>
            )}

            {/* ADR compliance */}
            <div className="flex items-center gap-2 pl-4" style={{ borderLeft: '1px solid hsl(var(--border))' }}>
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>ADR:</span>
              <StatusBadge variant={adrCompliant ? 'pass' : 'fail'}>
                {adrCompliant ? 'Compliant' : 'Review Required'}
              </StatusBadge>
              <span
                className="data-lineage-indicator"
                title="Source: fhq_meta.v_active_adrs"
              >
                i
              </span>
            </div>

            {/* Data freshness */}
            <div className="flex items-center gap-2 pl-4" style={{ borderLeft: '1px solid hsl(var(--border))' }}>
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Data:</span>
              <StatusBadge
                variant={
                  dataFreshness === 'FRESH'
                    ? 'fresh'
                    : dataFreshness === 'STALE'
                    ? 'stale'
                    : 'outdated'
                }
                icon={
                  dataFreshness === 'FRESH'
                    ? '✓'
                    : dataFreshness === 'STALE'
                    ? '⚠'
                    : '✗'
                }
              >
                {dataFreshness}
              </StatusBadge>
              <span
                className="data-lineage-indicator"
                title="Source: fhq_finn.v_btc_data_freshness"
              >
                i
              </span>
            </div>

            {/* FINN V3.0: Narrative Shift Risk (CDS) */}
            {narrativeShiftRisk && (
              <div className="flex items-center gap-2 pl-4" style={{ borderLeft: '1px solid hsl(var(--border))' }}>
                <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Narrative:</span>
                <StatusBadge
                  variant={
                    narrativeShiftRisk === 'LOW'
                      ? 'pass'
                      : narrativeShiftRisk === 'MODERATE'
                      ? 'warning'
                      : 'fail'
                  }
                  icon={
                    narrativeShiftRisk === 'LOW'
                      ? '✓'
                      : narrativeShiftRisk === 'MODERATE'
                      ? '⚠'
                      : '✗'
                  }
                >
                  {narrativeShiftRisk === 'LOW'
                    ? 'Aligned'
                    : narrativeShiftRisk === 'MODERATE'
                    ? 'Monitoring'
                    : 'Divergence'}
                  {cdsScore !== undefined && ` (${(cdsScore * 100).toFixed(0)}%)`}
                </StatusBadge>
                <span
                  className="data-lineage-indicator"
                  title="Source: fhq_finn.derivative_metrics.cds_score (Calculated from price_series + serper_events)"
                >
                  i
                </span>
              </div>
            )}
          </div>

          {/* Right: Quick stats & actions */}
          <div className="flex items-center gap-4 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
            {/* Overall health summary */}
            <div
              className={cn(
                'px-3 py-1.5 rounded-full font-semibold text-xs',
                overallStatus === 'healthy' && 'glow-success',
                overallStatus === 'warning' && 'glow-warning'
              )}
              style={
                overallStatus === 'healthy'
                  ? { backgroundColor: 'rgba(34, 197, 94, 0.15)', color: 'rgb(134, 239, 172)', border: '1px solid rgba(34, 197, 94, 0.3)' }
                  : overallStatus === 'warning'
                  ? { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: 'rgb(253, 224, 71)', border: '1px solid rgba(245, 158, 11, 0.3)' }
                  : { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'rgb(252, 165, 165)', border: '1px solid rgba(239, 68, 68, 0.3)' }
              }
            >
              {overallStatus === 'healthy' && '✓ All Systems Operational'}
              {overallStatus === 'warning' && '⚠ Minor Issues Detected'}
              {overallStatus === 'critical' && '✗ Critical Issues Detected'}
            </div>

            {/* Last updated */}
            <span style={{ color: 'hsl(var(--muted-foreground))' }}>
              {currentTime}
            </span>

            {/* Refresh button */}
            <button
              className="font-semibold transition-colors px-3 py-1 rounded-lg"
              style={{
                color: 'hsl(var(--primary))',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'hsl(var(--primary) / 0.1)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent'
              }}
              onClick={() => window.location.reload()}
              title="Refresh all data (revalidates cache)"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Determine overall system health status
 * MBB-grade logic: Clear hierarchy of severity
 * FINN V3.0: Includes narrative shift risk
 */
function getOverallStatus(
  gateStatus: string,
  alertCount: number,
  adrCompliant: boolean,
  dataFreshness: string,
  narrativeShiftRisk?: 'LOW' | 'MODERATE' | 'HIGH'
): 'healthy' | 'warning' | 'critical' {
  // CRITICAL if:
  // - Gates completely fail
  // - Data is outdated
  // - Narrative shift risk is HIGH (CDS ≥ 0.65)
  if (
    gateStatus === 'FAIL' ||
    dataFreshness === 'OUTDATED' ||
    narrativeShiftRisk === 'HIGH'
  ) {
    return 'critical'
  }

  // WARNING if:
  // - Partial gate failures
  // - Any alerts exist
  // - ADR non-compliant
  // - Data is stale
  // - Narrative shift risk is MODERATE (0.30 ≤ CDS < 0.65)
  if (
    gateStatus === 'PARTIAL' ||
    alertCount > 0 ||
    !adrCompliant ||
    dataFreshness === 'STALE' ||
    narrativeShiftRisk === 'MODERATE'
  ) {
    return 'warning'
  }

  return 'healthy'
}
