/**
 * Metacognitive Observability - Epistemic Perspective Component
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Displays:
 * - Parametric vs External boundary metrics
 * - Boundary confidence tracking
 * - Belief-policy divergence metrics
 * - Suppression ledger insights
 */

'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  Shield,
  AlertTriangle,
  TrendingDown,
  Info,
  RefreshCw,
  Lock,
  Unlock,
} from 'lucide-react'

interface SuppressionSummary {
  suppression_category: string
  count: number
  avg_confidence_delta: number
  regret_rate: number
  wisdom_rate: number
}

interface BeliefPolicyDivergence {
  date: string
  total_beliefs: number
  suppressed_count: number
  divergence_rate: number
}

interface BoundaryStatus {
  total_validations: number
  passed_count: number
  failed_count: number
  pass_rate: number
}

interface LessonBreakdown {
  lesson_category: string
  count: number
}

interface EpistemicData {
  perspective: string
  summary: {
    total_suppressions_30d: number
    avg_regret_rate: number
    avg_wisdom_rate: number
    boundary_pass_rate: number
    boundary_violations: number
    computed_at: string
  }
  suppression_by_category: SuppressionSummary[]
  divergence_trend: BeliefPolicyDivergence[]
  boundary_status: BoundaryStatus
  lesson_breakdown: LessonBreakdown[]
  _meta: {
    source_tables: string[]
    authority: string
    fetched_at: string
  }
}

