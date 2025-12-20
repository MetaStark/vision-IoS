/**
 * FCC ADR Overview Component
 * Glass Wall Observability Layer - ADR Registry View
 *
 * Authority: CEO Directive 2026
 * Compliance: ADR-001, ADR-013, ADR-019
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import type { ADRRecord, ADRSummary } from '@/lib/fcc/types'
import { Shield, CheckCircle, FileText, Users } from 'lucide-react'

interface ADROverviewProps {
  adrs: ADRRecord[]
  summary: ADRSummary
}

export function ADROverview({ adrs, summary }: ADROverviewProps) {
  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Total ADRs"
          value={summary.total}
          icon={<FileText className="w-5 h-5" />}
        />
        <SummaryCard
          label="Approved"
          value={summary.approved}
          icon={<CheckCircle className="w-5 h-5 text-green-500" />}
        />
        <SummaryCard
          label="Constitutional"
          value={summary.constitutional}
          icon={<Shield className="w-5 h-5 text-blue-500" />}
        />
        <SummaryCard
          label="VEGA Attested"
          value={summary.vega_attested}
          icon={<Users className="w-5 h-5 text-purple-500" />}
        />
      </div>

      {/* ADR Registry Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>ADR Registry</CardTitle>
            <span className="text-xs text-slate-500">
              Source: fhq_meta.adr_registry
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left py-3 px-2 font-medium text-slate-400">ID</th>
                  <th className="text-left py-3 px-2 font-medium text-slate-400">Title</th>
                  <th className="text-left py-3 px-2 font-medium text-slate-400">Status</th>
                  <th className="text-left py-3 px-2 font-medium text-slate-400">Type</th>
                  <th className="text-left py-3 px-2 font-medium text-slate-400">Tier</th>
                  <th className="text-left py-3 px-2 font-medium text-slate-400">Owner</th>
                  <th className="text-center py-3 px-2 font-medium text-slate-400">VEGA</th>
                </tr>
              </thead>
              <tbody>
                {adrs.map((adr) => (
                  <tr
                    key={adr.adr_id}
                    className="border-b border-slate-700/50 hover:bg-slate-800/50 transition-colors"
                  >
                    <td className="py-3 px-2 font-mono text-xs text-slate-300">{adr.adr_id}</td>
                    <td className="py-3 px-2 max-w-xs truncate text-slate-200" title={adr.adr_title}>
                      {adr.adr_title}
                    </td>
                    <td className="py-3 px-2">
                      <StatusBadge variant={getStatusVariant(adr.adr_status)}>
                        {adr.adr_status}
                      </StatusBadge>
                    </td>
                    <td className="py-3 px-2">
                      <TypeBadge type={adr.adr_type} />
                    </td>
                    <td className="py-3 px-2 text-xs text-slate-300">{adr.governance_tier}</td>
                    <td className="py-3 px-2 text-xs text-slate-300">{adr.owner || '-'}</td>
                    <td className="py-3 px-2 text-center">
                      {adr.vega_attested ? (
                        <span className="text-green-400" title="VEGA Attested">
                          <CheckCircle className="w-4 h-4 inline" />
                        </span>
                      ) : (
                        <span className="text-slate-600">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Tier Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Governance Tier</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(summary.by_tier)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([tier, count]) => (
                  <div key={tier} className="flex items-center justify-between">
                    <span className="text-sm text-slate-300">{tier}</span>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2 bg-blue-500 rounded"
                        style={{ width: `${(count / summary.total) * 100}px` }}
                      />
                      <span className="text-sm font-mono text-slate-200">{count}</span>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">By Owner</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(summary.by_owner)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 8)
                .map(([owner, count]) => (
                  <div key={owner} className="flex items-center justify-between">
                    <span className="text-sm text-slate-300">{owner}</span>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2 bg-purple-500 rounded"
                        style={{ width: `${(count / summary.total) * 100}px` }}
                      />
                      <span className="text-sm font-mono text-slate-200">{count}</span>
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
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-slate-700 rounded-lg">{icon}</div>
        <div>
          <p className="text-2xl font-semibold text-slate-100">{value}</p>
          <p className="text-xs text-slate-400">{label}</p>
        </div>
      </div>
    </div>
  )
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    CONSTITUTIONAL: 'bg-blue-900/50 text-blue-300 border border-blue-700',
    ARCHITECTURAL: 'bg-purple-900/50 text-purple-300 border border-purple-700',
    OPERATIONAL: 'bg-green-900/50 text-green-300 border border-green-700',
    COMPLIANCE: 'bg-amber-900/50 text-amber-300 border border-amber-700',
  }

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[type] || 'bg-slate-800 text-slate-300 border border-slate-600'}`}>
      {type}
    </span>
  )
}

function getStatusVariant(status: string): 'pass' | 'fail' | 'info' | 'warning' {
  switch (status) {
    case 'APPROVED':
      return 'pass'
    case 'DEPRECATED':
    case 'SUPERSEDED':
      return 'fail'
    case 'PROPOSED':
      return 'warning'
    default:
      return 'info'
  }
}
