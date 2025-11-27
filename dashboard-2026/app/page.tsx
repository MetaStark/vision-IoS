/**
 * Overview Page - Vision-IoS Dashboard
 * Main landing page with system health overview (ADR-005 Section 4.1)
 *
 * Data Lineage:
 * - fhq_validation.gate_status
 * - fhq_validation.data_freshness
 * - fhq_finn.cds_metrics
 * - fhq_finn.serper_events
 * - fhq_governance.economic_safety
 * - fhq_data.price_series
 */

import { Card, DataLineageIndicator } from '@/components/ui/Card';
import { MetricCard } from '@/components/ui/MetricCard';
import { StatusBadge, GateStatusBadge } from '@/components/ui/StatusBadge';
import { SkeletonCard, SkeletonMetricCard } from '@/components/ui/Skeleton';
import {
  getSystemHealth,
  getLatestCds,
  getDataFreshness,
  getLatestPrice,
  getHighRelevanceEvents,
  getIosModules,
  getRecentAuditLogs,
} from '@/lib/data';
import { formatCurrency, formatRelativeTime, cn } from '@/lib/utils';
import { Suspense } from 'react';

export const dynamic = 'force-dynamic';

async function OverviewMetrics() {
  const [btcPrice, ethPrice, systemHealth] = await Promise.all([
    getLatestPrice('BTC-USD'),
    getLatestPrice('ETH-USD'),
    getSystemHealth(),
  ]);

  const metrics = [
    {
      label: 'BTC Price',
      value: btcPrice?.close || 0,
      format: 'currency' as const,
      status: 'LIVE',
    },
    {
      label: 'ETH Price',
      value: ethPrice?.close || 0,
      format: 'currency' as const,
      status: 'LIVE',
    },
    {
      label: 'System Health',
      value: systemHealth.overall,
      format: 'raw' as const,
      status: systemHealth.overall,
    },
    {
      label: 'CDS Score',
      value: systemHealth.cds ? `${(systemHealth.cds.score * 100).toFixed(0)}%` : 'N/A',
      format: 'raw' as const,
      status: systemHealth.cds?.tier || 'unknown',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metrics.map((metric) => (
        <MetricCard
          key={metric.label}
          label={metric.label}
          value={metric.value}
          format={metric.format}
          status={metric.status}
        />
      ))}
    </div>
  );
}

async function GatesSummary() {
  const systemHealth = await getSystemHealth();
  const { gates } = systemHealth;

  return (
    <Card
      title="Gate Status"
      subtitle="ADR-004 Change Gates"
      lineage={['fhq_validation.gate_status']}
    >
      <div className="space-y-3">
        {gates.all.map((gate) => (
          <div key={gate.gateId} className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm text-gray-400">{gate.gateName}</span>
              <span className="text-xs text-gray-500">{gate.gateName === 'G0' ? 'Syntax' :
                gate.gateName === 'G1' ? 'Technical' :
                gate.gateName === 'G2' ? 'Governance' :
                gate.gateName === 'G3' ? 'Audit' : 'CEO Approval'}</span>
            </div>
            <StatusBadge status={gate.status} size="sm" />
          </div>
        ))}
      </div>
    </Card>
  );
}

