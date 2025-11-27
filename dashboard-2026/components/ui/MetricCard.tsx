import { cn, formatCurrency, formatPercent, formatCompact } from '@/lib/utils';
import { StatusBadge } from './StatusBadge';

interface MetricCardProps {
  label: string;
  value: string | number;
  format?: 'currency' | 'percent' | 'compact' | 'raw';
  status?: string;
  trend?: {
    direction: 'up' | 'down' | 'neutral';
    value: number;
  };
  subtitle?: string;
  className?: string;
}

export function MetricCard({
  label,
  value,
  format = 'raw',
  status,
  trend,
  subtitle,
  className
}: MetricCardProps) {
  const formattedValue = (() => {
    if (typeof value === 'string') return value;
    switch (format) {
      case 'currency': return formatCurrency(value);
      case 'percent': return formatPercent(value);
      case 'compact': return formatCompact(value);
      default: return value.toString();
    }
  })();

  const trendColor = trend?.direction === 'up'
    ? 'text-trust-green'
    : trend?.direction === 'down'
      ? 'text-trust-red'
      : 'text-gray-400';

  const trendIcon = trend?.direction === 'up'
    ? '↑'
    : trend?.direction === 'down'
      ? '↓'
      : '→';

  return (
    <div className={cn(
      'bg-fjord-800/50 border border-fjord-700 rounded-lg p-4',
      className
    )}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-400">{label}</span>
        {status && <StatusBadge status={status} size="sm" />}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-semibold text-white">{formattedValue}</span>
        {trend && (
          <span className={cn('text-sm font-medium', trendColor)}>
            {trendIcon} {formatPercent(trend.value)}
          </span>
        )}
      </div>
      {subtitle && (
        <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
      )}
    </div>
  );
}
