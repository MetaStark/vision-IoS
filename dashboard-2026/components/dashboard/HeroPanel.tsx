/**
 * Hero Panel Component (Zone 1)
 * 3-Second Understanding: "What's Happening Now?"
 *
 * Authority: Dashboard UX Specification 2026 v2.0
 * North Star: CIO Understanding < 3 seconds
 *
 * Displays:
 * - Meta allocation (BUY/SELL/HOLD + %)
 * - Regime context (BULL/NEUTRAL/BEAR)
 * - FINN's verdict (3-layer narrative)
 * - Drift status (normal/warning)
 */

'use client'

import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils/cn'

interface HeroPanelProps {
  listingId?: string
  className?: string
}

interface MetaSignal {
  allocation_pct: number
  direction: 'LONG' | 'SHORT' | 'NEUTRAL'
  signal_strength: number
  regime_label: 'BULL' | 'NEUTRAL' | 'BEAR' | null
  regime_confidence: number | null
  risk_gates_passed: boolean
  risk_block_reason: string | null
  finn_narrative: string
  integrity_status: string
}

interface DriftStatus {
  current_status: {
    drift_alert_level: 'NORMAL' | 'WARNING' | 'CRITICAL'
    drift_alert_reason: string | null
    finn_interpretation: string
  }
}

