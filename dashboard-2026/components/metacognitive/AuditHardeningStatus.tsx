/**
 * Metacognitive Observability - Audit-Hardening Status Component
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - G4+ Compliance
 *
 * Displays:
 * - Hash chain integrity status
 * - Court-proof evidence coverage
 * - Boundary violation tracking
 * - DEFCON system state
 * - Overall audit health score
 */

'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  Shield,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Lock,
  FileCheck,
  Link as LinkIcon,
  Activity,
  Info,
  RefreshCw,
  Clock,
} from 'lucide-react'

interface HealthIndicators {
  hash_chain: 'PASS' | 'WARN' | 'FAIL'
  court_proof: 'PASS' | 'WARN' | 'FAIL'
  boundary: 'PASS' | 'WARN' | 'FAIL'
  defcon: 'PASS' | 'WARN' | 'FAIL'
}

interface HashChainMetrics {
  checks_24h: number
  valid: number
  integrity_pct: number
  last_check: string | null
}

interface CourtProofMetrics {
  summaries_7d: number
  with_raw_query: number
  coverage_pct: number
  last_evidence: string | null
}

interface BoundaryMetrics {
  checks_30d: number
  violations: number
  last_validation: string | null
}

interface SystemMetrics {
  defcon: string
  defcon_updated: string | null
}

interface CircuitBreakerEvent {
  event_id: string
  breaker_name: string
  event_type: string
  defcon_before: string
  defcon_after: string
  triggered_at: string
}

interface Verification {
  verification_id: string
  summary_type: string
  verification_result: string
  verified_at: string
}

interface AuditStatusData {
  overall_status: 'ALL_CLEAR' | 'WARNING' | 'CRITICAL' | 'ERROR'
  audit_health_score: number
  health_indicators: HealthIndicators
  metrics: {
    hash_chain: HashChainMetrics
    court_proof: CourtProofMetrics
    boundary: BoundaryMetrics
    system: SystemMetrics
  }
  recent_circuit_breaker_events: CircuitBreakerEvent[]
  recent_verifications: Verification[]
  _meta: {
    source_view: string
    authority: string
    adr_references: string[]
    fetched_at: string
  }
}

