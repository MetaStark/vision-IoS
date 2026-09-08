/**
 * Metacognitive Observability - Cognitive Perspective Component
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Displays:
 * - Chain-of-Query (CoQ) efficiency metrics
 * - Abort rate tracking
 * - CV (Coefficient of Variation) per regime
 * - Latency and cost metrics
 */

'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  Brain,
  Gauge,
  Timer,
  DollarSign,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Info,
  RefreshCw,
  HelpCircle,
} from 'lucide-react'

interface CognitiveSummary {
  coq_efficiency_score: number
  abort_rate_pct: number
  avg_latency_ms: number
  total_query_cost_7d: number
  cv_per_regime: Record<string, number>
  computed_at: string
}

interface DailyCoQMetrics {
  query_date: string
  querying_agent: string
  total_queries: number
  avg_latency_ms: number
  total_cost_usd: number
  aborted_queries: number
  abort_rate: number
  efficiency_score: number
}

interface RegimeVariance {
  dominant_regime: string
  week: string
  belief_count: number
  confidence_cv: number
  entropy_cv: number
  stability_indicator: string
}

interface CognitiveData {
  perspective: string
  summary: CognitiveSummary
  daily_trend: DailyCoQMetrics[]
  regime_variance: RegimeVariance[]
  _meta: {
    source_views: string[]
    authority: string
    fetched_at: string
  }
}

export function CognitivePerspective() {
  const [data, setData] = useState<CognitiveData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/metacognitive/cognitive')
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
            <span>Cognitive perspective unavailable: {error}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const summary = data?.summary

  // Parse numeric values that come as strings from Postgres
  const coqEfficiency = parseFloat(String(summary?.coq_efficiency_score || 0))
  const abortRate = parseFloat(String(summary?.abort_rate_pct || 0))
  const avgLatency = parseFloat(String(summary?.avg_latency_ms || 0))
  const queryCost = parseFloat(String(summary?.total_query_cost_7d || 0))

  // Calculate efficiency status
  const efficiencyStatus = coqEfficiency >= 80 ? 'pass' :
                           coqEfficiency >= 60 ? 'warning' : 'fail'

  // Calculate abort rate status (lower is better)
  const abortStatus = abortRate <= 5 ? 'pass' :
                      abortRate <= 15 ? 'warning' : 'fail'

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md" style={{ backgroundColor: 'rgba(147, 51, 234, 0.15)' }}>
              <Brain className="w-4 h-4 text-purple-400" />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold">COGNITIVE</CardTitle>
              <p className="text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
                CoQ Efficiency | Abort Rate | CV per Regime
              </p>
            </div>
          </div>
          <SemanticTooltip
            title="Kognitiv Perspektiv"
            description="Viser hvor effektivt systemet 'tenker' - altså hvor godt det søker etter og bruker informasjon."
            details={[
              'CoQ Eff: Karakter 0-100 på hvor effektivt systemet stiller spørsmål. Over 80 er bra.',
              'Abort: Hvor mange søk som feilet. Under 5% er bra.',
              'CV per Regime: Hvor stabil oppførselen er i ulike markeder. Lavere = bedre.'
            ]}
          />
        </div>
      </CardHeader>
      <CardContent>
        {/* Main Metrics - Compact Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
          {/* CoQ Efficiency Score */}
          <MetricCard
            label="CoQ Eff."
            value={coqEfficiency > 0 ? coqEfficiency.toFixed(0) : '—'}
            color={getScoreColor(coqEfficiency)}
            status={efficiencyStatus}
            tooltip="Karakter 0-100 på hvor effektivt systemet stiller spørsmål til databasen. Over 80 er bra!"
            icon={<Gauge className="w-2.5 h-2.5" />}
            showMeter
            meterValue={coqEfficiency}
          />

          {/* Abort Rate */}
          <MetricCard
            label="Abort"
            value={`${abortRate.toFixed(1)}%`}
            color={getAbortColor(abortRate)}
            status={abortStatus}
            tooltip="Hvor mange søk som ble avbrutt eller feilet. Under 5% er bra!"
            icon={<AlertTriangle className="w-2.5 h-2.5" />}
          />

          {/* Avg Latency */}
          <MetricCard
            label="Latency"
            value={avgLatency > 0 ? (avgLatency / 1000).toFixed(1) + 's' : '—'}
            color="hsl(var(--foreground))"
            tooltip="Gjennomsnittlig tid for et søk. Raskere er bedre!"
            icon={<Timer className="w-2.5 h-2.5" />}
          />

          {/* Query Cost 7d */}
          <MetricCard
            label="Cost 7d"
            value={`$${queryCost.toFixed(2)}`}
            color="hsl(var(--foreground))"
            tooltip="Totalkostnad for informasjonssøk de siste 7 dagene."
            icon={<DollarSign className="w-2.5 h-2.5" />}
          />
        </div>

        {/* CV per Regime - Compact */}
        <div className="mb-3">
          <div className="flex items-center gap-1.5 mb-1.5">
            <span className="text-[10px] uppercase tracking-wide font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>CV per Regime</span>
            <SemanticTooltip
              title="Variasjonskoeffisient per Regime"
              description="Måler hvor konsistent systemet oppfører seg i ulike markedssituasjoner. Lavere tall = mer forutsigbar."
              details={[
                'BULL: Oppgangsmarked - forventet høy aktivitet',
                'BEAR: Nedgangsmarked - forventet forsiktighet',
                'NEUTRAL: Sidelengs marked - balansert oppførsel'
              ]}
            />
          </div>
          <div className="grid grid-cols-3 gap-1.5">
            {['BULL', 'BEAR', 'NEUTRAL'].map(regime => {
              const cv = summary?.cv_per_regime?.[regime]
              const cvValue = typeof cv === 'number' ? cv : null
              return (
                <div key={regime} className="p-2 rounded-md text-center" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
                  <div className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: 'hsl(var(--muted-foreground))' }}>{regime}</div>
                  <div className="text-sm font-semibold font-mono" style={{ color: getCVColor(cvValue) }}>
                    {cvValue !== null ? cvValue.toFixed(3) : '—'}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Regime Variance Table - Compact */}
        {data?.regime_variance && data.regime_variance.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Regime Variance (4w)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                    <th className="text-left py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Regime</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>N</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Conf CV</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Ent CV</th>
                    <th className="text-center py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>St</th>
                  </tr>
                </thead>
                <tbody>
                  {data.regime_variance.slice(0, 6).map((rv, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid hsl(var(--border) / 0.2)' }}>
                      <td className="py-1 px-1.5 font-mono" style={{ color: 'hsl(var(--foreground))' }}>{rv.dominant_regime}</td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>{rv.belief_count}</td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: getCVColor(rv.confidence_cv) }}>
                        {rv.confidence_cv?.toFixed(3) || '—'}
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: getCVColor(rv.entropy_cv) }}>
                        {rv.entropy_cv?.toFixed(3) || '—'}
                      </td>
                      <td className="py-1 px-1.5 text-center">
                        <span className={`inline-block w-2 h-2 rounded-full ${rv.stability_indicator === 'STABLE' ? 'bg-green-400' : rv.stability_indicator === 'MODERATE' ? 'bg-yellow-400' : 'bg-red-400'}`} />
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
function getScoreColor(score: number): string {
  if (score >= 80) return 'rgb(134, 239, 172)' // green
  if (score >= 60) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red
}

function getAbortColor(rate: number): string {
  if (rate <= 5) return 'rgb(134, 239, 172)' // green (low is good)
  if (rate <= 15) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red
}

function getCVColor(cv: number | null): string {
  if (cv === null) return 'hsl(var(--muted-foreground))'
  if (cv <= 0.15) return 'rgb(134, 239, 172)' // green (stable)
  if (cv <= 0.25) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red (volatile)
}

function RadialMeter({ value, max }: { value: number; max: number }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100))

  return (
    <div className="w-full h-2 rounded-full mt-2 overflow-hidden" style={{ backgroundColor: 'hsl(var(--border))' }}>
      <div
        className="h-full rounded-full transition-all"
        style={{
          width: `${percentage}%`,
          backgroundColor: getScoreColor(value)
        }}
      />
    </div>
  )
}

