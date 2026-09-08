/**
 * Metacognitive Observability - Economic Perspective Component
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * Displays:
 * - Information Gain Ratio (IGR)
 * - EVPI Proxy (Expected Value of Perfect Information)
 * - Scent-to-Gain efficiency
 * - Calibration status (Brier scores when available)
 */

'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  DollarSign,
  TrendingUp,
  Target,
  BarChart3,
  Info,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react'

interface EconomicSummary {
  avg_information_gain_ratio: number
  total_query_cost_30d: number
  avg_evidence_coverage: number
  evpi_proxy_value: number
  regret_count_12w: number
  wisdom_count_12w: number
  avg_brier_score: number
  calibrated_forecasts: number
  calibration_status: string
  computed_at: string
}

interface EVPIData {
  week: string
  suppression_category: string
  suppression_count: number
  evpi_proxy: number
  avg_regret_magnitude: number
  regret_count: number
  wisdom_count: number
  opportunity_cost_indicator: string
}

interface IGRData {
  date: string
  querying_agent: string
  total_queries: number
  total_cost: number
  avg_evidence_coverage: number
  information_gain_ratio: number
}

interface EconomicData {
  perspective: string
  summary: EconomicSummary
  evpi_trend: EVPIData[]
  igr_trend: IGRData[]
  derived_metrics: {
    deferred_gain_ratio_pct: number
    suppression_wisdom_indicator: string
  }
  _meta: {
    source_views: string[]
    authority: string
    note?: string
    fetched_at: string
  }
}