export function EpistemicPerspective() {
  const [data, setData] = useState<EpistemicData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/metacognitive/epistemic')
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
    const interval = setInterval(fetchData, 10000) // 10s polling
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-5 h-5 animate-spin" style={{ color: 'hsl(var(--muted-foreground))' }} />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center gap-2 py-4 text-red-400 text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>Epistemic unavailable: {error}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const summary = data?.summary
  const boundaryStatus = data?.boundary_status

  // Parse numeric values
  const boundaryPassRate = parseFloat(String(summary?.boundary_pass_rate || 100))
  const boundaryViolations = parseInt(String(summary?.boundary_violations || 0))
  const avgRegretRate = parseFloat(String(summary?.avg_regret_rate || 0))
  const totalSuppressions = parseInt(String(summary?.total_suppressions_30d || 0))

  // Boundary health status
  const boundaryHealth = boundaryPassRate >= 95 ? 'pass' :
                         boundaryPassRate >= 80 ? 'warning' : 'fail'

  // Violations status
  const violationStatus = boundaryViolations === 0 ? 'pass' :
                          boundaryViolations < 5 ? 'warning' : 'fail'

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md" style={{ backgroundColor: 'rgba(96, 165, 250, 0.15)' }}>
              <Shield className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold">EPISTEMIC</CardTitle>
              <p className="text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Boundary Health | Divergence | Suppression
              </p>
            </div>
          </div>
          <SemanticTooltip
            title="Epistemisk Perspektiv"
            description="Handler om kunnskapsgrenser - vet systemet hva det vet, og hva det IKKE vet?"
            details={[
              'Boundary: Hvor ofte systemet holder seg innenfor sine grenser. 100% = perfekt.',
              'Violations: Antall regelbrudd. 0 er ideelt!',
              'Suppression: Signaler stoppet pga. usikkerhet.'
            ]}
          />
        </div>
      </CardHeader>
      <CardContent>
        {/* Main Metrics - Compact Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
          {/* Boundary Pass Rate */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <Lock className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Boundary</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-sm font-semibold font-mono" style={{ color: getBoundaryColor(boundaryPassRate) }}>
                {boundaryPassRate.toFixed(0)}%
              </span>
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${boundaryHealth === 'pass' ? 'bg-green-400' : boundaryHealth === 'warning' ? 'bg-yellow-400' : 'bg-red-400'}`} />
            </div>
            <HoverTip text="Hvor ofte systemet holder seg innenfor kunnskapsgrensene. 100% = perfekt!" />
          </div>

          {/* Boundary Violations */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <AlertTriangle className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Violations</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-sm font-semibold font-mono" style={{ color: getViolationColor(boundaryViolations) }}>
                {boundaryViolations}
              </span>
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${violationStatus === 'pass' ? 'bg-green-400' : violationStatus === 'warning' ? 'bg-yellow-400' : 'bg-red-400'}`} />
            </div>
            <HoverTip text="Antall ganger systemet har brutt sine egne regler. 0 er ideelt!" />
          </div>

          {/* Regret Rate */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <TrendingDown className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Regret</span>
            </div>
            <span className="text-sm font-semibold font-mono block" style={{ color: getRegretColor(avgRegretRate) }}>
              {avgRegretRate.toFixed(0)}%
            </span>
            <HoverTip text="Gjennomsnittlig angre-rate - hvor ofte beslutninger viste seg å være feil. Lavere er bedre." />
          </div>

          {/* Total Suppressions */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <Unlock className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Supp 30d</span>
            </div>
            <span className="text-sm font-semibold font-mono block" style={{ color: 'hsl(var(--foreground))' }}>
              {totalSuppressions}
            </span>
            <HoverTip text="Antall signaler som ble stoppet de siste 30 dagene fordi systemet var usikkert." />
          </div>
        </div>

        {/* Suppression by Category - Compact */}
        {data?.suppression_by_category && data.suppression_by_category.length > 0 && (
          <div className="mb-3">
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Suppression by Category
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {data.suppression_by_category.slice(0, 4).map((cat, idx) => (
                <div key={idx} className="p-2 rounded-md flex items-center justify-between" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
                  <span className="text-[10px] font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {cat.suppression_category?.slice(0, 10)}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold font-mono" style={{ color: 'hsl(var(--foreground))' }}>{cat.count}</span>
                    <span className="text-[9px] text-red-400">R:{(parseFloat(String(cat.regret_rate)) * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Belief-Policy Divergence Trend - Compact */}
        {data?.divergence_trend && data.divergence_trend.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Divergence (14d)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                    <th className="text-left py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Date</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Beliefs</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Supp</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Div%</th>
                  </tr>
                </thead>
                <tbody>
                  {data.divergence_trend.slice(0, 5).map((div, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid hsl(var(--border) / 0.2)' }}>
                      <td className="py-1 px-1.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        {div.date ? new Date(div.date).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '—'}
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: 'hsl(var(--foreground))' }}>
                        {div.total_beliefs}
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: parseInt(String(div.suppressed_count)) > 0 ? 'rgb(253, 224, 71)' : 'hsl(var(--foreground))' }}>
                        {div.suppressed_count}
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: getDivergenceColor(div.divergence_rate) }}>
                        {div.divergence_rate !== null ? (parseFloat(String(div.divergence_rate)) * 100).toFixed(0) + '%' : '—'}
                      </td>
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

// Helper functions
function getBoundaryColor(rate: number): string {
  if (rate >= 95) return 'rgb(134, 239, 172)' // green
  if (rate >= 80) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red
}

function getViolationColor(count: number): string {
  if (count === 0) return 'rgb(134, 239, 172)' // green
  if (count < 5) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red
}

function getRegretColor(rate: number): string {
  if (rate <= 15) return 'rgb(134, 239, 172)' // green (low regret is good)
  if (rate <= 25) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red
}

function getDivergenceColor(rate: number | null): string {
  if (rate === null) return 'hsl(var(--muted-foreground))'
  const numRate = parseFloat(String(rate))
  if (numRate <= 0.1) return 'rgb(134, 239, 172)' // green (low divergence is good)
  if (numRate <= 0.2) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red
}

function SemanticTooltip({ title, description, details }: { title: string; description: string; details: string[] }) {
  return (
    <span className="group relative inline-flex">
      <Info className="w-3.5 h-3.5 cursor-help opacity-50 hover:opacity-100 transition-opacity" style={{ color: 'hsl(var(--muted-foreground))' }} />
      <span className="invisible group-hover:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-150 pointer-events-none w-64 z-50 shadow-xl" style={{ backgroundColor: 'hsl(var(--popover))', border: '1px solid hsl(var(--border))', color: 'hsl(var(--popover-foreground))' }}>
        <div className="font-semibold text-xs mb-1" style={{ color: 'hsl(var(--primary))' }}>{title}</div>
        <div className="text-xs mb-1.5 leading-tight" style={{ color: 'hsl(var(--muted-foreground))' }}>{description}</div>
        <div className="space-y-0.5">
          {details.map((detail, i) => (
            <div key={i} className="font-mono text-[10px] leading-tight" style={{ color: 'hsl(var(--foreground))' }}>• {detail}</div>
          ))}
        </div>
      </span>
    </span>
  )
}

function HoverTip({ text }: { text: string }) {
  return (
    <span className="invisible group-hover/m:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2.5 py-2 text-[10px] rounded-md opacity-0 group-hover/m:opacity-100 transition-all duration-150 pointer-events-none w-52 z-50 text-center leading-relaxed shadow-lg" style={{ backgroundColor: 'rgb(30, 30, 35)', border: '1px solid rgb(60, 60, 70)', color: 'rgb(220, 220, 230)' }}>
      {text}
    </span>
  )
}