function SemanticTooltip({ title, description, details }: { title: string; description: string; details: string[] }) {
  return (
    <span className="group relative inline-flex">
      <Info className="w-3.5 h-3.5 cursor-help opacity-50 hover:opacity-100 transition-opacity" style={{ color: 'hsl(var(--muted-foreground))' }} />
      <span className="invisible group-hover:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2.5 text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-150 pointer-events-none w-72 z-50 shadow-xl" style={{ backgroundColor: 'rgb(25, 25, 30)', border: '1px solid rgb(70, 70, 80)', color: 'rgb(230, 230, 240)' }}>
        <div className="font-semibold text-xs mb-1.5" style={{ color: 'rgb(147, 197, 253)' }}>{title}</div>
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

function MetricCard({
  label,
  value,
  color,
  status,
  tooltip,
  icon,
  showMeter,
  meterValue
}: {
  label: string
  value: string
  color: string
  status?: 'pass' | 'warning' | 'fail'
  tooltip: string
  icon?: React.ReactNode
  showMeter?: boolean
  meterValue?: number
}) {
  return (
    <div className="group/metric p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
      <div className="flex items-center gap-1 mb-1">
        {icon && <span className="flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }}>{icon}</span>}
        <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-sm font-semibold font-mono" style={{ color }}>{value}</span>
        {status && (
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${status === 'pass' ? 'bg-green-400' : status === 'warning' ? 'bg-yellow-400' : 'bg-red-400'}`} />
        )}
      </div>
      {showMeter && meterValue !== undefined && <RadialMeter value={meterValue} max={100} />}
      {/* Hover tooltip */}
      <span className="invisible group-hover/metric:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2.5 py-2 text-[10px] rounded-md opacity-0 group-hover/metric:opacity-100 transition-all duration-150 pointer-events-none w-52 z-50 text-center leading-relaxed shadow-lg" style={{ backgroundColor: 'rgb(30, 30, 35)', border: '1px solid rgb(60, 60, 70)', color: 'rgb(220, 220, 230)' }}>
        {tooltip}
      </span>
    </div>
  )
}
