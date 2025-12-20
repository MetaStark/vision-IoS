/**
 * StatusBadge Component
 * Displays status indicators with consistent styling
 */

import { cn } from '@/lib/utils/cn'

export type BadgeVariant =
  | 'fresh'
  | 'stale'
  | 'outdated'
  | 'pass'
  | 'fail'
  | 'warning'
  | 'info'
  | 'default'

interface StatusBadgeProps {
  variant: BadgeVariant
  children: React.ReactNode
  className?: string
  icon?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  fresh: 'status-fresh',
  stale: 'status-stale',
  outdated: 'status-outdated',
  pass: 'status-pass',
  fail: 'status-fail',
  warning: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700',
  info: 'bg-blue-900/50 text-blue-300 border border-blue-700',
  default: 'bg-slate-800 text-slate-300 border border-slate-600',
}

export function StatusBadge({
  variant,
  children,
  className,
  icon,
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'status-badge',
        variantStyles[variant],
        className
      )}
    >
      {icon && <span className="mr-1">{icon}</span>}
      {children}
    </span>
  )
}
