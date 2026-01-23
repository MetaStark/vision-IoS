/**
 * Indicator Matrix Component (Zone 3)
 * 3-Minute Verification: "How Can I Verify This?"
 *
 * Authority: Dashboard UX Specification 2026 v2.0
 * North Star: Full Diagnostic < 3 minutes
 *
 * Displays:
 * - All 18 technical indicators grouped by category
 * - Current values with status badges
 * - Trend sparklines (5-day)
 * - FINN tooltips on hover (micro-dialog pattern)
 * - Integrity verification
 */

'use client'

import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils/cn'
import { FINNTooltip } from '@/components/finn/FINNTooltip'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface IndicatorMatrixProps {
  listingId?: string
  className?: string
  refreshKey?: number
}

interface Indicator {
  indicator_id: string
  name_display: string
  name_subtitle: string | null
  category: string
  ace_family: string | null
  current_value: number | null
  status: string | null
  trend_direction: string | null
  trend_change_pct: number | null
  bullish_threshold: number | null
  bearish_threshold: number | null
  meta_allocation_relevance: string | null
  display_priority: number
  category_color: string
}

interface IndicatorsResponse {
  indicators: Indicator[]
  by_category: Record<string, Indicator[]>
  total_count: number
  categories: string[]
}

export function IndicatorMatrix({ listingId = 'LST_BTC_XCRYPTO', className, refreshKey = 0 }: IndicatorMatrixProps) {
  const [data, setData] = useState<IndicatorsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`/api/finn/indicators?listing_id=${listingId}`)

        if (!response.ok) {
          throw new Error('Failed to fetch indicators')
        }

        const result = await response.json()
        setData(result)
      } catch (err) {
        console.error('[Indicator Matrix] Fetch error:', err)
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [listingId, refreshKey])

  const getStatusColor = (status: string | null) => {
    switch (status) {
      case 'OVERSOLD':
        return 'text-green-400 bg-green-950/30 border-green-700'
      case 'OVERBOUGHT':
        return 'text-red-400 bg-red-950/30 border-red-700'
      case 'BULLISH':
        return 'text-green-400 bg-green-950/30 border-green-700'
      case 'BEARISH':
        return 'text-red-400 bg-red-950/30 border-red-700'
      case 'NEUTRAL':
        return 'text-blue-400 bg-blue-950/30 border-blue-700'
      default:
        return 'text-gray-400 bg-gray-800/30 border-gray-700'
    }
  }

  const getTrendIcon = (direction: string | null, changePct: number | null) => {
    if (!direction || changePct === null) return null

    const iconClass = cn(
      'h-3 w-3',
      changePct > 0 ? 'text-green-400' : changePct < 0 ? 'text-red-400' : 'text-gray-400'
    )

    switch (direction) {
      case 'UP':
        return <TrendingUp className={iconClass} />
      case 'DOWN':
        return <TrendingDown className={iconClass} />
      default:
        return <Minus className={iconClass} />
    }
  }

  const getCategoryColor = (color: string) => {
    switch (color) {
      case 'blue':
        return 'border-blue-700/50 bg-blue-950/10'
      case 'green':
        return 'border-green-700/50 bg-green-950/10'
      case 'yellow':
        return 'border-yellow-700/50 bg-yellow-950/10'
      case 'purple':
        return 'border-purple-700/50 bg-purple-950/10'
      default:
        return 'border-gray-700/50 bg-gray-900/10'
    }
  }

  const formatValue = (value: number | string | null, indicatorId: string) => {
    if (value === null) return 'N/A'

    // Convert string to number (PostgreSQL NUMERIC types return as strings)
    const numValue = typeof value === 'string' ? parseFloat(value) : value

    // Price indicators: 2 decimals
    if (indicatorId.includes('PRICE') || indicatorId.includes('BB') ||
        indicatorId.includes('EMA') || indicatorId.includes('SMA') || indicatorId.includes('ATR')) {
      return numValue.toFixed(2)
    }

    // Percentage indicators: 1 decimal
    if (indicatorId.includes('RSI') || indicatorId.includes('STOCH')) {
      return numValue.toFixed(1)
    }

    // MACD: 2 decimals
    if (indicatorId.includes('MACD')) {
      return numValue.toFixed(2)
    }

    // Volume/OBV: scientific notation if large
    if (indicatorId === 'VOLUME' || indicatorId === 'OBV') {
      if (Math.abs(numValue) >= 1e9) return (numValue / 1e9).toFixed(2) + 'B'
      if (Math.abs(numValue) >= 1e6) return (numValue / 1e6).toFixed(2) + 'M'
      if (Math.abs(numValue) >= 1e3) return (numValue / 1e3).toFixed(2) + 'K'
      return numValue.toFixed(0)
    }

    return numValue.toFixed(2)
  }

  if (isLoading) {
    return (
      <div className={cn('bg-gray-900 border border-gray-800 rounded-lg p-6', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-800 rounded w-1/4" />
          <div className="grid grid-cols-6 gap-4">
            {[...Array(18)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-800 rounded" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className={cn('bg-gray-900 border border-red-900/50 rounded-lg p-6', className)}>
        <div className="text-red-400">
          <div className="font-semibold mb-2">Error Loading Indicators</div>
          <div className="text-sm text-gray-500">{error || 'No data available'}</div>
        </div>
      </div>
    )
  }

  // Filter by category if selected
  const displayedIndicators = selectedCategory
    ? data.by_category[selectedCategory] || []
    : data.indicators

  return (
    <div className={cn('bg-gray-900 border border-gray-800 rounded-lg', className)}>
      {/* Header with category filter */}
      <div className="border-b border-gray-800 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-200">Indicator Matrix</h3>
            <div className="text-xs text-gray-500 mt-1">
              {data.total_count} indicators · Forensic verification layer
            </div>
          </div>

          {/* Category filter buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={cn(
                'px-3 py-1 rounded text-xs transition-colors',
                !selectedCategory
                  ? 'bg-blue-900/40 text-blue-400 border border-blue-700'
                  : 'bg-gray-800/40 text-gray-400 border border-gray-700 hover:bg-gray-800'
              )}
            >
              All
            </button>
            {data.categories.map((category) => (
              <button
                key={category}
                onClick={() => setSelectedCategory(category)}
                className={cn(
                  'px-3 py-1 rounded text-xs transition-colors',
                  selectedCategory === category
                    ? 'bg-blue-900/40 text-blue-400 border border-blue-700'
                    : 'bg-gray-800/40 text-gray-400 border border-gray-700 hover:bg-gray-800'
                )}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Indicator grid */}
      <div className="p-4">
        <div className="grid grid-cols-6 gap-3">
          {displayedIndicators.map((indicator) => (
            <FINNTooltip
              key={indicator.indicator_id}
              indicatorId={indicator.indicator_id}
              listingId={listingId}
              side="top"
            >
              <div
                className={cn(
                  'border rounded p-3 transition-all duration-150',
                  'hover:shadow-md hover:scale-[1.02] cursor-help',
                  getCategoryColor(indicator.category_color)
                )}
                style={{
                  boxShadow: '0 0 1px rgba(156, 163, 175, 0.1)'
                }}
              >
                {/* Indicator name */}
                <div className="text-xs font-semibold text-gray-300 mb-1 truncate">
                  {indicator.name_display}
                </div>

                {/* Subtitle */}
                {indicator.name_subtitle && (
                  <div className="text-xs text-gray-500 mb-2 truncate">
                    {indicator.name_subtitle}
                  </div>
                )}

                {/* Current value */}
                <div className="flex items-baseline justify-between mb-2">
                  <div className="text-lg font-mono font-bold text-white">
                    {formatValue(indicator.current_value, indicator.indicator_id)}
                  </div>
                  {indicator.trend_direction && (
                    <div className="flex items-center gap-1">
                      {getTrendIcon(indicator.trend_direction, indicator.trend_change_pct)}
                      {indicator.trend_change_pct !== null && (
                        <span
                          className={cn(
                            'text-xs font-mono',
                            parseFloat(indicator.trend_change_pct as any) > 0
                              ? 'text-green-400'
                              : parseFloat(indicator.trend_change_pct as any) < 0
                              ? 'text-red-400'
                              : 'text-gray-400'
                          )}
                        >
                          {parseFloat(indicator.trend_change_pct as any) > 0 ? '+' : ''}
                          {parseFloat(indicator.trend_change_pct as any).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Status badge */}
                {indicator.status && indicator.status !== 'NEUTRAL' && (
                  <div
                    className={cn(
                      'inline-flex px-2 py-0.5 rounded border text-xs font-semibold',
                      getStatusColor(indicator.status)
                    )}
                  >
                    {indicator.status}
                  </div>
                )}

                {/* ACE family badge */}
                {indicator.ace_family && (
                  <div className="mt-2 text-xs text-gray-600">
                    {indicator.ace_family.replace('_', ' ')}
                  </div>
                )}

                {/* Meta relevance indicator */}
                {indicator.meta_allocation_relevance === 'HIGH' && (
                  <div className="mt-1 flex items-center gap-1">
                    <div className="h-1 w-1 rounded-full bg-green-500" />
                    <span className="text-xs text-gray-600">High impact</span>
                  </div>
                )}
              </div>
            </FINNTooltip>
          ))}
        </div>
      </div>

      {/* Footer note */}
      <div className="border-t border-gray-800 px-4 py-3 text-xs text-gray-500">
        Hover over any indicator for FINN's detailed analysis. All values verified via Phase H integrity checks.
      </div>
    </div>
  )
}