export function EconomicPerspective() {
  const [data, setData] = useState<EconomicData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/metacognitive/economic')
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
            <span>Economic perspective unavailable: {error}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const summary = data?.summary
  const derived = data?.derived_metrics

  // Parse numeric values that come as strings from Postgres
  const igr = parseFloat(String(summary?.avg_information_gain_ratio || 0))
  const evpi = parseFloat(String(summary?.evpi_proxy_value || 0))
  const queryCost = parseFloat(String(summary?.total_query_cost_30d || 0))
  const wisdomRatio = parseFloat(String(derived?.deferred_gain_ratio_pct || 0))
  const brierScore = parseFloat(String(summary?.avg_brier_score || 0))
  const calibratedForecasts = parseInt(String(summary?.calibrated_forecasts || 0))
  const regretCount = parseInt(String(summary?.regret_count_12w || 0))
  const wisdomCount = parseInt(String(summary?.wisdom_count_12w || 0))

  // Wisdom indicator status
  const wisdomStatus = derived?.suppression_wisdom_indicator === 'HIGH' ? 'pass' :
                       derived?.suppression_wisdom_indicator === 'MEDIUM' ? 'warning' : 'fail'

  // Calibration status
  const calibrationStatus = summary?.calibration_status === 'CALIBRATED' ? 'pass' :
                            summary?.calibration_status === 'AWAITING_FINN_DATA' ? 'info' : 'warning'

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md" style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)' }}>
              <DollarSign className="w-4 h-4 text-green-400" />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold">ECONOMIC</CardTitle>
              <p className="text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
                IGR | EVPI Proxy | Calibration
              </p>
            </div>
          </div>
          <SemanticTooltip
            title="Økonomisk Perspektiv"
            description="Viser om informasjonen systemet henter faktisk er verdt pengene - får vi 'value for money'?"
            details={[
              'IGR: Verdi delt på kostnad. Over 1.2x er bra!',
              'EVPI: Hva det koster oss å ta feil. Lavere er bedre.',
              'Wisdom: Hvor ofte kloke valg var riktige.'
            ]}
          />
        </div>
      </CardHeader>
      <CardContent>
        {/* Main Metrics - Compact */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
          {/* IGR */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <TrendingUp className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>IGR</span>
            </div>
            <span className="text-sm font-semibold font-mono block truncate" style={{ color: getIGRColor(igr) }}>
              {igr > 0 ? igr.toFixed(1) : '—'}x
            </span>
            <HoverTip text="Information Gain Ratio - verdi delt på kostnad. Over 1.2x er bra!" />
          </div>

          {/* EVPI Proxy */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <Target className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>EVPI</span>
            </div>
            <span className="text-sm font-semibold font-mono block truncate" style={{ color: 'hsl(var(--foreground))' }}>
              ${evpi.toFixed(4)}
            </span>
            <HoverTip text="Expected Value of Perfect Information - hva det koster å ta feil. Lavere er bedre." />
          </div>

          {/* Wisdom Ratio */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <BarChart3 className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Wisdom</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-sm font-semibold font-mono" style={{ color: getWisdomColor(wisdomRatio) }}>
                {wisdomRatio.toFixed(0)}%
              </span>
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${wisdomStatus === 'pass' ? 'bg-green-400' : wisdomStatus === 'warning' ? 'bg-yellow-400' : 'bg-red-400'}`} />
            </div>
            <HoverTip text="Andel kloke beslutninger som viste seg å være riktige. Høyere er bedre!" />
          </div>

          {/* Query Cost 30d */}
          <div className="group/m p-2 rounded-md min-w-0 relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <DollarSign className="w-2.5 h-2.5 flex-shrink-0" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-[9px] uppercase tracking-wide truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>Cost 30d</span>
            </div>
            <span className="text-sm font-semibold font-mono block truncate" style={{ color: 'hsl(var(--foreground))' }}>
              ${queryCost.toFixed(2)}
            </span>
            <HoverTip text="Totalkostnad for informasjonssøk de siste 30 dagene." />
          </div>
        </div>

        {/* Regret/Wisdom Summary - Compact */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="p-2 rounded-md" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase" style={{ color: 'hsl(var(--muted-foreground))' }}>Regret 12w</span>
              <span className="text-sm font-semibold font-mono text-red-400">{regretCount}</span>
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-[10px] uppercase" style={{ color: 'hsl(var(--muted-foreground))' }}>Wisdom 12w</span>
              <span className="text-sm font-semibold font-mono text-green-400">{wisdomCount}</span>
            </div>
          </div>

          {/* Calibration Status */}
          <div className="p-2 rounded-md" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] uppercase" style={{ color: 'hsl(var(--muted-foreground))' }}>Calibration</span>
              <StatusBadge variant={calibrationStatus}>
                {summary?.calibration_status === 'AWAITING_FINN_DATA' ? 'AWAIT' : summary?.calibration_status || '—'}
              </StatusBadge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase" style={{ color: 'hsl(var(--muted-foreground))' }}>Brier</span>
              <span className="text-sm font-mono" style={{ color: 'hsl(var(--foreground))' }}>
                {brierScore > 0 ? brierScore.toFixed(3) : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* EVPI Trend Table - Compact */}
        {data?.evpi_trend && data.evpi_trend.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wide font-medium mb-1.5" style={{ color: 'hsl(var(--muted-foreground))' }}>
              EVPI Trend (12w)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                    <th className="text-left py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Cat</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>N</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>EVPI</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>R</th>
                    <th className="text-right py-1 px-1.5 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>W</th>
                  </tr>
                </thead>
                <tbody>
                  {data.evpi_trend.slice(0, 4).map((ev, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid hsl(var(--border) / 0.2)' }}>
                      <td className="py-1 px-1.5 font-mono" style={{ color: 'hsl(var(--foreground))' }}>{ev.suppression_category?.slice(0,8)}</td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>{ev.suppression_count}</td>
                      <td className="py-1 px-1.5 text-right font-mono" style={{ color: 'hsl(var(--foreground))' }}>
                        ${parseFloat(String(ev.evpi_proxy || 0)).toFixed(2)}
                      </td>
                      <td className="py-1 px-1.5 text-right font-mono text-red-400">{ev.regret_count}</td>
                      <td className="py-1 px-1.5 text-right font-mono text-green-400">{ev.wisdom_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* CEO-DIR-2026-025: Calibration Risk Warning (VEGA Mandate) */}
        {brierScore > 0.30 && (
          <div className="mt-2 p-2.5 rounded-md text-[10px] border" style={{
            backgroundColor: 'rgba(251, 146, 60, 0.15)',
            borderColor: 'rgba(251, 146, 60, 0.4)'
          }}>
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="font-semibold text-orange-300 mb-1">
                  CALIBRATION WARNING (CEO-DIR-2026-025)
                </div>
                <div style={{ color: 'rgb(220, 180, 140)' }}>
                  Brier Score {brierScore.toFixed(3)} &gt; 0.30 threshold. System is overconfident.
                  High-confidence decisions (&gt;90%) should be treated with caution until calibration improves.
                </div>
                <div className="mt-1.5 flex items-center gap-1.5" style={{ color: 'rgb(180, 160, 130)' }}>
                  <Clock className="w-3 h-3" />
                  <span>Target: Brier &lt; 0.30 for Phase 3 Learning Activation</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Note about calibration - Compact */}
        {data?._meta?.note && !brierScore && (
          <div className="mt-2 p-2 rounded-md text-[10px]" style={{ backgroundColor: 'rgba(96, 165, 250, 0.1)' }}>
            <span style={{ color: 'hsl(var(--muted-foreground))' }}>{data._meta.note}</span>
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
function getIGRColor(igr: number): string {
  if (igr >= 1.2) return 'rgb(134, 239, 172)' // green (good ROI)
  if (igr >= 0.8) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red (poor ROI)
}

function getWisdomColor(ratio: number): string {
  if (ratio >= 70) return 'rgb(134, 239, 172)' // green
  if (ratio >= 50) return 'rgb(253, 224, 71)' // yellow
  return 'rgb(252, 165, 165)' // red
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

function HoverTip({ text }: { text: string }) {
  return (
    <span className="invisible group-hover/m:visible absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2.5 py-2 text-[10px] rounded-md opacity-0 group-hover/m:opacity-100 transition-all duration-150 pointer-events-none w-52 z-50 text-center leading-relaxed shadow-lg" style={{ backgroundColor: 'rgb(30, 30, 35)', border: '1px solid rgb(60, 60, 70)', color: 'rgb(220, 220, 230)' }}>
      {text}
    </span>
  )
}
