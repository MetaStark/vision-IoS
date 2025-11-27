import { cn, getStatusColor, getAgentColor } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'status' | 'agent';
}

export function StatusBadge({ status, size = 'md', variant = 'status' }: StatusBadgeProps) {
  const colorClass = variant === 'agent' ? getAgentColor(status) : getStatusColor(status);

  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-xs',
    lg: 'px-3 py-1.5 text-sm',
  };

  return (
    <span className={cn(
      'inline-flex items-center rounded-full font-medium border',
      colorClass,
      sizeClasses[size]
    )}>
      {status}
    </span>
  );
}

interface GateStatusBadgeProps {
  gate: string;
  status: 'PASS' | 'FAIL' | 'PENDING' | 'BLOCKED';
}

export function GateStatusBadge({ gate, status }: GateStatusBadgeProps) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-mono text-gray-400">{gate}</span>
      <StatusBadge status={status} size="sm" />
    </div>
  );
}
