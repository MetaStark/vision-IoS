/**
 * Candlestick Chart Component (Sprint 1.3)
 * Bloomberg-minimal institutional design
 * Recharts-based with clean visual hierarchy
 * MBB-grade: Clarity + Lineage
 */

'use client'

import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from 'recharts'
import { formatNumber, formatDate } from '@/lib/utils/format'
import { cn } from '@/lib/utils/cn'

interface OHLCVData {
  date: string | Date
  open: number
  high: number
  low: number
  close: number
  volume?: number
}

interface CandlestickChartProps {
  data: OHLCVData[]
  resolution: '1h' | '1d'
  title?: string
  showVolume?: boolean
  source?: string
  height?: number
  className?: string
}

/**
 * Candlestick Chart
 * Uses Recharts Bar chart with custom rendering for OHLC candles
 * Visual hierarchy: Price primary, Volume secondary
 */
export function CandlestickChart({
  data,
  resolution,
  title,
  showVolume = true,
  source,
  height = 400,
  className,
}: CandlestickChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className={cn('flex items-center justify-center', className)} style={{ height }}>
        <p className="text-slate-500">No chart data available</p>
      </div>
    )
  }

  // Transform data for Recharts
  const chartData = data.map((item) => {
    const open = item.open
    const close = item.close
    const isUp = close >= open

    return {
      date: item.date,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume,
      // Recharts Bar chart fields
      candleBody: isUp ? [open, close] : [close, open],
      candleWick: [item.low, item.high],
      isUp,
      // For custom rendering
      bodyHeight: Math.abs(close - open),
      bodyStart: Math.min(open, close),
    }
  })

  // Calculate volume scale (for secondary axis)
  const maxVolume = Math.max(...chartData.map((d) => d.volume || 0))

  return (
    <div className={cn('space-y-2', className)}>
      {/* Header */}
      {(title || source) && (
        <div className="flex items-center justify-between px-2">
          {title && <h3 className="text-sm font-semibold text-slate-900">{title}</h3>}
          {source && (
            <span
              className="data-lineage-indicator"
              title={`Source: ${source}`}
            >
              i
            </span>
          )}
        </div>
      )}

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={chartData}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          {/* Grid - Minimal Bloomberg style */}
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="#e2e8f0"
            vertical={false}
          />

          {/* X Axis */}
          <XAxis
            dataKey="date"
            tickFormatter={(value) => formatDateForResolution(value, resolution)}
            tick={{ fill: '#64748b', fontSize: 11 }}
            stroke="#cbd5e1"
            tickLine={false}
          />

          {/* Y Axis - Price */}
          <YAxis
            yAxisId="price"
            domain={['auto', 'auto']}
            tickFormatter={(value) => `$${formatNumber(value, 0)}`}
            tick={{ fill: '#64748b', fontSize: 11 }}
            stroke="#cbd5e1"
            tickLine={false}
            width={70}
          />

          {/* Y Axis - Volume (if enabled) */}
          {showVolume && (
            <YAxis
              yAxisId="volume"
              orientation="right"
              domain={[0, maxVolume * 4]} // Volume takes bottom 25% of chart
              tickFormatter={(value) => formatNumber(value / 1000000, 1) + 'M'}
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              stroke="#cbd5e1"
              tickLine={false}
              width={60}
            />
          )}

          {/* Tooltip */}
          <Tooltip
            content={<CustomTooltip resolution={resolution} />}
            cursor={{ stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '5 5' }}
          />

          {/* Volume Bars (behind candlesticks) */}
          {showVolume && (
            <Bar
              yAxisId="volume"
              dataKey="volume"
              fill="#cbd5e1"
              opacity={0.3}
              radius={[2, 2, 0, 0]}
            />
          )}

          {/* Candlestick Wicks */}
          <Bar
            yAxisId="price"
            dataKey="candleWick"
            fill="transparent"
            stroke="#64748b"
            strokeWidth={1}
          />

          {/* Candlestick Bodies */}
          <Bar
            yAxisId="price"
            dataKey="candleBody"
            radius={[1, 1, 1, 1]}
          >
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.isUp ? '#10b981' : '#ef4444'}
                stroke={entry.isUp ? '#059669' : '#dc2626'}
                strokeWidth={1}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      {/* Chart Legend */}
      <div className="flex items-center justify-center gap-6 text-xs text-slate-600 pt-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 border border-green-600 rounded-sm" />
          <span>Up</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-red-500 border border-red-600 rounded-sm" />
          <span>Down</span>
        </div>
        {showVolume && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-slate-300 rounded-sm" />
            <span>Volume</span>
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Custom Tooltip Component
 * Displays OHLCV data on hover
 */
function CustomTooltip({ active, payload, resolution }: any) {
  if (!active || !payload || !payload.length) return null

  const data = payload[0].payload
  const isUp = data.isUp

  return (
    <div className="bg-white border border-slate-300 rounded-lg shadow-lg p-3 space-y-2">
      {/* Date */}
      <p className="text-xs font-semibold text-slate-900 border-b border-slate-200 pb-2">
        {formatDateForResolution(data.date, resolution, true)}
      </p>

      {/* OHLC */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="text-slate-600">Open:</div>
        <div className="font-mono text-slate-900">${formatNumber(data.open, 2)}</div>

        <div className="text-slate-600">High:</div>
        <div className="font-mono text-slate-900">${formatNumber(data.high, 2)}</div>

        <div className="text-slate-600">Low:</div>
        <div className="font-mono text-slate-900">${formatNumber(data.low, 2)}</div>

        <div className="text-slate-600">Close:</div>
        <div className={cn('font-mono font-semibold', isUp ? 'text-green-600' : 'text-red-600')}>
          ${formatNumber(data.close, 2)}
        </div>
      </div>

      {/* Volume */}
      {data.volume !== undefined && (
        <div className="pt-2 border-t border-slate-200">
          <div className="grid grid-cols-2 gap-x-4 text-xs">
            <div className="text-slate-600">Volume:</div>
            <div className="font-mono text-slate-900">{formatNumber(data.volume, 0)}</div>
          </div>
        </div>
      )}

      {/* Change */}
      <div className="pt-2 border-t border-slate-200">
        <div className="grid grid-cols-2 gap-x-4 text-xs">
          <div className="text-slate-600">Change:</div>
          <div className={cn('font-semibold', isUp ? 'text-green-600' : 'text-red-600')}>
            {isUp ? '+' : ''}{formatNumber(data.close - data.open, 2)} ({isUp ? '+' : ''}{formatNumber(((data.close - data.open) / data.open) * 100, 2)}%)
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Format date based on resolution
 */
function formatDateForResolution(
  date: string | Date,
  resolution: '1h' | '1d',
  fullFormat: boolean = false
): string {
  const d = typeof date === 'string' ? new Date(date) : date

  if (fullFormat) {
    return resolution === '1h'
      ? d.toLocaleString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })
      : d.toLocaleString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })
  }

  // Compact format for axis
  return resolution === '1h'
    ? d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
