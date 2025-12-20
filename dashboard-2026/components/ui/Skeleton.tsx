/**
 * Skeleton Loader Component
 * Loading state placeholder for data-fetching components
 * MBB-grade: Clean, unobtrusive, institutional design
 */

import { cn } from '@/lib/utils/cn'

interface SkeletonProps {
  className?: string
  variant?: 'text' | 'card' | 'metric' | 'chart' | 'badge'
  width?: string
  height?: string
  count?: number
}

export function Skeleton({
  className,
  variant = 'text',
  width,
  height,
  count = 1,
}: SkeletonProps) {
  const skeletons = Array.from({ length: count })

  const baseClasses = 'skeleton'

  const variantClasses = {
    text: 'h-4 w-full',
    card: 'h-48 w-full rounded-lg',
    metric: 'h-24 w-full rounded-lg',
    chart: 'h-96 w-full rounded-lg',
    badge: 'h-6 w-20 rounded-full',
  }

  const variantClass = variantClasses[variant] || variantClasses.text

  return (
    <>
      {skeletons.map((_, index) => (
        <div
          key={index}
          className={cn(
            baseClasses,
            variantClass,
            className
          )}
          style={{
            width: width || undefined,
            height: height || undefined,
          }}
        />
      ))}
    </>
  )
}

/**
 * Skeleton Card - Specific skeleton for Card components
 */
export function SkeletonCard() {
  return (
    <div className="card p-6 space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-32" />
        <Skeleton variant="badge" />
      </div>
      <Skeleton className="h-4 w-full" count={3} />
      <Skeleton className="h-8 w-24" />
    </div>
  )
}

/**
 * Skeleton Metric Card - Specific skeleton for MetricCard
 */
export function SkeletonMetricCard() {
  return (
    <div className="metric-card space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-3 w-20" />
    </div>
  )
}

/**
 * Skeleton Table - For data tables
 */
export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4">
          {Array.from({ length: cols }).map((_, colIndex) => (
            <Skeleton key={colIndex} className="h-6 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

/**
 * Skeleton Text Block - For paragraph content
 */
export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className="h-4"
          width={i === lines - 1 ? '80%' : '100%'}
        />
      ))}
    </div>
  )
}
