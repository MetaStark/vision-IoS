/**
 * Market Summary Stats Panel (Sprint 1.3)
 * Display key price metrics with lineage
 * Bloomberg-minimal design
 * MBB-grade: Clear hierarchy + data lineage
 */

'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { formatNumber, formatPercent } from '@/lib/utils/format'
import { cn } from '@/lib/utils/cn'

export interface MarketSummaryData {
  asset: string
  resolution: string
  period: string
  latest: {
    date: string
    open: number
    high: number
    low: number
    close: number
    volume?: number
  }
  periodStats: {
    high: number
    low: number
    avgVolume?: number
    change: number
    changePercent: number
  }
  source: string
}

interface MarketSummaryStatsProps {
  data: MarketSummaryData
  className?: string
}

/**
 * Market Summary Stats Panel
 * Shows latest OHLCV + period statistics
 * Visual hierarchy: Latest close prominent, stats secondary
 */
export function MarketSummaryStats({ data, className }: MarketSummaryStatsProps) {
  const isPositive = data.periodStats.change >= 0

  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Market Summary</CardTitle>
          <span
            className="data-lineage-indicator"
            title={`Source: ${data.source}`}
          >
            i
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-600 mt-1">
          <span>{data.asset}</span>
          <span>•</span>
          <span>{data.resolution}</span>
          <span>•</span>
          <span>{data.period}</span>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Latest Price - Prominent */}
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-xs text-slate-600 uppercase font-medium mb-1">
                Latest Close
              </p>
              <p className="text-3xl font-semibold text-slate-900">
                ${formatNumber(data.latest.close, 2)}
              </p>
            </div>
            <div className="text-right">
              <p
                className={cn(
                  'text-lg font-semibold',
                  isPositive ? 'text-green-600' : 'text-red-600'
                )}
              >
                {isPositive ? '+' : ''}
                {formatNumber(data.periodStats.change, 2)}
              </p>
              <p
                className={cn(
                  'text-sm font-medium',
                  isPositive ? 'text-green-600' : 'text-red-600'
                )}
              >
                {isPositive ? '+' : ''}
                {formatPercent(data.periodStats.changePercent)}
              </p>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            As of {new Date(data.latest.date).toLocaleString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </p>
        </div>

        {/* Latest OHLC Grid */}
        <div>
          <p className="text-xs text-slate-600 uppercase font-medium mb-3">
            Latest Candle
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-slate-600">Open</p>
              <p className="text-lg font-mono text-slate-900">
                ${formatNumber(data.latest.open, 2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-600">Close</p>
              <p className="text-lg font-mono text-slate-900">
                ${formatNumber(data.latest.close, 2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-600">High</p>
              <p className="text-lg font-mono text-slate-900">
                ${formatNumber(data.latest.high, 2)}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-600">Low</p>
              <p className="text-lg font-mono text-slate-900">
                ${formatNumber(data.latest.low, 2)}
              </p>
            </div>
            {data.latest.volume !== undefined && (
              <div className="col-span-2">
                <p className="text-xs text-slate-600">Volume</p>
                <p className="text-lg font-mono text-slate-900">
                  {formatNumber(data.latest.volume, 0)}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Period Statistics */}
        <div className="pt-4 border-t border-slate-200">
          <p className="text-xs text-slate-600 uppercase font-medium mb-3">
            Period Statistics ({data.period})
          </p>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-slate-600">Period High</p>
              <p className="font-mono text-slate-900">
                ${formatNumber(data.periodStats.high, 2)}
              </p>
            </div>
            <div>
              <p className="text-slate-600">Period Low</p>
              <p className="font-mono text-slate-900">
                ${formatNumber(data.periodStats.low, 2)}
              </p>
            </div>
            {data.periodStats.avgVolume !== undefined && (
              <div className="col-span-2">
                <p className="text-slate-600">Avg Volume</p>
                <p className="font-mono text-slate-900">
                  {formatNumber(data.periodStats.avgVolume, 0)}
                </p>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
