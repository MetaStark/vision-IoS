/**
 * Research Workspace Page - IoS-006
 * Agent Chat Interface for CEO interaction
 *
 * ADR-005 Section 7 - Agent Chat Workspace Constraints:
 * - Every message bound to target agent
 * - Logged with CEO identity, agent, timestamp, task type
 * - Routed via Orchestrator (not direct LLM)
 * - Subject to VEGA economic safety (ADR-012)
 */

import { AgentChat } from '@/components/AgentChat';
import { Card } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { getRecentAuditLogs, getEconomicSafety } from '@/lib/data';
import { formatRelativeTime, cn } from '@/lib/utils';
import { Suspense } from 'react';
import { SkeletonCard } from '@/components/ui/Skeleton';

export const dynamic = 'force-dynamic';

async function RecentChatActivity() {
  const logs = await getRecentAuditLogs(10);
  const chatLogs = logs.filter(l => l.eventType === 'CHAT_MESSAGE');

  return (
    <Card
      title="Recent Chat Activity"
      subtitle="ADR-002 Audit Trail"
      lineage={['fhq_meta.audit_log', 'agent_chat_history']}
    >
      {chatLogs.length === 0 ? (
        <p className="text-gray-400 text-sm">No chat activity yet. Start a conversation with an agent.</p>
      ) : (
        <div className="space-y-2 max-h-[200px] overflow-y-auto">
          {chatLogs.map((log) => (
            <div key={log.id} className="flex items-start gap-2 text-sm">
              <StatusBadge status={log.eventCategory} size="sm" />
              <div className="flex-1">
                <p className="text-gray-300 truncate">{log.changeDescription}</p>
                <p className="text-xs text-gray-500">{formatRelativeTime(log.changedAt || new Date())}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

async function EconomicSafetyStatus() {
  const metrics = await getEconomicSafety();
  const llmCost = metrics.find(m => m.metricName === 'daily_llm_cost');

  return (
    <Card
      title="Economic Safety"
      subtitle="ADR-012 Chat Cost Tracking"
      lineage={['fhq_governance.economic_safety']}
    >
      {llmCost && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">Daily LLM Cost</span>
            <StatusBadge status={llmCost.status} size="sm" />
          </div>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-3 bg-fjord-700 rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  llmCost.status === 'SAFE' ? 'bg-trust-green' : 'bg-trust-yellow'
                )}
                style={{
                  width: llmCost.ceiling
                    ? `${Math.min((llmCost.currentValue / llmCost.ceiling) * 100, 100)}%`
                    : '0%'
                }}
              />
            </div>
            <span className="text-sm text-white font-mono">
              ${llmCost.currentValue.toFixed(2)} / ${llmCost.ceiling?.toFixed(2)}
            </span>
          </div>
          <p className="text-xs text-gray-500">
            Chat messages contribute to daily LLM cost ceiling
          </p>
        </div>
      )}
    </Card>
  );
}

function AgentCapabilities() {
  const agents = [
    { id: 'LARS', focus: 'Strategy & Scenarios', actions: ['Capital calibration', 'Risk assessment'] },
    { id: 'FINN', focus: 'Intelligence & CDS', actions: ['Market research', 'Narrative analysis'] },
    { id: 'STIG', focus: 'Technical Validation', actions: ['Schema review', 'Gate checks'] },
    { id: 'LINE', focus: 'Data & Pipelines', actions: ['Ingestion status', 'Freshness monitoring'] },
    { id: 'VEGA', focus: 'Governance', actions: ['ADR compliance', 'Risk classification'] },
  ];

  return (
    <Card
      title="Agent Capabilities"
      subtitle="Available agents and their focus areas"
    >
      <div className="space-y-3">
        {agents.map((agent) => (
          <div key={agent.id} className="flex items-center gap-3">
            <StatusBadge status={agent.id} size="md" variant="agent" />
            <div className="flex-1">
              <p className="text-sm text-white">{agent.focus}</p>
              <p className="text-xs text-gray-500">{agent.actions.join(', ')}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function ResearchWorkspacePage() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Research Workspace</h1>
        <p className="text-gray-400 mt-1">
          IoS-006 - Chat with agents (LARS, FINN, STIG, LINE, VEGA)
        </p>
      </div>

      {/* ADR-005 Notice */}
      <div className="bg-agent-vega/10 border border-agent-vega/20 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <StatusBadge status="VEGA" size="md" variant="agent" />
          <div>
            <h4 className="font-medium text-white">ADR-005 Chat Governance</h4>
            <p className="text-sm text-gray-400 mt-1">
              All messages are logged with CEO identity, routed via Orchestrator, and subject to VEGA economic safety constraints.
              Agent proposals affecting governance, capital, or cost ceilings are treated as recommendations requiring G4 approval.
            </p>
          </div>
        </div>
      </div>

      {/* Main Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
        {/* Chat Interface - Takes 3 columns */}
        <div className="xl:col-span-3">
          <AgentChat initialAgent="LARS" />
        </div>

        {/* Sidebar - Takes 1 column */}
        <div className="space-y-6">
          <AgentCapabilities />
          <Suspense fallback={<SkeletonCard />}>
            <EconomicSafetyStatus />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <RecentChatActivity />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