export function HeroPanel({ listingId = 'LST_BTC_XCRYPTO', className }: HeroPanelProps) {
  const [metaSignal, setMetaSignal] = useState<MetaSignal | null>(null)
  const [driftStatus, setDriftStatus] = useState<DriftStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        // Fetch meta signal and drift status in parallel
        const [metaRes, driftRes] = await Promise.all([
          fetch(`/api/finn/meta-signal?listing_id=${listingId}`),
          fetch(`/api/finn/drift-status?listing_id=${listingId}`)
        ])

        if (!metaRes.ok || !driftRes.ok) {
          throw new Error('Failed to fetch hero panel data')
        }

        const [meta, drift] = await Promise.all([metaRes.json(), driftRes.json()])

        setMetaSignal(meta)
        setDriftStatus(drift)
      } catch (err) {
        console.error('[Hero Panel] Fetch error:', err)
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [listingId])

  const getAllocationColor = (allocation: number) => {
    if (allocation > 20) return 'text-green-400 bg-green-950/30 border-green-700'
    if (allocation < -20) return 'text-red-400 bg-red-950/30 border-red-700'
    return 'text-blue-400 bg-blue-950/30 border-blue-700'
  }

  const getRegimeColor = (regime: string | null | undefined) => {
    switch (regime) {
      case 'BULL':
        return 'bg-green-900/40 text-green-400 border-green-700'
      case 'BEAR':
        return 'bg-red-900/40 text-red-400 border-red-700'
      case 'NEUTRAL':
        return 'bg-gray-800/40 text-gray-400 border-gray-600'
      default:
        return 'bg-gray-800/40 text-gray-500 border-gray-700'
    }
  }

  const getDriftColor = (level: string | undefined) => {
    switch (level) {
      case 'CRITICAL':
        return 'bg-red-900/40 text-red-400 border-red-700'
      case 'WARNING':
        return 'bg-yellow-900/40 text-yellow-400 border-yellow-700'
      default:
        return 'bg-green-900/40 text-green-400 border-green-700'
    }
  }

  if (isLoading) {
    return (
      <div className={cn('bg-gray-900 border border-gray-800 rounded-lg p-8', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-800 rounded w-1/3" />
          <div className="h-20 bg-gray-800 rounded" />
          <div className="h-4 bg-gray-800 rounded w-2/3" />
        </div>
      </div>
    )
  }

  if (error || !metaSignal) {
    return (
      <div className={cn('bg-gray-900 border border-red-900/50 rounded-lg p-8', className)}>
        <div className="text-red-400">
          <div className="font-semibold mb-2">Error Loading Meta Signal</div>
          <div className="text-sm text-gray-500">{error || 'No data available'}</div>
        </div>
      </div>
    )
  }

  return (
    <div
      className={cn(
        // Design: Minimalist black/charcoal theme
        'bg-gray-900 border border-gray-800 rounded-lg',
        // Subtle glow effect
        'shadow-lg shadow-gray-950/50',
        // Padding
        'p-8',
        className
      )}
      style={{
        boxShadow: '0 0 1px rgba(156, 163, 175, 0.2), 0 8px 24px rgba(0, 0, 0, 0.5)'
      }}
    >
      {/* Top: Meta allocation + Regime */}
      <div className="flex items-start justify-between mb-6">
        {/* Left: Allocation */}
        <div>
          <div className="text-xs uppercase tracking-wider text-gray-500 mb-2">
            Meta Allocation
          </div>
          <div className="flex items-baseline gap-3">
            <div className="text-5xl font-bold font-mono text-white">
              {parseFloat(metaSignal.allocation_pct as any) > 0 ? '+' : ''}
              {parseFloat(metaSignal.allocation_pct as any).toFixed(0)}%
            </div>
            <div
              className={cn(
                'px-3 py-1 rounded border text-sm font-semibold',
                getAllocationColor(parseFloat(metaSignal.allocation_pct as any))
              )}
            >
              {metaSignal.direction}
            </div>
          </div>
          <div className="mt-2 text-xs text-gray-500">
            Signal strength: {(parseFloat(metaSignal.signal_strength as any) * 100).toFixed(0)}%
          </div>
        </div>

        {/* Right: Regime + Drift */}
        <div className="flex flex-col items-end gap-2">
          {/* Regime badge */}
          <div
            className={cn(
              'px-4 py-2 rounded border text-sm font-semibold',
              getRegimeColor(metaSignal.regime_label)
            )}
          >
            <div className="text-xs uppercase tracking-wider opacity-70">Regime</div>
            <div className="text-lg">{metaSignal.regime_label || 'UNKNOWN'}</div>
            {metaSignal.regime_confidence && (
              <div className="text-xs opacity-70 mt-1">
                {(parseFloat(metaSignal.regime_confidence as any) * 100).toFixed(0)}% confidence
              </div>
            )}
          </div>

          {/* Drift status */}
          {driftStatus && (
            <div
              className={cn(
                'px-3 py-1 rounded border text-xs',
                getDriftColor(driftStatus.current_status.drift_alert_level)
              )}
            >
              {driftStatus.current_status.drift_alert_level === 'NORMAL' ? '✓ ' : '⚠ '}
              {driftStatus.current_status.drift_alert_level}
            </div>
          )}
        </div>
      </div>

      {/* Middle: FINN's Verdict (3-layer narrative) */}
      <div className="border-t border-b border-gray-800 py-6 my-6">
        <div className="text-xs uppercase tracking-wider text-gray-500 mb-3">
          FINN's Verdict
        </div>
        <div className="text-lg leading-relaxed text-gray-200">
          {metaSignal.finn_narrative}
        </div>
      </div>

      {/* Bottom: Risk gates + Integrity */}
      <div className="flex items-center justify-between text-xs">
        {/* Risk gates */}
        {!metaSignal.risk_gates_passed && metaSignal.risk_block_reason && (
          <div className="flex items-center gap-2 text-yellow-400">
            <span>⚠</span>
            <span>Risk block: {metaSignal.risk_block_reason}</span>
          </div>
        )}
        {metaSignal.risk_gates_passed && (
          <div className="flex items-center gap-2 text-green-400">
            <span>✓</span>
            <span>Risk gates passed</span>
          </div>
        )}

        {/* Integrity status */}
        <div
          className={cn(
            'flex items-center gap-2',
            metaSignal.integrity_status === 'VERIFIED'
              ? 'text-green-400'
              : metaSignal.integrity_status === 'STALE'
              ? 'text-yellow-400'
              : 'text-gray-500'
          )}
        >
          {metaSignal.integrity_status === 'VERIFIED' && <span>✓</span>}
          {metaSignal.integrity_status === 'STALE' && <span>⚠</span>}
          <span>{metaSignal.integrity_status}</span>
        </div>
      </div>
    </div>
  )
}
