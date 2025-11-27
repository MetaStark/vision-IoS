/**
 * Line Chart Component (Sprint 1.3)
 * For price trends and indicator overlays
 * Bloomberg-minimal institutional design
 * MBB-grade: Multi-series support + Lineage
 */

'use client'

import {
  ResponsiveContainer,
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { formatNumber } from '@/lib/utils/format'
import { cn } from '@/lib/utils/cn'

export interface LineSeriesConfig {
  dataKey: string
  name: string
  color: string
  strokeWidth?: number
  strokeDasharray?: string
  yAxisId?: string
}

interface LineChartProps {
  data: Array<Record<string, any>>
  series: LineSeriesConfig[]
  xAxisKey?: string
  resolution?: '1h' | '1d'
  title?: string
  source?: string
  height?: number
  className?: string
  showLegend?: boolean
  yAxisFormatter?: (value: number) => string
}

/**
 * Line Chart Component
 * Supports multiple line series for price and indicators
 * Visual hierarchy: Primary line bold, indicators lighter
 */
export function LineChart({
  data,
  series,
  xAxisKey = 'date',
  resolution = '1d',
  title,
  source,
  height = 400,
  className,
  showLegend = true,
  yAxisFormatter = (value) => `$${formatNumber(value, 2)}`,
}: LineChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className={cn('flex items-center justify-center', className)} style={{ height }}>
        <p className="text-slate-500">No chart data available</p>
      </div>
    )
  }

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
        <RechartsLineChart
          data={data}
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
            dataKey={xAxisKey}
            tickFormatter={(value) => formatDateForResolution(value, resolution)}
            tick={{ fill: '#64748b', fontSize: 11 }}
            stroke="#cbd5e1"
            tickLine={false}
          />

          {/* Y Axis */}
          <YAxis
            domain={['auto', 'auto']}
            tickFormatter={yAxisFormatter}
            tick={{ fill: '#64748b', fontSize: 11 }}
            stroke="#cbd5e1"
            tickLine={false}
            width={70}
          />

          {/* Tooltip */}
          <Tooltip
            content={<CustomTooltip resolution={resolution} series={series} />}
            cursor={{ stroke: '#94a3b8', strokeWidth: 1, strokeDasharray: '5 5' }}
          />

          {/* Legend */}
          {showLegend && (
            <Legend
              wrapperStyle={{ paddingTop: '20px' }}
              iconType="line"
              formatter={(value) => <span className="text-xs text-slate-700">{value}</span>}
            />
          )}

          {/* Line Series */}
          {series.map((s) => (
            <Line
              key={s.dataKey}
              type="monotone"
              dataKey={s.dataKey}
              name={s.name}
              stroke={s.color}
              strokeWidth={s.strokeWidth || 2}
              strokeDasharray={s.strokeDasharray}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, fill: '#fff' }}
              yAxisId={s.yAxisId || 0}
            />
          ))}
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  )
}

/**
 * Custom Tooltip Component
 * Displays all series values on hover
 */
function CustomTooltip({ active, payload, resolution, series }: any) {
  if (!active || !payload || !payload.length) return null

  const dataPoint = payload[0].payload

  return (
    <div className="bg-white border border-slate-300 rounded-lg shadow-lg p-3 space-y-2">
      {/* Date */}
      <p className="text-xs font-semibold text-slate-900 border-b border-slate-200 pb-2">
        {formatDateForResolution(dataPoint.date, resolution, true)}
      </p>

      {/* Series Values */}
      <div className="space-y-1">
        {series.map((s: LineSeriesConfig) => {
          const value = dataPoint[s.dataKey]
          if (value === undefined || value === null) return null

          return (
            <div key={s.dataKey} className="flex items-center justify-between gap-4 text-xs">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-0.5 rounded"
                  style={{ backgroundColor: s.color }}
                />
                <span className="text-slate-600">{s.name}:</span>
              </div>
              <span className="font-mono text-slate-900 font-semibold">
                {typeof value === 'number' ? formatNumber(value, 2) : value}
              </span>
            </div>
          )
        })}
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
