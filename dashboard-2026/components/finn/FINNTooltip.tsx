/**
 * FINN Tooltip Component
 * Implements FINN Micro-Dialog Pattern (5-step conversation)
 *
 * Authority: FINN Voice Guidelines v1.0
 * Pattern: State → Signal → Regime → Interpretation → Recommendation
 *
 * Design: Minimalist black/charcoal theme with 1px glow (Bloomberg 2026)
 */

'use client'

import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils/cn'

interface FINNTooltipProps {
  indicatorId: string
  listingId?: string
  children: React.ReactNode
  side?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

interface TooltipData {
  name_display: string
  current_value: number
  status: string
  status_color: string
  trend_direction: string
  trend_duration_days: number
  trend_change_pct: number
  regime_label: string | null
  regime_interpretation: string
  family_signal: string | null
  contribution_to_meta: string
  finn_narrative: string
  integrity_status: string
}

export function FINNTooltip({
  indicatorId,
  listingId = 'LST_BTC_XCRYPTO',
  children,
  side = 'top',
  className
}: FINNTooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [data, setData] = useState<TooltipData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch FINN explainer data on hover
  useEffect(() => {
    if (!isVisible || data) return

    const fetchData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(
          `/api/finn/indicator/${indicatorId}?listing_id=${listingId}`
        )

        if (!response.ok) {
          throw new Error(`Failed to fetch: ${response.statusText}`)
        }

        const result = await response.json()
        setData(result)
      } catch (err) {
        console.error('[FINN Tooltip] Fetch error:', err)
        setError(err instanceof Error ? err.message : 'Failed to load')
      } finally {
        setIsLoading(false)
      }
    }

    // Debounce fetch to avoid excessive API calls
    const timer = setTimeout(fetchData, 150)
    return () => clearTimeout(timer)
  }, [isVisible, indicatorId, listingId, data])

  const getStatusColor = (color: string | undefined) => {
    switch (color) {
      case 'green':
        return 'text-green-400 bg-green-950/30'
      case 'red':
        return 'text-red-400 bg-red-950/30'
      case 'yellow':
        return 'text-yellow-400 bg-yellow-950/30'
      case 'blue':
        return 'text-blue-400 bg-blue-950/30'
      default:
        return 'text-gray-400 bg-gray-800/30'
    }
  }

  const getTrendIcon = (direction: string | undefined) => {
    switch (direction) {
      case 'UP':
        return '↗'
      case 'DOWN':
        return '↘'
      default:
        return '→'
    }
  }

  const getIntegrityColor = (status: string | undefined) => {
    switch (status) {
      case 'VERIFIED':
        return 'text-green-500'
      case 'STALE':
        return 'text-yellow-500'
      default:
        return 'text-gray-500'
    }
  }

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {/* Trigger element */}
      <div className="cursor-help border-b border-dashed border-gray-600 hover:border-gray-400 transition-colors">
        {children}
      </div>

      {/* Tooltip content */}
      {isVisible && (
        <div
          className={cn(
            // Positioning
            'absolute z-50 w-96',
            side === 'top' && 'bottom-full left-1/2 -translate-x-1/2 mb-2',
            side === 'bottom' && 'top-full left-1/2 -translate-x-1/2 mt-2',
            side === 'left' && 'right-full top-1/2 -translate-y-1/2 mr-2',
            side === 'right' && 'left-full top-1/2 -translate-y-1/2 ml-2',

            // Design: Minimalist black/charcoal with 1px glow
            'bg-gray-900 border border-gray-700',
            'shadow-lg shadow-gray-950/50',
            'rounded-md',

            // Animation: Soft easing 150ms
            'animate-in fade-in-0 zoom-in-95',
            'duration-150',

            className
          )}
          style={{
            boxShadow: '0 0 1px rgba(156, 163, 175, 0.3), 0 4px 12px rgba(0, 0, 0, 0.5)'
          }}
        >
          {/* Loading state */}
          {isLoading && (
            <div className="p-4 text-sm text-gray-400 animate-pulse">
              FINN is analyzing...
            </div>
          )}

          {/* Error state */}
          {error && (
            <div className="p-4 text-sm text-red-400">
              <div className="font-semibold mb-1">Error loading FINN analysis</div>
              <div className="text-xs text-gray-500">{error}</div>
            </div>
          )}

          {/* FINN 5-step micro-dialog */}
          {data && (
            <div className="p-4 space-y-3">
              {/* Header: Indicator name + current value */}
              <div className="border-b border-gray-800 pb-2">
                <div className="text-sm font-semibold text-gray-200">
                  {data.name_display}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xl font-mono text-white">
                    {data.current_value != null ? Number(data.current_value).toFixed(2) : 'N/A'}
                  </span>
                  <span
                    className={cn(
                      'text-xs px-2 py-0.5 rounded',
                      getStatusColor(data.status_color)
                    )}
                  >
                    {data.status}
                  </span>
                </div>
              </div>

              {/* Step 1: STATE (Trend) */}
              {data.trend_direction && (
                <div className="text-xs text-gray-400">
                  {getTrendIcon(data.trend_direction)} Trending{' '}
                  <span className="text-gray-300">{data.trend_direction.toLowerCase()}</span>{' '}
                  for {data.trend_duration_days} days{' '}
                  <span
                    className={cn(
                      'font-mono',
                      data.trend_change_pct > 0 ? 'text-green-400' : 'text-red-400'
                    )}
                  >
                    ({data.trend_change_pct > 0 ? '+' : ''}
                    {data.trend_change_pct.toFixed(1)}%)
                  </span>
                </div>
              )}

              {/* Step 2-5: FINN Narrative (all steps combined) */}
              <div className="text-sm text-gray-300 leading-relaxed">
                {data.finn_narrative}
              </div>

              {/* Regime context (highlighted) */}
              {data.regime_label && (
                <div className="bg-gray-800/50 border border-gray-700 rounded px-3 py-2">
                  <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">
                    Regime Context
                  </div>
                  <div className="text-xs text-gray-400">
                    {data.regime_interpretation}
                  </div>
                </div>
              )}

              {/* Integrity footer (always visible) */}
              <div className="border-t border-gray-800 pt-2 flex items-center justify-between text-xs">
                <span className="text-gray-500">Data integrity</span>
                <span className={getIntegrityColor(data.integrity_status)}>
                  {data.integrity_status === 'VERIFIED' && '✓ Verified'}
                  {data.integrity_status === 'STALE' && '⚠ Stale data'}
                  {data.integrity_status === 'UNVERIFIED' && '✗ Unverified'}
                </span>
              </div>
            </div>
          )}

          {/* Tooltip arrow (visual pointer) */}
          <div
            className={cn(
              'absolute w-2 h-2 bg-gray-900 border-gray-700 rotate-45',
              side === 'top' && 'bottom-[-5px] left-1/2 -translate-x-1/2 border-b border-r',
              side === 'bottom' && 'top-[-5px] left-1/2 -translate-x-1/2 border-t border-l',
              side === 'left' && 'right-[-5px] top-1/2 -translate-y-1/2 border-t border-r',
              side === 'right' && 'left-[-5px] top-1/2 -translate-y-1/2 border-b border-l'
            )}
          />
        </div>
      )}
    </div>
  )
}
