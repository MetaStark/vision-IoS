/**
 * FINN Intelligence Page - Vision-IoS Dashboard
 * CDS metrics, briefings, events (IoS-003)
 *
 * Data Lineage:
 * - fhq_finn.cds_metrics
 * - fhq_finn.daily_briefings
 * - fhq_finn.serper_events
 */

import { Card } from '@/components/ui/Card';
import { MetricCard } from '@/components/ui/MetricCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { SkeletonCard } from '@/components/ui/Skeleton';
import { getLatestCds, getLatestBriefing, getSerperEvents, getHighRelevanceEvents } from '@/lib/data';
import { formatRelativeTime, cn } from '@/lib/utils';
import { Suspense } from 'react';

export const dynamic = 'force-dynamic';

async function CdsMetricsPanel() {
  const cds = await getLatestCds();

  if (!cds) {
    return (
      <Card title="CDS Metrics">
        <p className="text-gray-400">No CDS data available</p>
      </Card>
    );
  }

  const conflicts = cds.topConflicts ? JSON.parse(cds.topConflicts) : [];

  return (
    <Card
      title="Cognitive Dissonance Score"
      subtitle="FINN Intelligence Analysis"
      lineage={['fhq_finn.cds_metrics']}
    >
      <div className="space-y-6">
        {/* CDS Gauge */}
        <div className="flex items-center gap-8">
          <div className="relative w-32 h-32">
            <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
              {/* Background circle */}
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="#374151"
                strokeWidth="8"
              />
              {/* Score arc */}
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke={cds.cdsTier === 'low' ? '#10b981' : cds.cdsTier === 'medium' ? '#f59e0b' : '#ef4444'}
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${cds.cdsScore * 251.2} 251.2`}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold text-white">
                {(cds.cdsScore * 100).toFixed(0)}
              </span>
              <span className="text-xs text-gray-400">CDS</span>
            </div>
          </div>

          <div className="flex-1 space-y-4">
            <div>
              <span className="text-sm text-gray-400">Risk Tier</span>
              <div className="flex items-center gap-2 mt-1">
                <StatusBadge status={cds.cdsTier} size="lg" />
                <span className="text-gray-300">
                  {cds.cdsTier === 'low' ? 'Low market conflict' :
                   cds.cdsTier === 'medium' ? 'Moderate narrative tension' :
                   'High cognitive dissonance detected'}
                </span>
              </div>
            </div>
            <div>
              <span className="text-sm text-gray-400">Conflicts Detected</span>
              <p className="text-2xl font-semibold text-white mt-1">{cds.conflictCount || 0}</p>
            </div>
          </div>
        </div>

        {/* Narrative Summary */}
        <div className="bg-fjord-700/50 rounded-lg p-4">
          <h4 className="text-sm font-medium text-gray-400 mb-2">Narrative Summary</h4>
          <p className="text-white">{cds.narrativeSummary}</p>
        </div>

        {/* Top Conflicts */}
        {conflicts.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-3">Top Conflicts</h4>
            <div className="space-y-2">
              {conflicts.map((conflict: any, i: number) => (
                <div key={i} className="flex items-center justify-between bg-fjord-700/30 rounded-lg p-3">
                  <span className="text-white">{conflict.topic}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-24 h-2 bg-fjord-600 rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full',
                          conflict.severity > 0.7 ? 'bg-trust-red' :
                          conflict.severity > 0.5 ? 'bg-trust-yellow' : 'bg-trust-green'
                        )}
                        style={{ width: `${conflict.severity * 100}%` }}
                      />
                    </div>
                    <span className="text-sm text-gray-400 w-12 text-right">
                      {(conflict.severity * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="text-xs text-gray-500 flex items-center gap-2">
          <StatusBadge status="FINN" size="sm" variant="agent" />
          <span>Calculated {formatRelativeTime(cds.calculatedAt || new Date())}</span>
        </div>
      </div>
    </Card>
  );
}

async function DailyBriefingPanel() {
  const briefing = await getLatestBriefing();

  if (!briefing) {
    return (
      <Card title="Daily Briefing">
        <p className="text-gray-400">No briefing available</p>
      </Card>
    );
  }

  const keyEvents = briefing.keyEvents ? JSON.parse(briefing.keyEvents) : [];

  return (
    <Card
      title="Daily Briefing"
      subtitle={`${briefing.briefingDate}`}
      lineage={['fhq_finn.daily_briefings']}
    >
      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Market Summary</h4>
          <p className="text-white">{briefing.marketSummary}</p>
        </div>

        {keyEvents.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Key Events</h4>
            <ul className="space-y-2">
              {keyEvents.map((event: string, i: number) => (
                <li key={i} className="flex items-start gap-2 text-gray-300">
                  <span className="text-trust-blue">-</span>
                  <span>{event}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {briefing.riskAssessment && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Risk Assessment</h4>
            <p className="text-gray-300">{briefing.riskAssessment}</p>
          </div>
        )}

        {briefing.recommendations && (
          <div>
            <h4 className="text-sm font-medium text-gray-400 mb-2">Recommendations</h4>
            <p className="text-gray-300">{briefing.recommendations}</p>
          </div>
        )}

        <div className="text-xs text-gray-500 flex items-center gap-2 pt-2 border-t border-fjord-700">
          <StatusBadge status="FINN" size="sm" variant="agent" />
          <span>Generated {formatRelativeTime(briefing.generatedAt || new Date())}</span>
        </div>
      </div>
    </Card>
  );
}

async function EventsFeed() {
  const events = await getSerperEvents(15);

  return (
    <Card
      title="Events Feed"
      subtitle="Latest news and events"
      lineage={['fhq_finn.serper_events']}
    >
      {events.length === 0 ? (
        <p className="text-gray-400">No events available</p>
      ) : (
        <div className="space-y-4 max-h-[600px] overflow-y-auto">
          {events.map((event) => (
            <div
              key={event.eventId}
              className="border-b border-fjord-700 pb-4 last:border-0 last:pb-0"
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="text-sm font-medium text-white">{event.title}</h4>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {event.relevanceScore && (
                    <span className={cn(
                      'text-xs font-medium px-2 py-0.5 rounded',
                      event.relevanceScore > 0.7 ? 'bg-trust-blue/20 text-trust-blue' :
                      event.relevanceScore > 0.5 ? 'bg-trust-yellow/20 text-trust-yellow' :
                      'bg-gray-700 text-gray-400'
                    )}>
                      {(event.relevanceScore * 100).toFixed(0)}%
                    </span>
                  )}
                  {event.sentimentScore !== null && (
                    <span className={cn(
                      'text-xs',
                      event.sentimentScore > 0 ? 'text-trust-green' :
                      event.sentimentScore < 0 ? 'text-trust-red' : 'text-gray-400'
                    )}>
                      {event.sentimentScore > 0 ? '+' : ''}{event.sentimentScore?.toFixed(2)}
                    </span>
                  )}
                </div>
              </div>
              {event.description && (
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">{event.description}</p>
              )}
              <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                <span className="uppercase">{event.eventType}</span>
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

async function HighRelevancePanel() {
  const events = await getHighRelevanceEvents(0.7, 5);

  return (
    <Card
      title="High Relevance Alerts"
      subtitle="Events with relevance > 70%"
      lineage={['fhq_finn.serper_events']}
    >
      {events.length === 0 ? (
        <p className="text-gray-400">No high-relevance events</p>
      ) : (
        <div className="space-y-3">
          {events.map((event) => (
            <div
              key={event.eventId}
              className="bg-trust-blue/10 border border-trust-blue/20 rounded-lg p-3"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-trust-blue text-sm font-medium">
                  {(event.relevanceScore! * 100).toFixed(0)}% Relevance
                </span>
                <span className="text-xs text-gray-500">
                  {event.publishedAt && formatRelativeTime(event.publishedAt)}
                </span>
              </div>
              <h4 className="text-white font-medium">{event.title}</h4>
              {event.description && (
                <p className="text-xs text-gray-400 mt-1">{event.description}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function FinnIntelligencePage() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">FINN Intelligence</h1>
        <p className="text-gray-400 mt-1">
          IoS-003 - CDS metrics, daily briefings, and event analysis
        </p>
      </div>

      {/* CDS and Briefing */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Suspense fallback={<SkeletonCard />}>
          <CdsMetricsPanel />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <DailyBriefingPanel />
        </Suspense>
      </div>

      {/* Events */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Suspense fallback={<SkeletonCard />}>
            <EventsFeed />
          </Suspense>
        </div>
        <Suspense fallback={<SkeletonCard />}>
          <HighRelevancePanel />
        </Suspense>
      </div>
    </div>
  );
}
