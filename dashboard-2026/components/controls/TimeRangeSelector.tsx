/**
 * Time Range Selector Component (Sprint 1.3)
 * Resolution-aware time range presets
 * Bloomberg-minimal button group design
 * MBB-grade: Context-aware presets + accessibility
 */

'use client'

import { cn } from '@/lib/utils/cn'
import type { Resolution } from './ResolutionSelector'

export interface TimeRangeConfig {
  value: string
  label: string
  days: number
  resolution: Resolution[]
}

/**
 * Resolution-aware time range presets
 * 1h: Short ranges (24h, 7d, 30d)
 * 1d: Medium-long ranges (1m, 3m, 6m, 1y, all)
 */
export const TIME_RANGE_PRESETS: TimeRangeConfig[] = [
  // Hourly-only presets
  { value: '24h', label: '24H', days: 1, resolution: ['1h'] },
  { value: '7d', label: '7D', days: 7, resolution: ['1h'] },
  { value: '30d', label: '30D', days: 30, resolution: ['1h'] },

  // Daily presets
  { value: '1m', label: '1M', days: 30, resolution: ['1d'] },
  { value: '3m', label: '3M', days: 90, resolution: ['1d'] },
  { value: '6m', label: '6M', days: 180, resolution: ['1d'] },
  { value: '1y', label: '1Y', days: 365, resolution: ['1d'] },
  { value: 'all', label: 'All', days: 9999, resolution: ['1d'] },
]

interface TimeRangeSelectorProps {
  selectedRange: string
  onRangeChange: (range: string) => void
  resolution: Resolution
  className?: string
}

/**
 * Time Range Selector Component
 * Shows presets appropriate for current resolution
 * Visual hierarchy: Active state clearly distinguished
 */
export function TimeRangeSelector({
  selectedRange,
  onRangeChange,
  resolution,
  className,
}: TimeRangeSelectorProps) {
  // Filter presets based on current resolution
  const availableRanges = TIME_RANGE_PRESETS.filter((range) =>
    range.resolution.includes(resolution)
  )

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="text-sm text-slate-600 mr-2">Range:</span>
      <div className="inline-flex rounded-lg border border-slate-300 bg-white p-1">
        {availableRanges.map((range) => (
          <button
            key={range.value}
            onClick={() => onRangeChange(range.value)}
            className={cn(
              'px-3 py-2 text-sm font-medium rounded-md transition-all',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
              selectedRange === range.value
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
            )}
            aria-pressed={selectedRange === range.value}
            aria-label={`Show ${range.label} data`}
          >
            {range.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * Get time range config by value
 */
export function getTimeRangeConfig(value: string): TimeRangeConfig | undefined {
  return TIME_RANGE_PRESETS.find((r) => r.value === value)
}

/**
 * Get default time range for resolution
 */
export function getDefaultTimeRange(resolution: Resolution): string {
  return resolution === '1h' ? '7d' : '1y'
}

/**
 * Calculate date range from preset
 */
export function getDateRange(rangeValue: string): { startDate: Date; endDate: Date } {
  const endDate = new Date()
  const config = getTimeRangeConfig(rangeValue)

  if (!config || config.value === 'all') {
    // For 'all', go back 10 years
    const startDate = new Date()
    startDate.setFullYear(startDate.getFullYear() - 10)
    return { startDate, endDate }
  }

  const startDate = new Date()
  startDate.setDate(startDate.getDate() - config.days)

  return { startDate, endDate }
}
