/**
 * Indicator Selector Component (Sprint 1.3)
 * Toggle technical indicators (RSI, MACD, EMA)
 * Bloomberg-minimal checkbox group design
 * MBB-grade: Clear state + config display
 */

'use client'

import { cn } from '@/lib/utils/cn'
import { LineSeriesConfig } from '@/components/charts/LineChart'

export type IndicatorType = 'ema_20' | 'ema_50' | 'rsi' | 'macd'

export interface IndicatorConfig {
  type: IndicatorType
  name: string
  description: string
  color: string
  chartType: 'overlay' | 'subplot' // overlay on price chart or separate subplot
  yAxisFormatter?: (value: number) => string
}

export const AVAILABLE_INDICATORS: IndicatorConfig[] = [
  {
    type: 'ema_20',
    name: 'EMA (20)',
    description: 'Exponential Moving Average (20 periods)',
    color: '#3b82f6', // blue
    chartType: 'overlay',
  },
  {
    type: 'ema_50',
    name: 'EMA (50)',
    description: 'Exponential Moving Average (50 periods)',
    color: '#8b5cf6', // purple
    chartType: 'overlay',
  },
  {
    type: 'rsi',
    name: 'RSI (14)',
    description: 'Relative Strength Index (14 periods)',
    color: '#f59e0b', // orange
    chartType: 'subplot',
    yAxisFormatter: (value: number) => value.toFixed(0),
  },
  {
    type: 'macd',
    name: 'MACD',
    description: 'Moving Average Convergence Divergence',
    color: '#10b981', // green
    chartType: 'subplot',
  },
]

interface IndicatorSelectorProps {
  selectedIndicators: IndicatorType[]
  onIndicatorsChange: (indicators: IndicatorType[]) => void
  className?: string
}

/**
 * Indicator Selector Component
 * Checkbox group for toggling indicators
 * Visual hierarchy: Checked state clearly distinguished
 */
export function IndicatorSelector({
  selectedIndicators,
  onIndicatorsChange,
  className,
}: IndicatorSelectorProps) {
  const toggleIndicator = (indicator: IndicatorType) => {
    if (selectedIndicators.includes(indicator)) {
      onIndicatorsChange(selectedIndicators.filter((i) => i !== indicator))
    } else {
      onIndicatorsChange([...selectedIndicators, indicator])
    }
  }

  return (
    <div className={cn('space-y-2', className)}>
      <span className="text-sm text-slate-600 font-medium">Indicators:</span>
      <div className="flex flex-wrap gap-2">
        {AVAILABLE_INDICATORS.map((indicator) => {
          const isSelected = selectedIndicators.includes(indicator.type)

          return (
            <button
              key={indicator.type}
              onClick={() => toggleIndicator(indicator.type)}
              className={cn(
                'px-3 py-2 text-sm font-medium rounded-lg border transition-all',
                'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
                isSelected
                  ? 'bg-white border-2 shadow-sm'
                  : 'bg-slate-50 border-slate-300 text-slate-700 hover:bg-slate-100'
              )}
              style={
                isSelected
                  ? { borderColor: indicator.color, color: indicator.color }
                  : undefined
              }
              aria-pressed={isSelected}
              title={indicator.description}
            >
              <div className="flex items-center gap-2">
                {isSelected && (
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: indicator.color }}
                  />
                )}
                <span>{indicator.name}</span>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

/**
 * Get indicator config by type
 */
export function getIndicatorConfig(type: IndicatorType): IndicatorConfig | undefined {
  return AVAILABLE_INDICATORS.find((i) => i.type === type)
}

/**
 * Convert indicator configs to line series configs
 * For use with LineChart component
 */
export function indicatorsToLineSeries(
  indicators: IndicatorType[],
  chartType: 'overlay' | 'subplot'
): LineSeriesConfig[] {
  return indicators
    .map((type) => getIndicatorConfig(type))
    .filter((config): config is IndicatorConfig =>
      config !== undefined && config.chartType === chartType
    )
    .map((config) => ({
      dataKey: config.type,
      name: config.name,
      color: config.color,
      strokeWidth: 2,
      strokeDasharray: config.chartType === 'overlay' ? '5 5' : undefined,
    }))
}
