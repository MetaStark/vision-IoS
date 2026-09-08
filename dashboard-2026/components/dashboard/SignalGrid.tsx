/**
 * Signal Grid Component (Zone 2)
 * 30-Second Understanding: "Why Is This Happening?"
 *
 * Authority: Dashboard UX Specification 2026 v2.0
 * North Star: Narrative Completion < 30 seconds
 *
 * Displays:
 * - 4 ACE family cards (TREND, REVERSION, VOLATILITY, BREAKOUT)
 * - Signal direction per family
 * - Confidence/conviction bars
 * - Primary drivers
 * - Consensus analysis
 */

'use client'

import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils/cn'
import {
  TrendingUp,
  RefreshCw,
  Activity,
  Zap,
  ArrowUp,
  ArrowDown,
  Minus
} from 'lucide-react'

interface SignalGridProps {
  listingId?: string
  className?: string
  refreshKey?: number
}

interface FamilySignal {
  family_id: string
  family_name: 'TREND_FOLLOWING' | 'MEAN_REVERSION' | 'VOLATILITY' | 'BREAKOUT'
  signal_direction: 'LONG' | 'SHORT' | 'NEUTRAL'
  allocation_pct: number
  confidence_score: number
  conviction_strength: number
  primary_driver: string | null
  driver_strategies: string[]
  strategy_count: number
  meta_weight: number | null
  meta_contribution_pct: number | null
  family_color: string
  family_icon: string
}

interface FamiliesResponse {
  families: FamilySignal[]
  consensus: {
    total: number
    long: number
    short: number
    neutral: number
    alignment: string
    finn_interpretation: string
  }
}

