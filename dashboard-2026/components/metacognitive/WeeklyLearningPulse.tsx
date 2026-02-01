/**
 * Metacognitive Observability - Weekly Learning Pulse Component
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Displays:
 * - Weekly regret/wisdom metrics
 * - Attribution breakdown (TYPE_A, TYPE_B, TYPE_C, TYPE_X)
 * - Learning health indicators
 * - Trailing 12-week trends
 */

'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Info,
  RefreshCw,
  BarChart3,
} from 'lucide-react'

interface CurrentWeek {
  week_label: string
  total_suppressions: number
  regret_pct: number
  wisdom_pct: number
  unresolved_pct: number
}

interface AttributionType {
  count: number
  pct: number
  label: string
}

interface AttributionBreakdown {
  type_a_hysteresis: AttributionType
  type_b_confidence: AttributionType
  type_c_data: AttributionType
  type_x_unknown: AttributionType
}

interface WeeklyHistory {
  week_label: string
  regret_rate: number
  wisdom_rate: number
  total: number
}

interface MagnitudeBreakdown {
  low: number
  medium: number
  high: number
  extreme: number
}

interface WeeklyPulseData {
  current_week: CurrentWeek | null
  attribution_breakdown: AttributionBreakdown | null
  learning_health: 'EXCELLENT' | 'GOOD' | 'WARNING' | 'CRITICAL' | 'NO_DATA' | 'ERROR'
  trend: 'IMPROVING' | 'STABLE' | 'DEGRADING' | 'INSUFFICIENT_DATA'
  weekly_history: WeeklyHistory[]
  magnitude_breakdown: MagnitudeBreakdown | null
  _meta: {
    source_view: string
    authority: string
    weeks_analyzed: number
    fetched_at: string
  }
}

