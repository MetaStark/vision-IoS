/**
 * System Health Page - Vision-IoS Dashboard
 * Gates, governance, ADRs, economic safety
 *
 * Data Lineage:
 * - fhq_validation.gate_status
 * - fhq_governance.governance_state
 * - fhq_governance.economic_safety
 * - fhq_meta.adr_registry
 * - fhq_meta.audit_log
 */

import { Card } from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { SkeletonCard } from '@/components/ui/Skeleton';
import {
  getSystemHealth,
  getAdrRegistry,
  getGovernanceState,
  getEconomicSafety,
  getRecentAuditLogs,
  getAgents,
} from '@/lib/data';
import { formatRelativeTime, cn } from '@/lib/utils';
import { Suspense } from 'react';

export const dynamic = 'force-dynamic';

async function GatesPanel() {
  const systemHealth = await getSystemHealth();
  const { gates } = systemHealth;

  const gateDescriptions: Record<string, string> = {
    G0: 'Syntax & Format Validation',
    G1: 'STIG Technical Validation',
    G2: 'LARS + VEGA Governance Validation',
    G3: 'VEGA Audit Verification',
    G4: 'CEO Final Approval',
  };

  return (
    <Card
      title="ADR-004 Change Gates"
      subtitle="Governance gate status"
      lineage={['fhq_validation.gate_status']}
    >
      <div className="space-y-4">
        {gates.all.map((gate, index) => (
          <div key={gate.gateId} className="relative">
            <div className="flex items-center gap-4">
              {/* Gate number with connector */}
              <div className="relative">
                <div className={cn(
                  'w-10 h-10 rounded-full flex items-center justify-center font-mono font-bold text-sm',
                  gate.status === 'PASS' ? 'bg-trust-green/20 text-trust-green border border-trust-green/40' :
                  gate.status === 'FAIL' ? 'bg-trust-red/20 text-trust-red border border-trust-red/40' :
                  gate.status === 'PENDING' ? 'bg-trust-yellow/20 text-trust-yellow border border-trust-yellow/40' :
                  'bg-fjord-600 text-gray-400 border border-fjord-500'
                )}>
                  {gate.gateId}
                </div>
                {index < gates.all.length - 1 && (
                  <div className={cn(
                    'absolute top-10 left-1/2 w-0.5 h-6 -translate-x-1/2',
                    gate.status === 'PASS' ? 'bg-trust-green/40' : 'bg-fjord-600'
                  )} />
                )}
              </div>

              {/* Gate info */}
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium text-white">{gate.gateName}</h4>
                    <p className="text-xs text-gray-400">{gateDescriptions[gate.gateId] || gate.gateName}</p>
                  </div>
                  <StatusBadge status={gate.status} size="md" />
                </div>
                {gate.failureReason && (
                  <p className="text-xs text-trust-red mt-1">{gate.failureReason}</p>
                )}
                {gate.checkedBy && (
                  <p className="text-xs text-gray-500 mt-1">
                    Checked by {gate.checkedBy} {gate.lastCheckedAt && `- ${formatRelativeTime(gate.lastCheckedAt)}`}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

async function GovernanceStatePanel() {
  const state = await getGovernanceState();

  if (!state) {
    return (
      <Card title="Governance State">
        <p className="text-gray-400">No governance state available</p>
      </Card>
    );
  }

  return (
    <Card
      title="Governance State"
      subtitle="Current system phase"
      lineage={['fhq_governance.governance_state']}
    >
      <div className="space-y-4">
        <div className="bg-fjord-700/30 rounded-lg p-4">
          <span className="text-xs text-gray-400">Current Phase</span>
          <p className="text-xl font-bold text-white mt-1">{state.currentPhase}</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-xs text-gray-400">Production Mode</span>
            <div className="mt-1">
              <StatusBadge status={state.productionMode ? 'ACTIVE' : 'INACTIVE'} size="md" />
            </div>
          </div>
          <div>
            <span className="text-xs text-gray-400">Architecture Freeze</span>
            <div className="mt-1">
              <StatusBadge status={state.architectureFreeze ? 'FROZEN' : 'UNLOCKED'} size="md" />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <span className="text-xs text-gray-400">Baseline Version</span>
            <p className="font-mono text-white">{state.baselineVersion || '-'}</p>
          </div>
          <div>
            <span className="text-xs text-gray-400">Baseline Commit</span>
            <p className="font-mono text-white">{state.baselineCommit || '-'}</p>
          </div>
        </div>

        {state.approvedBy && (
          <div className="text-xs text-gray-500 pt-2 border-t border-fjord-700">
            Approved by {state.approvedBy} {state.approvedAt && `on ${new Date(state.approvedAt).toLocaleDateString()}`}
          </div>
        )}
      </div>
    </Card>
  );
}

async function EconomicSafetyPanel() {
  const metrics = await getEconomicSafety();

  return (
    <Card
      title="Economic Safety (ADR-012)"
      subtitle="Cost ceilings and budget controls"
      lineage={['fhq_governance.economic_safety']}
    >
      <div className="space-y-4">
        {metrics.map((metric) => {
          const usage = metric.ceiling ? (metric.currentValue / metric.ceiling) * 100 : 0;

          return (
            <div key={metric.metricName} className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">
                  {metric.metricName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </span>
                <StatusBadge status={metric.status} size="sm" />
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1 h-3 bg-fjord-700 rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all',
                      usage > 90 ? 'bg-trust-red' :
                      usage > 70 ? 'bg-trust-yellow' : 'bg-trust-green'
                    )}
                    style={{ width: `${Math.min(usage, 100)}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400 w-24 text-right font-mono">
                  {metric.currentValue.toFixed(2)} / {metric.ceiling?.toFixed(2) || '?'}
                </span>
              </div>
              <p className="text-xs text-gray-500">
                {metric.unit} - Updated by {metric.updatedBy}
              </p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

async function AdrRegistryPanel() {
  const adrs = await getAdrRegistry();

  return (
    <Card
      title="ADR Registry"
      subtitle="Constitutional and operational ADRs"
      lineage={['fhq_meta.adr_registry']}
    >
      <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-fjord-800">
            <tr>
              <th>ADR</th>
              <th>Title</th>
              <th>Tier</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {adrs.map((adr) => (
              <tr key={adr.adrNumber}>
                <td className="font-mono text-trust-blue">{adr.adrNumber}</td>
                <td>
                  <span className="text-white">{adr.title}</span>
                  {adr.author && (
                    <span className="text-xs text-gray-500 ml-2">by {adr.author}</span>
                  )}
                </td>
                <td>
                  <span className={cn(
                    'text-xs px-2 py-0.5 rounded',
                    adr.tier === 'Constitutional' ? 'bg-agent-vega/20 text-agent-vega' :
                    adr.tier === 'Operational' ? 'bg-agent-stig/20 text-agent-stig' :
                    'bg-gray-700 text-gray-400'
                  )}>
                    {adr.tier}
                  </span>
                </td>
                <td>
                  <StatusBadge status={adr.status} size="sm" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

async function AgentsPanel() {
  const agents = await getAgents();

  const agentDescriptions: Record<string, string> = {
    LARS: 'Logic, Analytics & Research Strategy',
    STIG: 'Schema, Technical & Infrastructure Guardian',
    LINE: 'Lineage & Ingestion Engine',
    FINN: 'Financial Intelligence & Narrative Navigator',
    VEGA: 'Governance Engine',
  };

  return (
    <Card
      title="Agent Registry"
      subtitle="ADR-008 Agent Keys"
      lineage={['fhq_meta.agent_keys']}
    >
      <div className="space-y-3">
        {agents.map((agent) => (
          <div key={agent.agentId} className="flex items-center justify-between bg-fjord-700/30 rounded-lg p-3">
            <div className="flex items-center gap-3">
              <StatusBadge status={agent.agentId} size="md" variant="agent" />
              <div>
                <span className="text-white font-medium">{agent.agentName}</span>
                <p className="text-xs text-gray-500">{agentDescriptions[agent.agentId]}</p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs text-gray-400">{agent.keyType}</span>
              <p className="font-mono text-xs text-gray-500 truncate max-w-[120px]">
                {agent.publicKey}
              </p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

async function AuditLogPanel() {
  const logs = await getRecentAuditLogs(10);

  return (
    <Card
      title="Audit Log"
      subtitle="ADR-002 Compliance"
      lineage={['fhq_meta.audit_log']}
    >
      {logs.length === 0 ? (
        <p className="text-gray-400">No audit logs available</p>
      ) : (
        <div className="space-y-3 max-h-[400px] overflow-y-auto">
          {logs.map((log) => (
            <div key={log.id} className="border-b border-fjord-700 pb-3 last:border-0 last:pb-0">
              <div className="flex items-start gap-3">
                <StatusBadge status={log.eventCategory} size="sm" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white">{log.changeDescription}</p>
                  <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                    <span>{log.eventType}</span>
                    {log.schemaName && (
                      <>
                        <span>|</span>
                        <span className="font-mono">{log.schemaName}.{log.tableName}</span>
                      </>
                    )}
                    <span>|</span>
                    <span>{log.changedBy}</span>
                    <span>|</span>
                    <span>{formatRelativeTime(log.changedAt || new Date())}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function SystemHealthPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">System Health</h1>
        <p className="text-gray-400 mt-1">
          Governance, gates, ADR registry, and economic safety controls
        </p>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {/* Column 1 */}
        <div className="space-y-6">
          <Suspense fallback={<SkeletonCard />}>
            <GatesPanel />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <GovernanceStatePanel />
          </Suspense>
        </div>

        {/* Column 2 */}
        <div className="space-y-6">
          <Suspense fallback={<SkeletonCard />}>
            <EconomicSafetyPanel />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <AgentsPanel />
          </Suspense>
        </div>

        {/* Column 3 */}
        <div className="space-y-6">
          <Suspense fallback={<SkeletonCard />}>
            <AdrRegistryPanel />
          </Suspense>
          <Suspense fallback={<SkeletonCard />}>
            <AuditLogPanel />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