export function AuditHardeningStatus() {
  const [data, setData] = useState<AuditStatusData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/metacognitive/audit-status')
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        if (json.error) throw new Error(json.error)
        setData(json)
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000) // 5s polling (critical monitoring)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin" style={{ color: 'hsl(var(--muted-foreground))' }} />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center gap-2 py-4 text-red-400">
            <AlertTriangle className="w-5 h-5" />
            <span>Audit status unavailable: {error}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const indicators = data?.health_indicators
  const metrics = data?.metrics

  // Overall status styling
  const statusStyle = data?.overall_status === 'ALL_CLEAR'
    ? { bg: 'rgba(34, 197, 94, 0.15)', border: '1px solid rgba(34, 197, 94, 0.3)', color: 'rgb(134, 239, 172)' }
    : data?.overall_status === 'WARNING'
    ? { bg: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.3)', color: 'rgb(253, 224, 71)' }
    : { bg: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: 'rgb(252, 165, 165)' }

  // DEFCON styling
  const defconStyle = metrics?.system.defcon === 'GREEN'
    ? { bg: 'rgba(34, 197, 94, 0.2)', color: 'rgb(134, 239, 172)' }
    : metrics?.system.defcon === 'YELLOW'
    ? { bg: 'rgba(245, 158, 11, 0.2)', color: 'rgb(253, 224, 71)' }
    : metrics?.system.defcon === 'ORANGE'
    ? { bg: 'rgba(251, 146, 60, 0.2)', color: 'rgb(251, 146, 60)' }
    : { bg: 'rgba(239, 68, 68, 0.2)', color: 'rgb(252, 165, 165)' }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md" style={{ backgroundColor: statusStyle.bg, border: statusStyle.border }}>
              <Shield className="w-4 h-4" style={{ color: statusStyle.color }} />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold">AUDIT STATUS</CardTitle>
              <p className="text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
                G4+ | Hash Chain | Court-Proof | DEFCON
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <SemanticTooltip
              title="Audit & Sikkerhetsstatus"
              description="Kan vi stole på at dataene er ekte og uendret? Dette er 'alarm-tavlen' for systemsikkerhet."
              details={[
                'Hash: Kryptografisk bevis på at ingen har tuklet med data. 100% = alt OK.',
                'Proof: Hvor mange rapporter har fullstendig dokumentasjon.',
                'Bound: Antall grensebrudd. 0 = ingen ulovlige forsøk.',
                'DEFCON: GREEN=OK, YELLOW=obs, ORANGE=problem, RED=kritisk!'
              ]}
            />
            {/* Audit Health Score */}
            <div className="text-sm font-bold font-mono" style={{ color: getScoreColor(parseFloat(String(data?.audit_health_score || 0))) }}>
              {data?.audit_health_score || 0}
            </div>
            {/* Overall Status Dot */}
            <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${data?.overall_status === 'ALL_CLEAR' ? 'bg-green-400' : data?.overall_status === 'WARNING' ? 'bg-yellow-400' : 'bg-red-400'}`} />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Health Indicator Grid - Compact */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
          {/* Hash Chain */}
          <div className="p-2 rounded-md min-w-0" style={{ backgroundColor: indicators?.hash_chain === 'PASS' ? 'rgba(34, 197, 94, 0.1)' : indicators?.hash_chain === 'WARN' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(239, 68, 68, 0.1)' }}>
            <div className="flex items-center gap-1 mb-1">
              <LinkIcon className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Hash</span>
            </div>
            <span className="text-sm font-semibold font-mono block" style={{ color: indicators?.hash_chain === 'PASS' ? 'rgb(134, 239, 172)' : indicators?.hash_chain === 'WARN' ? 'rgb(253, 224, 71)' : 'rgb(252, 165, 165)' }}>
              {parseFloat(String(metrics?.hash_chain.integrity_pct || 100)).toFixed(0)}%
            </span>
          </div>

          {/* Court-Proof */}
          <div className="p-2 rounded-md min-w-0" style={{ backgroundColor: indicators?.court_proof === 'PASS' ? 'rgba(34, 197, 94, 0.1)' : indicators?.court_proof === 'WARN' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(239, 68, 68, 0.1)' }}>
            <div className="flex items-center gap-1 mb-1">
              <FileCheck className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Proof</span>
            </div>
            <span className="text-sm font-semibold font-mono block" style={{ color: indicators?.court_proof === 'PASS' ? 'rgb(134, 239, 172)' : indicators?.court_proof === 'WARN' ? 'rgb(253, 224, 71)' : 'rgb(252, 165, 165)' }}>
              {parseFloat(String(metrics?.court_proof.coverage_pct || 100)).toFixed(0)}%
            </span>
          </div>

          {/* Boundary */}
          <div className="p-2 rounded-md min-w-0" style={{ backgroundColor: indicators?.boundary === 'PASS' ? 'rgba(34, 197, 94, 0.1)' : indicators?.boundary === 'WARN' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(239, 68, 68, 0.1)' }}>
            <div className="flex items-center gap-1 mb-1">
              <Lock className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Bound</span>
            </div>
            <span className="text-sm font-semibold font-mono block" style={{ color: indicators?.boundary === 'PASS' ? 'rgb(134, 239, 172)' : indicators?.boundary === 'WARN' ? 'rgb(253, 224, 71)' : 'rgb(252, 165, 165)' }}>
              {parseInt(String(metrics?.boundary.violations || 0))}
            </span>
          </div>

          {/* DEFCON */}
          <div className="p-2 rounded-md min-w-0" style={{ backgroundColor: defconStyle.bg }}>
            <div className="flex items-center gap-1 mb-1">
              <Activity className="w-2.5 h-2.5 flex-shrink-0" style={{ color: defconStyle.color }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>DEFCON</span>
            </div>
            <span className="text-sm font-semibold font-mono block" style={{ color: defconStyle.color }}>
              {metrics?.system.defcon || 'GREEN'}
            </span>
          </div>
        </div>

        {/* Detailed Metrics - Compact */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          {/* Hash Chain Details */}
          <div className="p-2 rounded-md" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>ADR-011 Hash Chain</div>
            <div className="space-y-0.5 text-[10px]">
              <div className="flex justify-between">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Checks 24h</span>
                <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>{metrics?.hash_chain.checks_24h || 0}</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Valid</span>
                <span className="font-mono text-green-400">{metrics?.hash_chain.valid || 0}</span>
              </div>
            </div>
          </div>

          {/* Court-Proof Details */}
          <div className="p-2 rounded-md" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>Court-Proof</div>
            <div className="space-y-0.5 text-[10px]">
              <div className="flex justify-between">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Summaries 7d</span>
                <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>{metrics?.court_proof.summaries_7d || 0}</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>With query</span>
                <span className="font-mono text-green-400">{metrics?.court_proof.with_raw_query || 0}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Circuit Breaker Events - Compact */}
        {data?.recent_circuit_breaker_events && data.recent_circuit_breaker_events.length > 0 && (
          <div className="mb-3">
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Circuit Breakers (24h)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                    <th className="text-left py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Breaker</th>
                    <th className="text-center py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Before</th>
                    <th className="text-center py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>After</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_circuit_breaker_events.slice(0, 3).map((event, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid hsl(var(--border) / 0.2)' }}>
                      <td className="py-1 px-1.5 font-mono" style={{ color: 'hsl(var(--foreground))' }}>{event.breaker_name?.slice(0, 12)}</td>
                      <td className="py-1 px-1.5 text-center"><DefconBadge level={event.defcon_before} /></td>
                      <td className="py-1 px-1.5 text-center"><DefconBadge level={event.defcon_after} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Footer - Compact */}
        <div className="flex items-center justify-end mt-2 pt-2 text-[9px]" style={{ borderTop: '1px solid hsl(var(--border) / 0.5)', color: 'hsl(var(--muted-foreground))' }}>
          <span>{data?._meta?.fetched_at ? new Date(data._meta.fetched_at).toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit'}) : '—'}</span>
        </div>
      </CardContent>
    </Card>
  )
}

function HealthIndicatorCard({
  icon,
  title,
  status,
  value,
  subtitle,
  lastUpdate
}: {
  icon: React.ReactNode
  title: string
  status: 'PASS' | 'WARN' | 'FAIL'
  value: string
  subtitle: string
  lastUpdate?: string | null
}) {
  const statusStyle = status === 'PASS'
    ? { bg: 'rgba(34, 197, 94, 0.1)', iconColor: 'rgb(134, 239, 172)' }
    : status === 'WARN'
    ? { bg: 'rgba(245, 158, 11, 0.1)', iconColor: 'rgb(253, 224, 71)' }
    : { bg: 'rgba(239, 68, 68, 0.1)', iconColor: 'rgb(252, 165, 165)' }

  const StatusIcon = status === 'PASS' ? CheckCircle : status === 'WARN' ? AlertTriangle : XCircle

  return (
    <div className="p-4 rounded-lg" style={{ backgroundColor: statusStyle.bg }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span style={{ color: 'hsl(var(--muted-foreground))' }}>{icon}</span>
          <span className="text-sm font-semibold" style={{ color: 'hsl(var(--foreground))' }}>{title}</span>
        </div>
        <StatusIcon className="w-4 h-4" style={{ color: statusStyle.iconColor }} />
      </div>
      <div className="text-2xl font-bold mb-1" style={{ color: statusStyle.iconColor }}>{value}</div>
      <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{subtitle}</div>
      {lastUpdate && (
        <div className="text-xs mt-1 flex items-center gap-1" style={{ color: 'hsl(var(--muted-foreground) / 0.7)' }}>
          <Clock className="w-3 h-3" />
          {formatTimeAgo(lastUpdate)}
        </div>
      )}
    </div>
  )
}

function DefconBadge({ level }: { level: string }) {
  const style = level === 'GREEN'
    ? { bg: 'rgba(34, 197, 94, 0.2)', color: 'rgb(134, 239, 172)' }
    : level === 'YELLOW'
    ? { bg: 'rgba(245, 158, 11, 0.2)', color: 'rgb(253, 224, 71)' }
    : level === 'ORANGE'
    ? { bg: 'rgba(251, 146, 60, 0.2)', color: 'rgb(251, 146, 60)' }
    : { bg: 'rgba(239, 68, 68, 0.2)', color: 'rgb(252, 165, 165)' }

  return (
    <span className="px-2 py-0.5 rounded text-xs font-bold" style={{ backgroundColor: style.bg, color: style.color }}>
      {level}
    </span>
  )
}

// Helper functions
function getScoreColor(score: number): string {
  if (score >= 90) return 'rgb(134, 239, 172)'
  if (score >= 70) return 'rgb(253, 224, 71)'
  return 'rgb(252, 165, 165)'
}

function getIntegrityColor(pct: number): string {
  if (pct === 100) return 'rgb(134, 239, 172)'
  if (pct >= 95) return 'rgb(253, 224, 71)'
  return 'rgb(252, 165, 165)'
}

function getCoverageColor(pct: number): string {
  if (pct === 100) return 'rgb(134, 239, 172)'
  if (pct >= 95) return 'rgb(253, 224, 71)'
  return 'rgb(252, 165, 165)'
}

function formatTimeAgo(timestamp: string): string {
  const now = new Date()
  const then = new Date(timestamp)
  const diffMs = now.getTime() - then.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}d ago`
}

function SemanticTooltip({ title, description, details }: { title: string; description: string; details: string[] }) {
  return (
    <span className="group relative inline-flex">
      <Info className="w-3.5 h-3.5 cursor-help opacity-50 hover:opacity-100 transition-opacity" style={{ color: 'hsl(var(--muted-foreground))' }} />
      <span className="invisible group-hover:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2.5 text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-150 pointer-events-none w-72 z-50 shadow-xl" style={{ backgroundColor: 'rgb(25, 25, 30)', border: '1px solid rgb(70, 70, 80)', color: 'rgb(230, 230, 240)' }}>
        <div className="font-semibold text-xs mb-1.5" style={{ color: 'rgb(134, 239, 172)' }}>{title}</div>
        <div className="text-[11px] mb-2 leading-relaxed" style={{ color: 'rgb(180, 180, 195)' }}>{description}</div>
        <div className="space-y-1">
          {details.map((detail, i) => (
            <div key={i} className="text-[10px] leading-relaxed" style={{ color: 'rgb(200, 200, 215)' }}>• {detail}</div>
          ))}
        </div>
      </span>
    </span>
  )
}