export function WeeklyLearningPulse() {
  const [data, setData] = useState<WeeklyPulseData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/metacognitive/weekly-pulse')
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
    const interval = setInterval(fetchData, 30000) // 30s polling (less frequent for weekly data)
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
            <span>Weekly pulse unavailable: {error}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const currentWeek = data?.current_week
  const attribution = data?.attribution_breakdown

  // Get health status variant
  const healthVariant = data?.learning_health === 'EXCELLENT' ? 'pass' :
                        data?.learning_health === 'GOOD' ? 'pass' :
                        data?.learning_health === 'WARNING' ? 'warning' :
                        data?.learning_health === 'CRITICAL' ? 'fail' : 'info'

  // Get trend icon
  const TrendIcon = data?.trend === 'IMPROVING' ? TrendingUp :
                    data?.trend === 'DEGRADING' ? TrendingDown : Minus

  const trendColor = data?.trend === 'IMPROVING' ? 'text-green-400' :
                     data?.trend === 'DEGRADING' ? 'text-red-400' : 'text-slate-400'

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md" style={{ backgroundColor: 'rgba(251, 146, 60, 0.15)' }}>
              <Activity className="w-4 h-4 text-orange-400" />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold">LEARNING PULSE</CardTitle>
              <p className="text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Regret/Wisdom | Attribution | 12w Trend
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <SemanticTooltip
              title="Læringspuls"
              description="Viser hvordan systemet lærer over tid - blir det smartere eller gjør det samme feil igjen?"
              details={[
                'Regret (Rød): Beslutninger vi angrer på',
                'Wisdom (Grønn): Kloke valg som var riktige',
                'Trend: Pil opp = forbedring, ned = forverring'
              ]}
            />
            <StatusBadge variant={healthVariant}>
              {data?.learning_health === 'EXCELLENT' ? 'OK' : data?.learning_health === 'GOOD' ? 'OK' : data?.learning_health === 'WARNING' ? '!' : data?.learning_health === 'CRITICAL' ? 'X' : '?'}
            </StatusBadge>
            <div className={`flex items-center gap-0.5 ${trendColor}`}>
              <TrendIcon className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Current Week Summary - Compact */}
        {currentWeek && (
          <div className="mb-3 p-2.5 rounded-md" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium" style={{ color: 'hsl(var(--foreground))' }}>
                {currentWeek.week_label}
              </span>
              <span className="text-[10px] font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>
                {currentWeek.total_suppressions} supp.
              </span>
            </div>

            {/* Stacked Progress Bar - Compact */}
            <div className="h-5 rounded overflow-hidden flex mb-2">
              <div className="flex items-center justify-center" style={{ width: `${currentWeek.regret_pct}%`, backgroundColor: 'rgb(239, 68, 68)', minWidth: currentWeek.regret_pct > 0 ? '20px' : '0' }}>
                {currentWeek.regret_pct > 8 && <span className="text-[9px] font-bold text-white">{currentWeek.regret_pct.toFixed(0)}%</span>}
              </div>
              <div className="flex items-center justify-center" style={{ width: `${currentWeek.wisdom_pct}%`, backgroundColor: 'rgb(34, 197, 94)', minWidth: currentWeek.wisdom_pct > 0 ? '20px' : '0' }}>
                {currentWeek.wisdom_pct > 8 && <span className="text-[9px] font-bold text-white">{currentWeek.wisdom_pct.toFixed(0)}%</span>}
              </div>
              <div className="flex items-center justify-center" style={{ width: `${currentWeek.unresolved_pct}%`, backgroundColor: 'rgb(148, 163, 184)', minWidth: currentWeek.unresolved_pct > 0 ? '20px' : '0' }}>
                {currentWeek.unresolved_pct > 8 && <span className="text-[9px] font-bold text-white">{currentWeek.unresolved_pct.toFixed(0)}%</span>}
              </div>
            </div>

            {/* Legend - Compact */}
            <div className="flex items-center justify-center gap-3 text-[9px]">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: 'rgb(239, 68, 68)' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>R:{currentWeek.regret_pct.toFixed(0)}%</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: 'rgb(34, 197, 94)' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>W:{currentWeek.wisdom_pct.toFixed(0)}%</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: 'rgb(148, 163, 184)' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>U:{currentWeek.unresolved_pct.toFixed(0)}%</span>
              </div>
            </div>
          </div>
        )}

        {/* Attribution Breakdown - Compact */}
        {attribution && (
          <div className="mb-3">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-[10px] uppercase tracking-wide font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Attribution</span>
              <SemanticTooltip
                title="Attribusjon - Hvorfor ble signaler stoppet?"
                description="Viser årsaken til at systemet valgte å ikke handle på et signal."
                details={[
                  'A (Hysteresis): Ventet for lenge med å reagere',
                  'B (Confidence): For usikker til å handle',
                  'C (Data): Manglet nødvendig data',
                  'X (Unknown): Ukjent årsak'
                ]}
              />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              <AttributionCard type="A" count={attribution.type_a_hysteresis.count} pct={attribution.type_a_hysteresis.pct} color="rgb(147, 51, 234)" />
              <AttributionCard type="B" count={attribution.type_b_confidence.count} pct={attribution.type_b_confidence.pct} color="rgb(59, 130, 246)" />
              <AttributionCard type="C" count={attribution.type_c_data.count} pct={attribution.type_c_data.pct} color="rgb(234, 179, 8)" />
              <AttributionCard type="X" count={attribution.type_x_unknown.count} pct={attribution.type_x_unknown.pct} color="rgb(156, 163, 175)" />
            </div>
          </div>
        )}

        {/* Magnitude Breakdown - Compact */}
        {data?.magnitude_breakdown && (
          <div className="mb-3">
            <div className="flex items-center gap-1.5 mb-1.5">
              <span className="text-[10px] uppercase tracking-wide font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Regret Magnitude</span>
              <SemanticTooltip
                title="Alvorlighetsgrad på feil"
                description="Hvor store konsekvenser hadde feilene? Ideelt: mest L og M, få H og X."
                details={[
                  'L (Low): Liten feil, minimal konsekvens',
                  'M (Medium): Moderat feil',
                  'H (High): Alvorlig feil',
                  'X (Extreme): Kritisk feil som krever oppmerksomhet'
                ]}
              />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              <MagnitudeCard label="L" count={data.magnitude_breakdown.low} color="rgb(134, 239, 172)" />
              <MagnitudeCard label="M" count={data.magnitude_breakdown.medium} color="rgb(253, 224, 71)" />
              <MagnitudeCard label="H" count={data.magnitude_breakdown.high} color="rgb(251, 146, 60)" />
              <MagnitudeCard label="X" count={data.magnitude_breakdown.extreme} color="rgb(239, 68, 68)" />
            </div>
          </div>
        )}

        {/* 12-Week Trend Chart - Compact */}
        {data?.weekly_history && data.weekly_history.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
              12w Trend
            </div>
            <div className="flex items-end gap-0.5 h-16">
              {data.weekly_history.slice().reverse().map((week, idx) => (
                <div key={idx} className="flex-1 flex flex-col items-center" title={`${week.week_label}: R:${week.regret_rate}% W:${week.wisdom_rate}%`}>
                  <div className="w-full flex flex-col-reverse" style={{ height: '48px' }}>
                    <div className="w-full" style={{ height: `${Math.min(100, week.regret_rate)}%`, backgroundColor: 'rgb(239, 68, 68)', minHeight: week.regret_rate > 0 ? '1px' : '0' }} />
                    <div className="w-full" style={{ height: `${Math.min(100, week.wisdom_rate)}%`, backgroundColor: 'rgb(34, 197, 94)', minHeight: week.wisdom_rate > 0 ? '1px' : '0' }} />
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-center gap-3 mt-1 text-[9px]">
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: 'rgb(239, 68, 68)' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Regret</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: 'rgb(34, 197, 94)' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Wisdom</span>
              </div>
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

function AttributionCard({ type, count, pct, color }: { type: string; count: number; pct: number; color: string }) {
  return (
    <div className="p-2 rounded-md text-center" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
      <div className="text-[9px] font-mono font-semibold mb-0.5" style={{ color }}>{type}</div>
      <div className="text-sm font-bold font-mono" style={{ color: 'hsl(var(--foreground))' }}>{count}</div>
      <div className="text-[9px]" style={{ color: 'hsl(var(--muted-foreground))' }}>{pct}%</div>
    </div>
  )
}

function MagnitudeCard({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="p-2 rounded-md text-center min-w-0" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
      <div className="text-[9px] uppercase tracking-wider mb-0.5" style={{ color: 'hsl(var(--muted-foreground))' }}>{label}</div>
      <div className="text-sm font-bold font-mono" style={{ color }}>{count}</div>
    </div>
  )
}

function SemanticTooltip({ title, description, details }: { title: string; description: string; details: string[] }) {
  return (
    <span className="group relative inline-flex">
      <Info className="w-3.5 h-3.5 cursor-help opacity-50 hover:opacity-100 transition-opacity" style={{ color: 'hsl(var(--muted-foreground))' }} />
      <span className="invisible group-hover:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2.5 text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-all duration-150 pointer-events-none w-72 z-50 shadow-xl" style={{ backgroundColor: 'rgb(25, 25, 30)', border: '1px solid rgb(70, 70, 80)', color: 'rgb(230, 230, 240)' }}>
        <div className="font-semibold text-xs mb-1.5" style={{ color: 'rgb(251, 146, 60)' }}>{title}</div>
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
