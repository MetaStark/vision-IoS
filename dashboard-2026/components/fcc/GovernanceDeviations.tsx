/**
 * FCC Governance Deviations Component
 * Glass Wall Observability Layer - Deviation & Violation View
 *
 * Authority: CEO Directive 2026
 * Compliance: ADR-001, ADR-011, ADR-018
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import type { GovernanceDeviation } from '@/lib/fcc/types'
import { AlertTriangle, ShieldAlert, AlertCircle, CheckCircle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface GovernanceDeviationsProps {
  deviations: GovernanceDeviation[]
}

export function GovernanceDeviations({ deviations }: GovernanceDeviationsProps) {
  const critical = deviations.filter(d => d.severity === 'CRITICAL' && !d.resolved)
  const high = deviations.filter(d => d.severity === 'HIGH' && !d.resolved)
  const medium = deviations.filter(d => d.severity === 'MEDIUM' && !d.resolved)
  const resolved = deviations.filter(d => d.resolved)

  const hasActiveDeviations = critical.length > 0 || high.length > 0 || medium.length > 0

  return (
    <div className="space-y-6">
      {/* Status Banner */}
      {hasActiveDeviations ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-6 h-6 text-red-600" />
            <div>
              <p className="font-semibold text-red-800">
                {critical.length + high.length + medium.length} Active Governance Deviations
              </p>
              <p className="text-sm text-red-600">
                {critical.length} Critical | {high.length} High | {medium.length} Medium
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-6 h-6 text-green-600" />
            <div>
              <p className="font-semibold text-green-800">No Active Governance Deviations</p>
              <p className="text-sm text-green-600">All systems operating within governance bounds</p>
            </div>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SeverityCard severity="CRITICAL" count={critical.length} />
        <SeverityCard severity="HIGH" count={high.length} />
        <SeverityCard severity="MEDIUM" count={medium.length} />
        <SeverityCard severity="RESOLVED" count={resolved.length} />
      </div>

      {/* Deviation List */}
      {deviations.length > 0 ? (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Deviation Log (Last 24h)</CardTitle>
              <span className="text-xs text-slate-500">
                Source: fhq_governance.asrp_violations, constitutional_violations
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {deviations.map((deviation) => (
                <DeviationCard key={deviation.id} deviation={deviation} />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <p className="text-slate-600">No governance deviations detected in the last 24 hours</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function DeviationCard({ deviation }: { deviation: GovernanceDeviation }) {
  const severityStyles: Record<string, { bg: string; border: string; text: string; icon: string }> = {
    CRITICAL: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-800', icon: 'text-red-600' },
    HIGH: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-800', icon: 'text-orange-600' },
    MEDIUM: { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-800', icon: 'text-yellow-600' },
    LOW: { bg: 'bg-blue-50', border: 'border-blue-200', text: 'text-blue-800', icon: 'text-blue-600' },
  }

  const style = severityStyles[deviation.severity] || severityStyles.LOW

  return (
    <div className={`${style.bg} ${style.border} border rounded-lg p-4 ${deviation.resolved ? 'opacity-60' : ''}`}>
      <div className="flex items-start gap-3">
        <AlertTriangle className={`w-5 h-5 ${style.icon} flex-shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`font-semibold ${style.text}`}>{deviation.type.replace(/_/g, ' ')}</span>
            <SeverityBadge severity={deviation.severity} />
            {deviation.resolved && (
              <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full">
                Resolved
              </span>
            )}
          </div>
          <p className="text-sm text-slate-700 mb-2">{deviation.description}</p>
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span>Entity: <code className="bg-slate-100 px-1 rounded">{deviation.affected_entity}</code></span>
            <span>{formatDistanceToNow(new Date(deviation.detected_at), { addSuffix: true })}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    CRITICAL: 'bg-red-600 text-white',
    HIGH: 'bg-orange-500 text-white',
    MEDIUM: 'bg-yellow-500 text-white',
    LOW: 'bg-blue-500 text-white',
  }

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold ${styles[severity] || 'bg-slate-500 text-white'}`}>
      {severity}
    </span>
  )
}

function SeverityCard({ severity, count }: { severity: string; count: number }) {
  const config: Record<string, { bg: string; icon: React.ReactNode; label: string }> = {
    CRITICAL: {
      bg: 'bg-red-50 border-red-200',
      icon: <ShieldAlert className="w-5 h-5 text-red-600" />,
      label: 'Critical',
    },
    HIGH: {
      bg: 'bg-orange-50 border-orange-200',
      icon: <AlertTriangle className="w-5 h-5 text-orange-600" />,
      label: 'High',
    },
    MEDIUM: {
      bg: 'bg-yellow-50 border-yellow-200',
      icon: <AlertCircle className="w-5 h-5 text-yellow-600" />,
      label: 'Medium',
    },
    RESOLVED: {
      bg: 'bg-green-50 border-green-200',
      icon: <CheckCircle className="w-5 h-5 text-green-600" />,
      label: 'Resolved',
    },
  }

  const { bg, icon, label } = config[severity] || config.RESOLVED

  return (
    <div className={`${bg} border rounded-lg p-4`}>
      <div className="flex items-center gap-3">
        <div className="p-2 bg-white rounded-lg">{icon}</div>
        <div>
          <p className="text-2xl font-bold">{count}</p>
          <p className="text-xs text-slate-500">{label}</p>
        </div>
      </div>
    </div>
  )
}