export function SignalGrid({ listingId = 'LST_BTC_XCRYPTO', className, refreshKey = 0 }: SignalGridProps) {
  const [data, setData] = useState<FamiliesResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch(`/api/finn/families?listing_id=${listingId}`)

        if (!response.ok) {
          throw new Error('Failed to fetch family signals')
        }

        const result = await response.json()
        setData(result)
      } catch (err) {
        console.error('[Signal Grid] Fetch error:', err)
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [listingId, refreshKey])

  const getFamilyIcon = (iconName: string) => {
    switch (iconName) {
      case 'trend-up':
        return <TrendingUp className="h-5 w-5" />
      case 'refresh-cw':
        return <RefreshCw className="h-5 w-5" />
      case 'activity':
        return <Activity className="h-5 w-5" />
      case 'zap':
        return <Zap className="h-5 w-5" />
      default:
        return <Minus className="h-5 w-5" />
    }
  }

  const getSignalIcon = (direction: string) => {
    switch (direction) {
      case 'LONG':
        return <ArrowUp className="h-4 w-4" />
      case 'SHORT':
        return <ArrowDown className="h-4 w-4" />
      default:
        return <Minus className="h-4 w-4" />
    }
  }

  const getSignalColor = (direction: string) => {
    switch (direction) {
      case 'LONG':
        return 'text-green-400 bg-green-950/30 border-green-700'
      case 'SHORT':
        return 'text-red-400 bg-red-950/30 border-red-700'
      default:
        return 'text-blue-400 bg-blue-950/30 border-blue-700'
    }
  }

  const getFamilyColor = (color: string) => {
    switch (color) {
      case 'blue':
        return 'border-blue-700/50 bg-blue-950/20'
      case 'green':
        return 'border-green-700/50 bg-green-950/20'
      case 'yellow':
        return 'border-yellow-700/50 bg-yellow-950/20'
      case 'purple':
        return 'border-purple-700/50 bg-purple-950/20'
      default:
        return 'border-gray-700/50 bg-gray-900/20'
    }
  }

  if (isLoading) {
    return (
      <div className={cn('space-y-4', className)}>
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="bg-gray-900 border border-gray-800 rounded-lg p-4 h-48 animate-pulse"
            />
          ))}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className={cn('bg-gray-900 border border-red-900/50 rounded-lg p-6', className)}>
        <div className="text-red-400">
          <div className="font-semibold mb-2">Error Loading Family Signals</div>
          <div className="text-sm text-gray-500">{error || 'No data available'}</div>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Consensus summary bar */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-400">
            <span className="text-gray-300 font-semibold">Family Consensus:</span>{' '}
            {data.consensus.finn_interpretation}
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1">
              <ArrowUp className="h-3 w-3 text-green-400" />
              <span className="text-gray-400">{data.consensus.long} LONG</span>
            </div>
            <div className="flex items-center gap-1">
              <ArrowDown className="h-3 w-3 text-red-400" />
              <span className="text-gray-400">{data.consensus.short} SHORT</span>
            </div>
            <div className="flex items-center gap-1">
              <Minus className="h-3 w-3 text-blue-400" />
              <span className="text-gray-400">{data.consensus.neutral} NEUTRAL</span>
            </div>
          </div>
        </div>
      </div>

      {/* 4 Family cards grid */}
      <div className="grid grid-cols-4 gap-4">
        {data.families.map((family) => (
          <div
            key={family.family_id}
            className={cn(
              'bg-gray-900 border rounded-lg p-4',
              'transition-all duration-150 hover:shadow-lg hover:scale-[1.02]',
              getFamilyColor(family.family_color)
            )}
            style={{
              boxShadow: '0 0 1px rgba(156, 163, 175, 0.15)'
            }}
          >
            {/* Header: Icon + Name */}
            <div className="flex items-center gap-2 mb-3">
              <div className="text-gray-400">{getFamilyIcon(family.family_icon)}</div>
              <div className="text-xs font-semibold text-gray-300 uppercase tracking-wide">
                {family.family_name.replace('_', ' ')}
              </div>
            </div>

            {/* Signal direction badge */}
            <div className="mb-4">
              <div
                className={cn(
                  'inline-flex items-center gap-1 px-3 py-1 rounded border text-sm font-semibold',
                  getSignalColor(family.signal_direction)
                )}
              >
                {getSignalIcon(family.signal_direction)}
                {family.signal_direction}
              </div>
            </div>

            {/* Allocation */}
            <div className="mb-3">
              <div className="text-2xl font-bold font-mono text-white">
                {parseFloat(family.allocation_pct as any) > 0 ? '+' : ''}
                {parseFloat(family.allocation_pct as any).toFixed(0)}%
              </div>
              <div className="text-xs text-gray-500">Allocation</div>
            </div>

            {/* Confidence bar */}
            <div className="mb-3">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-500">Confidence</span>
                <span className="text-gray-400">{(parseFloat(family.confidence_score as any) * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full transition-all duration-300',
                    parseFloat(family.confidence_score as any) > 0.7 ? 'bg-green-500' :
                    parseFloat(family.confidence_score as any) > 0.5 ? 'bg-yellow-500' :
                    'bg-gray-600'
                  )}
                  style={{ width: `${parseFloat(family.confidence_score as any) * 100}%` }}
                />
              </div>
            </div>

            {/* Conviction strength */}
            <div className="mb-3">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-gray-500">Conviction</span>
                <span className="text-gray-400">{(parseFloat(family.conviction_strength as any) * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full transition-all duration-300',
                    parseFloat(family.conviction_strength as any) > 0.7 ? 'bg-blue-500' :
                    parseFloat(family.conviction_strength as any) > 0.5 ? 'bg-blue-400' :
                    'bg-gray-600'
                  )}
                  style={{ width: `${parseFloat(family.conviction_strength as any) * 100}%` }}
                />
              </div>
            </div>

            {/* Primary driver */}
            {family.primary_driver && (
              <div className="border-t border-gray-800 pt-3">
                <div className="text-xs text-gray-500 mb-1">Primary Driver</div>
                <div className="text-xs text-gray-300 font-mono truncate">
                  {family.primary_driver}
                </div>
                <div className="text-xs text-gray-600 mt-1">
                  {family.strategy_count} strategies
                </div>
              </div>
            )}

            {/* Meta contribution */}
            {family.meta_contribution_pct !== null && (
              <div className="text-xs text-gray-600 mt-2">
                Contributes {parseFloat(family.meta_contribution_pct as any).toFixed(1)}% to meta
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
