/**
 * MetricCard Component
 * Display key metrics with value, label, and optional change indicator
 */

import { cn } from '@/lib/utils/cn'
import { getChangeClass, formatChange } from '@/lib/utils/format'

interface MetricCardProps {
  label: string
  value: string | number
  change?: number
  changeLabel?: string
  isPercent?: boolean
  className?: string
  icon?: React.ReactNode
  /** Data lineage - source table/view */
  source?: string
}

export function MetricCard({
  label,
  value,
  change,
  changeLabel,
  isPercent = false,
  className,
  icon,
  source,
}: MetricCardProps) {
  return (
    <div className={cn('metric-card', className)}>
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <p className="metric-label">{label}</p>
            {source && (
              <span
                className="data-lineage-indicator"
                title={`Source: ${source}`}
              >
                i
              </span>
            )}
          </div>
          <p className="metric-value">{value}</p>
          {change !== undefined && (
            <p className={cn('text-sm mt-1 font-medium', getChangeClass(change))}>
              {formatChange(change, 2, isPercent)}
              {changeLabel && <span className="text-slate-500 ml-1">{changeLabel}</span>}
            </p>
          )}
        </div>
        {icon && (
          <div className="text-slate-400">
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}
