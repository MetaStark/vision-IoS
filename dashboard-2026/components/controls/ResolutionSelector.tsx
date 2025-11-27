/**
 * Resolution Selector Component (Sprint 1.3)
 * Switch between 1h and 1d resolution
 * Bloomberg-minimal toggle design
 * MBB-grade: Clear selection state
 */

'use client'

import { cn } from '@/lib/utils/cn'

export type Resolution = '1h' | '1d'

export interface ResolutionConfig {
  value: Resolution
  label: string
  description: string
}

export const AVAILABLE_RESOLUTIONS: ResolutionConfig[] = [
  { value: '1h', label: '1H', description: 'Hourly candles' },
  { value: '1d', label: '1D', description: 'Daily candles' },
]

interface ResolutionSelectorProps {
  selectedResolution: Resolution
  onResolutionChange: (resolution: Resolution) => void
  className?: string
}

/**
 * Resolution Selector Component
 * Minimal toggle for resolution switching
 * Visual hierarchy: Active state clearly distinguished
 */
export function ResolutionSelector({
  selectedResolution,
  onResolutionChange,
  className,
}: ResolutionSelectorProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="text-sm text-slate-600 mr-2">Resolution:</span>
      <div className="inline-flex rounded-lg border border-slate-300 bg-white p-1">
        {AVAILABLE_RESOLUTIONS.map((res) => (
          <button
            key={res.value}
            onClick={() => onResolutionChange(res.value)}
            className={cn(
              'px-4 py-2 text-sm font-medium rounded-md transition-all',
              'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
              selectedResolution === res.value
                ? 'bg-primary-600 text-white shadow-sm'
                : 'text-slate-700 hover:bg-slate-100 hover:text-slate-900'
            )}
            aria-pressed={selectedResolution === res.value}
            aria-label={res.description}
            title={res.description}
          >
            {res.label}
          </button>
        ))}
      </div>
    </div>
  )
}
