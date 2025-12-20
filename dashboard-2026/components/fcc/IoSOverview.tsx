/**
 * FCC IoS Overview Component
 * Glass Wall Observability Layer - IoS Module Registry View
 *
 * Authority: CEO Directive 2026
 * Compliance: ADR-001, ADR-013, ADR-019
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import type { IoSRecord, IoSSummary } from '@/lib/fcc/types'
import { Cpu, Zap, Lock, Layers } from 'lucide-react'

interface IoSOverviewProps {
  modules: IoSRecord[]
  summary: IoSSummary
}

export function IoSOverview({ modules, summary }: IoSOverviewProps) {
  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Total Modules"
          value={summary.total}
          icon={<Layers className="w-5 h-5" />}
        />
        <SummaryCard
          label="Active"
          value={summary.active}
          icon={<Zap className="w-5 h-5 text-green-500" />}
        />
        <SummaryCard
          label="Canonical"
          value={summary.canonical}
          icon={<Lock className="w-5 h-5 text-blue-500" />}
        />
        <SummaryCard
          label="G4 Constitutional"
          value={summary.g4_constitutional}
          icon={<Cpu className="w-5 h-5 text-purple-500" />}
        />
      </div>

      {/* IoS Module Cards */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>IoS Module Registry</CardTitle>
            <span className="text-xs text-slate-500">
              Source: fhq_meta.ios_registry
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {modules.map((mod) => (
              <ModuleCard key={mod.ios_id} module={mod} />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Distribution Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Owner Role</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(summary.by_owner)
                .sort(([, a], [, b]) => b - a)
                .map(([owner, count]) => (
                  <div key={owner} className="flex items-center justify-between">
                    <span className="text-sm text-slate-600 font-medium">{owner}</span>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2 rounded"
                        style={{
                          width: `${(count / summary.total) * 120}px`,
                          backgroundColor: getOwnerColor(owner),
                        }}
                      />
                      <span className="text-sm font-mono">{count}</span>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Governance Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(summary.by_status)
                .sort(([, a], [, b]) => b - a)
                .map(([status, count]) => (
                  <div key={status} className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">{formatStatus(status)}</span>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2 rounded"
                        style={{
                          width: `${(count / summary.total) * 120}px`,
                          backgroundColor: getStatusColor(status),
                        }}
                      />
                      <span className="text-sm font-mono">{count}</span>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function ModuleCard({ module }: { module: IoSRecord }) {
  const isActive = module.status === 'ACTIVE' || module.status?.includes('G4')
  const isCanonical = module.canonical

  return (
    <div
      className={`
        border rounded-lg p-4 transition-all
        ${isActive ? 'border-green-200 bg-green-50/30' : 'border-slate-200 bg-white'}
        ${isCanonical ? 'ring-1 ring-blue-200' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold text-slate-700">
            {module.ios_id}
          </span>
          {isCanonical && (
            <span title="Canonical">
              <Lock className="w-3 h-3 text-blue-500" />
            </span>
          )}
        </div>
        <StatusIndicator status={module.status} />
      </div>

      {/* Title */}
      <h4 className="text-sm font-medium text-slate-900 mb-1 line-clamp-2">
        {module.title}
      </h4>

      {/* Description */}
      <p className="text-xs text-slate-500 line-clamp-2 mb-3">
        {module.description}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between text-xs">
        <span
          className="px-2 py-0.5 rounded-full font-medium"
          style={{
            backgroundColor: getOwnerColor(module.owner_role) + '20',
            color: getOwnerColor(module.owner_role),
          }}
        >
          {module.owner_role}
        </span>
        <span className="text-slate-400 font-mono">{module.version}</span>
      </div>

      {/* Governance State */}
      {module.governance_state && (
        <div className="mt-2 pt-2 border-t border-slate-100">
          <span className="text-xs text-slate-500">
            Gate: <span className="font-medium">{module.governance_state}</span>
          </span>
        </div>
      )}
    </div>
  )
}

function StatusIndicator({ status }: { status: string }) {
  const isActive = status === 'ACTIVE' || status?.includes('G4')
  const isDeprecated = status === 'DEPRECATED'
  const isDraft = status === 'DRAFT'

  if (isDeprecated) {
    return (
      <span className="flex items-center gap-1 text-xs text-red-600">
        <span className="w-2 h-2 rounded-full bg-red-500" />
        Deprecated
      </span>
    )
  }

  if (isDraft) {
    return (
      <span className="flex items-center gap-1 text-xs text-amber-600">
        <span className="w-2 h-2 rounded-full bg-amber-500" />
        Draft
      </span>
    )
  }

  if (isActive) {
    return (
      <span className="flex items-center gap-1 text-xs text-green-600">
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        Active
      </span>
    )
  }

  return (
    <span className="flex items-center gap-1 text-xs text-slate-500">
      <span className="w-2 h-2 rounded-full bg-slate-400" />
      {status}
    </span>
  )
}

function SummaryCard({
  label,
  value,
  icon,
}: {
  label: string
  value: number
  icon: React.ReactNode
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-slate-100 rounded-lg">{icon}</div>
        <div>
          <p className="text-2xl font-semibold">{value}</p>
          <p className="text-xs text-slate-500">{label}</p>
        </div>
      </div>
    </div>
  )
}

function getOwnerColor(owner: string): string {
  const colors: Record<string, string> = {
    LARS: '#3B82F6',   // Blue
    STIG: '#10B981',   // Green
    FINN: '#8B5CF6',   // Purple
    VEGA: '#F59E0B',   // Amber
    LINE: '#EC4899',   // Pink
    CDMO: '#06B6D4',   // Cyan
    CEO: '#EF4444',    // Red
  }
  return colors[owner] || '#6B7280'
}

function getStatusColor(status: string): string {
  if (status.includes('G4') || status === 'ACTIVE') return '#10B981'
  if (status.includes('G3')) return '#3B82F6'
  if (status.includes('G2')) return '#8B5CF6'
  if (status.includes('G1') || status.includes('G0')) return '#F59E0B'
  if (status === 'DEPRECATED') return '#EF4444'
  if (status === 'DRAFT') return '#6B7280'
  return '#94A3B8'
}

function formatStatus(status: string): string {
  return status.replace(/_/g, ' ')
}
