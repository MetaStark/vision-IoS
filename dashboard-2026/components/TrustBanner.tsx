/**
 * Trust Banner Component
 * Displays system health at a glance (ADR-005 Section 4.1)
 *
 * Data Lineage:
 * - fhq_validation.gate_status
 * - fhq_validation.data_freshness
 * - fhq_finn.cds_metrics
 * - fhq_governance.economic_safety
 */

import { cn, getStatusColor } from '@/lib/utils';
import { StatusBadge } from './ui/StatusBadge';

interface TrustBannerProps {
  systemHealth: {
    gates: {
      allPass: boolean;
      summary: string;
    };
    freshness: {
      status: string;
      fresh: number;
      stale: number;
    };
    cds: {
      score: number;
      tier: string;
    } | null;
    economic: {
      status: string;
    };
    overall: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  };
}

export function TrustBanner({ systemHealth }: TrustBannerProps) {
  const { gates, freshness, cds, economic, overall } = systemHealth;

  const overallColor = overall === 'HEALTHY'
    ? 'border-trust-green/30 bg-trust-green/5'
    : overall === 'DEGRADED'
      ? 'border-trust-yellow/30 bg-trust-yellow/5'
      : 'border-trust-red/30 bg-trust-red/5';

  const overallIconColor = overall === 'HEALTHY'
    ? 'text-trust-green'
    : overall === 'DEGRADED'
      ? 'text-trust-yellow'
      : 'text-trust-red';

  return (
    <div className={cn(
      'border rounded-lg px-4 py-3',
      overallColor
    )}>
      <div className="flex items-center justify-between flex-wrap gap-4">
        {/* Overall Status */}
        <div className="flex items-center gap-3">
          <div className={cn('w-3 h-3 rounded-full animate-pulse', overallIconColor.replace('text-', 'bg-'))} />
          <span className="font-medium text-white">System Status:</span>
          <StatusBadge status={overall} size="md" />
        </div>

        {/* Metrics */}
        <div className="flex items-center gap-6 text-sm">
          {/* Gates */}
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Gates:</span>
            <span className={cn(
              'font-medium',
              gates.allPass ? 'text-trust-green' : 'text-trust-yellow'
            )}>
              {gates.summary}
            </span>
          </div>

          {/* Freshness */}
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Data:</span>
            <span className={cn(
              'font-medium',
              freshness.status === 'FRESH' ? 'text-trust-green' :
              freshness.status === 'STALE' ? 'text-trust-yellow' : 'text-trust-red'
            )}>
              {freshness.fresh}/{freshness.fresh + freshness.stale} fresh
            </span>
          </div>

          {/* CDS */}
          {cds && (
            <div className="flex items-center gap-2">
              <span className="text-gray-400">CDS:</span>
              <span className={cn(
                'font-medium',
                cds.tier === 'low' ? 'text-trust-green' :
                cds.tier === 'medium' ? 'text-trust-yellow' : 'text-trust-red'
              )}>
                {(cds.score * 100).toFixed(0)}% ({cds.tier})
              </span>
            </div>
          )}

          {/* Economic Safety */}
          <div className="flex items-center gap-2">
            <span className="text-gray-400">Economic:</span>
            <StatusBadge status={economic.status} size="sm" />
          </div>
        </div>

        {/* ADR-005 Badge */}
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>ADR-005 Compliant</span>
          <svg className="w-4 h-4 text-trust-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
      </div>
    </div>
  );
}

// Loading state
export function TrustBannerSkeleton() {
  return (
    <div className="border border-fjord-700 rounded-lg px-4 py-3 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-fjord-600" />
          <div className="h-4 w-32 bg-fjord-600 rounded" />
        </div>
        <div className="flex items-center gap-6">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-4 w-24 bg-fjord-600 rounded" />
          ))}
        </div>
      </div>
    </div>
  );
}