async function DataFreshnessSummary() {
  const freshness = await getDataFreshness();

  return (
    <Card
      title="Data Freshness"
      subtitle="Multi-asset freshness status"
      lineage={['fhq_validation.data_freshness']}
    >
      <div className="space-y-3">
        {freshness.map((f) => (
          <div key={`${f.ticker}-${f.resolution}`} className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="font-medium text-white">{f.ticker}</span>
              <span className="text-xs text-gray-500 font-mono">{f.resolution}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400">{f.freshnessMinutes}m ago</span>
              <StatusBadge status={f.status} size="sm" />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

async function CdsSummary() {
  const cds = await getLatestCds();

  if (!cds) {
    return (
      <Card title="CDS Metrics" subtitle="Cognitive Dissonance Score">
        <p className="text-gray-400">No CDS data available</p>
      </Card>
    );
  }

  const conflicts = cds.topConflicts ? JSON.parse(cds.topConflicts) : [];

  return (
    <Card
      title="CDS Metrics"
      subtitle="Cognitive Dissonance Score (FINN)"
      lineage={['fhq_finn.cds_metrics']}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-3xl font-bold text-white">
              {(cds.cdsScore * 100).toFixed(0)}%
            </span>
            <span className={cn(
              'ml-2 text-sm font-medium',
              cds.cdsTier === 'low' ? 'text-trust-green' :
              cds.cdsTier === 'medium' ? 'text-trust-yellow' : 'text-trust-red'
            )}>
              {cds.cdsTier.toUpperCase()}
            </span>
          </div>
          <StatusBadge status={cds.cdsTier} size="md" />
        </div>

        <p className="text-sm text-gray-300">{cds.narrativeSummary}</p>

        {conflicts.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs text-gray-500 font-medium">Top Conflicts:</p>
            {conflicts.slice(0, 3).map((conflict: any, i: number) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span className="text-gray-300">{conflict.topic}</span>
                <span className="text-gray-500">{(conflict.severity * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}

async function HighRelevanceEvents() {
  const events = await getHighRelevanceEvents(0.5, 5);

  return (
    <Card
      title="High Relevance Events"
      subtitle="Top events by relevance score"
      lineage={['fhq_finn.serper_events']}
    >
      {events.length === 0 ? (
        <p className="text-gray-400">No high-relevance events</p>
      ) : (
        <div className="space-y-3">
          {events.map((event) => (
            <div key={event.eventId} className="border-b border-fjord-700 pb-3 last:border-0 last:pb-0">
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-medium text-white">{event.title}</h4>
                <span className="text-xs text-trust-blue whitespace-nowrap">
                  {event.relevanceScore ? `${(event.relevanceScore * 100).toFixed(0)}%` : '-'}
                </span>
              </div>
              {event.description && (
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">{event.description}</p>
              )}
              <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                {event.source && <span>{event.source}</span>}
                {event.publishedAt && (
                  <span>{formatRelativeTime(event.publishedAt)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

async function EconomicSafetySummary() {
  const systemHealth = await getSystemHealth();
  const { economic } = systemHealth;

  return (
    <Card
      title="Economic Safety"
      subtitle="ADR-012 Cost & Budget Controls"
      lineage={['fhq_governance.economic_safety']}
    >
      <div className="space-y-3">
        {economic.all.map((metric) => (
          <div key={metric.metricName} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">{metric.metricName.replace(/_/g, ' ')}</span>
              <StatusBadge status={metric.status} size="sm" />
            </div>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-fjord-700 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full',
                    metric.status === 'SAFE' ? 'bg-trust-green' :
                    metric.status === 'WARNING' ? 'bg-trust-yellow' : 'bg-trust-red'
                  )}
                  style={{
                    width: metric.ceiling
                      ? `${Math.min((metric.currentValue / metric.ceiling) * 100, 100)}%`
                      : '0%'
                  }}
                />
              </div>
              <span className="text-xs text-gray-400 w-20 text-right">
                {metric.currentValue.toFixed(2)} / {metric.ceiling?.toFixed(2) || '?'} {metric.unit}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

async function IoSModulesStatus() {
  const modules = await getIosModules();

  return (
    <Card
      title="IoS Modules"
      subtitle="Application Layer Status (ADR-005)"
      lineage={['fhq_meta.ios_module_registry']}
    >
      <div className="space-y-3">
        {modules.map((module) => (
          <div key={module.moduleId} className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm text-trust-blue">{module.moduleId}</span>
              <span className="text-sm text-white">{module.moduleName}</span>
            </div>
            <StatusBadge status={module.status} size="sm" />
          </div>
        ))}
      </div>
    </Card>
  );
}

async function RecentActivity() {
  const logs = await getRecentAuditLogs(5);

  return (
    <Card
      title="Recent Activity"
      subtitle="Audit log (ADR-002)"
      lineage={['fhq_meta.audit_log']}
    >
      {logs.length === 0 ? (
        <p className="text-gray-400">No recent activity</p>
      ) : (
        <div className="space-y-3">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-3">
              <StatusBadge status={log.eventCategory} size="sm" variant="status" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{log.changeDescription}</p>
                <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                  <span>{log.changedBy}</span>
                  <span>|</span>
                  <span>{formatRelativeTime(log.changedAt || new Date())}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function OverviewPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Overview</h1>
        <p className="text-gray-400 mt-1">
          Vision-IoS Dashboard - The only authorized human interface to FjordHQ
        </p>
      </div>

      {/* Key Metrics */}
      <Suspense fallback={
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => <SkeletonMetricCard key={i} />)}
        </div>
      }>
        <OverviewMetrics />
      </Suspense>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {/* Column 1 */}
        <div className="space-y-6">
          <Suspense fallback={<SkeletonCard />}>
            <GatesSummary />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <DataFreshnessSummary />
          </Suspense>
        </div>

        {/* Column 2 */}
        <div className="space-y-6">
          <Suspense fallback={<SkeletonCard />}>
            <CdsSummary />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <EconomicSafetySummary />
          </Suspense>
        </div>

        {/* Column 3 */}
        <div className="space-y-6">
          <Suspense fallback={<SkeletonCard />}>
            <HighRelevanceEvents />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <IoSModulesStatus />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <RecentActivity />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
