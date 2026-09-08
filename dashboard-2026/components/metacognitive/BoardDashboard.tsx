/**
 * Board-Grade Dashboard - ACI Learning Status
 *
 * Authority: CEO-DIR-2026-036
 * Classification: CONSTITUTIONAL - Board Dashboard
 *
 * Three-layer visualization:
 * - LAG 1: Executive Summary (5 seconds) - Status at a glance
 * - LAG 2: Learning Trajectory (30 seconds) - 12-week trends with targets
 * - LAG 3: Attribution Deep-Dive (2 minutes) - Detailed breakdown
 */

'use client'

import { useEffect, useState } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Info,
  RefreshCw,
  Target,
  BarChart3,
  Gauge,
  Shield,
  Zap,
  Eye,
  Calendar,
} from 'lucide-react'

// Types
interface ExecutiveSummary {
  status: 'ON_TRACK' | 'AT_RISK' | 'BLOCKED' | 'UNKNOWN'
  trend: 'IMPROVING' | 'STABLE' | 'DEGRADING' | 'INSUFFICIENT_DATA'
  phase: string
  current_day: number
  headline: string
  insight: string
}

interface KPI {
  value: number
  value_pct?: number
  target: number
  delta?: number
  status: string
  description: string
}

interface KPIs {
  calibration_index: KPI
  restraint_index: KPI
  learning_velocity: KPI
  attribution_coverage: KPI
  regret_exposure: KPI
}

interface TrajectoryPoint {
  week: string
  regret: number
  wisdom: number
  suppressions: number
  regretTarget: number
  wisdomTarget: number
  isCurrent: boolean
}

interface AttributionCategory {
  count: number
  pct: number
  label: string
  description: string
  types: string[]
  alert?: boolean
}

interface AttributionCategories {
  by_design: AttributionCategory
  challenging: AttributionCategory
  surprising: AttributionCategory
}

interface CalibrationBand {
  band: string
  samples: number
  confidence: number
  accuracy: number
  brier: number
  gap: number
  status: string
}

interface PhaseMilestone {
  day: number
  date: string
  objective: string
  status: string
  isCurrent: boolean
}

interface CurrentWeek {
  label: string
  suppressions: number
  regret_pct: number
  wisdom_pct: number
  unresolved_pct: number
}

interface MagnitudeDistribution {
  low: number
  medium: number
  high: number
  extreme: number
}

interface BoardMetricsData {
  executive_summary: ExecutiveSummary
  kpis: KPIs
  trajectory: TrajectoryPoint[]
  attribution_categories: AttributionCategories | null
  calibration_bands: CalibrationBand[]
  phase_milestones: PhaseMilestone[]
  phase_progress: { completed: number; total: number; pct: number }
  current_week: CurrentWeek | null
  magnitude_distribution: MagnitudeDistribution | null
  _meta: { source: string; authority: string; fetched_at: string }
}

export function BoardDashboard() {
  const [data, setData] = useState<BoardMetricsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedLayer, setExpandedLayer] = useState<1 | 2 | 3>(1)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/metacognitive/board-metrics')
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
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="w-8 h-8 animate-spin" style={{ color: 'hsl(var(--muted-foreground))' }} />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <div className="flex items-center gap-3 py-8 text-red-400">
            <AlertTriangle className="w-6 h-6" />
            <span>Board metrics unavailable: {error}</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data) return null

  const { executive_summary, kpis, trajectory, attribution_categories, calibration_bands, phase_milestones, current_week } = data

  return (
    <div className="space-y-4">
      {/* LAG 1: Executive Summary (5 seconds) */}
      <Card className="overflow-hidden">
        <div
          className="p-4 cursor-pointer transition-colors hover:bg-opacity-80"
          style={{
            backgroundColor: executive_summary.status === 'ON_TRACK' ? 'rgba(34, 197, 94, 0.15)' :
                            executive_summary.status === 'AT_RISK' ? 'rgba(251, 146, 60, 0.15)' :
                            executive_summary.status === 'BLOCKED' ? 'rgba(239, 68, 68, 0.15)' :
                            'rgba(148, 163, 184, 0.15)'
          }}
          onClick={() => setExpandedLayer(expandedLayer === 1 ? 2 : 1)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Gauge className="w-5 h-5" style={{
                  color: executive_summary.status === 'ON_TRACK' ? 'rgb(34, 197, 94)' :
                         executive_summary.status === 'AT_RISK' ? 'rgb(251, 146, 60)' :
                         executive_summary.status === 'BLOCKED' ? 'rgb(239, 68, 68)' :
                         'rgb(148, 163, 184)'
                }} />
                <span className="text-lg font-bold tracking-tight" style={{ color: 'hsl(var(--foreground))' }}>
                  ACI LEARNING STATUS
                </span>
              </div>
              <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ backgroundColor: 'hsl(var(--secondary))', color: 'hsl(var(--muted-foreground))' }}>
                2026-W{String(Math.ceil((new Date().getTime() - new Date(new Date().getFullYear(), 0, 1).getTime()) / 604800000)).padStart(2, '0')}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge variant={
                executive_summary.status === 'ON_TRACK' ? 'pass' :
                executive_summary.status === 'AT_RISK' ? 'warning' :
                executive_summary.status === 'BLOCKED' ? 'fail' : 'info'
              }>
                {executive_summary.status.replace('_', ' ')}
              </StatusBadge>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="mt-4 mb-2">
            <div className="flex items-center justify-between text-xs mb-1">
              <span style={{ color: 'hsl(var(--muted-foreground))' }}>Wisdom Rate</span>
              <span className="font-mono font-bold" style={{ color: kpis.restraint_index.status === 'MET' ? 'rgb(34, 197, 94)' : 'hsl(var(--foreground))' }}>
                {(kpis.restraint_index.value * 100).toFixed(0)}%
              </span>
            </div>
            <div className="h-3 rounded-full overflow-hidden" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, kpis.restraint_index.value * 100)}%`,
                  backgroundColor: kpis.restraint_index.value >= 0.8 ? 'rgb(34, 197, 94)' :
                                   kpis.restraint_index.value >= 0.6 ? 'rgb(251, 191, 36)' : 'rgb(239, 68, 68)'
                }}
              />
            </div>
            <div className="flex items-center justify-between mt-1 text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
              <span>Target: 80%</span>
              <span>{kpis.restraint_index.delta !== undefined && kpis.restraint_index.delta >= 0 ? '+' : ''}{((kpis.restraint_index.delta || 0) * 100).toFixed(0)}pp to target</span>
            </div>
          </div>

          {/* Status Row */}
          <div className="flex items-center justify-between mt-3 pt-3" style={{ borderTop: '1px solid hsl(var(--border) / 0.5)' }}>
            <div className="flex items-center gap-4 text-xs">
              <div className="flex items-center gap-1.5">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Trend:</span>
                <span className={`flex items-center gap-0.5 font-medium ${
                  executive_summary.trend === 'IMPROVING' ? 'text-green-400' :
                  executive_summary.trend === 'DEGRADING' ? 'text-red-400' : 'text-slate-400'
                }`}>
                  {executive_summary.trend === 'IMPROVING' ? <TrendingUp className="w-3.5 h-3.5" /> :
                   executive_summary.trend === 'DEGRADING' ? <TrendingDown className="w-3.5 h-3.5" /> :
                   <Minus className="w-3.5 h-3.5" />}
                  {executive_summary.trend}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Risk:</span>
                <span className={`font-medium ${
                  executive_summary.status === 'ON_TRACK' ? 'text-green-400' :
                  executive_summary.status === 'AT_RISK' ? 'text-yellow-400' : 'text-red-400'
                }`}>
                  {executive_summary.status === 'ON_TRACK' ? 'LOW' :
                   executive_summary.status === 'AT_RISK' ? 'MEDIUM' : 'HIGH'}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Phase:</span>
                <span className="font-mono font-medium" style={{ color: 'hsl(var(--foreground))' }}>
                  {executive_summary.phase.replace('_', ' ')}
                </span>
              </div>
            </div>
            <Info className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground) / 0.5)' }} />
          </div>

          {/* One-liner */}
          <p className="mt-3 text-sm font-medium" style={{ color: 'hsl(var(--foreground))' }}>
            "{executive_summary.headline}"
          </p>
        </div>
      </Card>

      {/* LAG 2: Learning Trajectory (30 seconds) */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-400" />
              <div>
                <CardTitle className="text-sm font-semibold">LEARNING TRAJECTORY</CardTitle>
                <p className="text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  Regret vs Wisdom over 12 weeks | Target zones shown
                </p>
              </div>
            </div>
            <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Click bars for details
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
            <KPICard
              label="Calibration"
              value={kpis.calibration_index.value}
              target={kpis.calibration_index.target}
              status={kpis.calibration_index.status}
              icon={<Target className="w-4 h-4" />}
              description={kpis.calibration_index.description}
            />
            <KPICard
              label="Restraint"
              value={kpis.restraint_index.value}
              target={kpis.restraint_index.target}
              status={kpis.restraint_index.status}
              icon={<Shield className="w-4 h-4" />}
              description={kpis.restraint_index.description}
            />
            <KPICard
              label="Velocity"
              value={kpis.learning_velocity.value_pct || 0}
              target={0}
              status={kpis.learning_velocity.status}
              icon={<Zap className="w-4 h-4" />}
              description={kpis.learning_velocity.description}
              suffix="%/wk"
              isVelocity
            />
            <KPICard
              label="Attribution"
              value={kpis.attribution_coverage.value}
              target={kpis.attribution_coverage.target}
              status={kpis.attribution_coverage.status}
              icon={<Eye className="w-4 h-4" />}
              description={kpis.attribution_coverage.description}
            />
            <KPICard
              label="Regret Exp."
              value={kpis.regret_exposure.value}
              target={kpis.regret_exposure.target}
              status={kpis.regret_exposure.status}
              icon={<AlertTriangle className="w-4 h-4" />}
              description={kpis.regret_exposure.description}
              inverse
            />
          </div>

          {/* 12-Week Chart */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
            <div className="flex items-end gap-1 h-40 mb-2">
              {/* Y-axis labels */}
              <div className="flex flex-col justify-between h-full text-[9px] font-mono pr-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
                <span>100%</span>
                <span className="text-green-500">80%</span>
                <span>50%</span>
                <span className="text-red-500">15%</span>
                <span>0%</span>
              </div>

              {/* Target line for Wisdom (80%) */}
              <div className="flex-1 relative">
                <div className="absolute left-0 right-0 border-t-2 border-dashed border-green-600/40" style={{ top: '20%' }}>
                  <span className="absolute -top-3 right-0 text-[8px] text-green-500">Wisdom Target 80%</span>
                </div>
                {/* Target line for Regret (15%) */}
                <div className="absolute left-0 right-0 border-t-2 border-dashed border-red-600/40" style={{ top: '85%' }}>
                  <span className="absolute -bottom-3 right-0 text-[8px] text-red-500">Regret Target 15%</span>
                </div>

                {/* Bars */}
                <div className="flex items-end gap-1 h-full">
                  {trajectory.map((point, idx) => (
                    <div key={idx} className="flex-1 flex flex-col items-center group relative">
                      {/* Tooltip */}
                      <div className="hidden group-hover:block absolute bottom-full mb-2 p-2 rounded-lg text-xs z-10 whitespace-nowrap" style={{ backgroundColor: 'rgb(30, 30, 35)', border: '1px solid rgb(60, 60, 70)' }}>
                        <div className="font-semibold text-white mb-1">{point.week}</div>
                        <div className="text-green-400">Wisdom: {point.wisdom}%</div>
                        <div className="text-red-400">Regret: {point.regret}%</div>
                        <div className="text-slate-400">{point.suppressions} suppressions</div>
                      </div>

                      <div className="w-full flex flex-col h-full justify-end gap-px">
                        {/* Wisdom bar (goes up) */}
                        <div
                          className={`w-full rounded-t transition-all ${point.isCurrent ? 'ring-2 ring-blue-400' : ''}`}
                          style={{
                            height: `${Math.min(100, point.wisdom)}%`,
                            backgroundColor: point.wisdom >= 80 ? 'rgb(34, 197, 94)' : 'rgb(74, 222, 128)',
                            minHeight: '2px'
                          }}
                        />
                        {/* Regret bar (goes down from bottom) */}
                        <div
                          className={`w-full rounded-b transition-all ${point.isCurrent ? 'ring-2 ring-blue-400' : ''}`}
                          style={{
                            height: `${Math.min(100, point.regret)}%`,
                            backgroundColor: point.regret <= 15 ? 'rgb(239, 68, 68)' : 'rgb(248, 113, 113)',
                            minHeight: '2px'
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* X-axis labels */}
            <div className="flex gap-1 ml-8">
              {trajectory.map((point, idx) => (
                <div key={idx} className={`flex-1 text-center text-[8px] font-mono ${point.isCurrent ? 'font-bold text-blue-400' : ''}`} style={{ color: point.isCurrent ? undefined : 'hsl(var(--muted-foreground))' }}>
                  {point.week.split('-')[1]}
                </div>
              ))}
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-6 mt-3 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgb(74, 222, 128)' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Wisdom (blocking bad forecasts)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded" style={{ backgroundColor: 'rgb(248, 113, 113)' }} />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Regret (missed opportunities)</span>
              </div>
            </div>
          </div>

          {/* Gap to target insight */}
          {current_week && (
            <div className="mt-3 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
              <div className="flex items-center gap-2 mb-1">
                <Info className="w-4 h-4 text-blue-400" />
                <span className="font-semibold" style={{ color: 'hsl(var(--foreground))' }}>Gap to Target</span>
              </div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>
                Wisdom: {current_week.wisdom_pct >= 80 ? <span className="text-green-400">+{(current_week.wisdom_pct - 80).toFixed(0)}pp above target</span> : <span className="text-yellow-400">-{(80 - current_week.wisdom_pct).toFixed(0)}pp to target</span>}
                {' | '}
                Regret: {current_week.regret_pct <= 15 ? <span className="text-green-400">{(15 - current_week.regret_pct).toFixed(0)}pp below target</span> : <span className="text-yellow-400">-{(current_week.regret_pct - 15).toFixed(0)}pp to target</span>}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* LAG 3: Attribution Deep-Dive (2 minutes) */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Eye className="w-5 h-5 text-purple-400" />
              <div>
                <CardTitle className="text-sm font-semibold">ATTRIBUTION DEEP-DIVE</CardTitle>
                <p className="text-[10px]" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  Why forecasts are suppressed | Diagnostic quality
                </p>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {attribution_categories && (
            <div className="space-y-3">
              {/* By Design */}
              <AttributionRow
                category={attribution_categories.by_design}
                color="rgb(34, 197, 94)"
                bgColor="rgba(34, 197, 94, 0.1)"
              />

              {/* Challenging */}
              <AttributionRow
                category={attribution_categories.challenging}
                color="rgb(251, 191, 36)"
                bgColor="rgba(251, 191, 36, 0.1)"
              />

              {/* Surprising */}
              <AttributionRow
                category={attribution_categories.surprising}
                color="rgb(239, 68, 68)"
                bgColor="rgba(239, 68, 68, 0.1)"
                isAlert
              />
            </div>
          )}

          {/* Calibration Bands */}
          {calibration_bands.length > 0 && (
            <div className="mt-4 pt-4" style={{ borderTop: '1px solid hsl(var(--border))' }}>
              <h4 className="text-xs font-semibold mb-3" style={{ color: 'hsl(var(--foreground))' }}>
                CONFIDENCE CALIBRATION BY BAND
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {calibration_bands.map((band) => (
                  <CalibrationBandCard key={band.band} band={band} />
                ))}
              </div>
            </div>
          )}

          {/* Phase Milestones */}
          {phase_milestones.length > 0 && (
            <div className="mt-4 pt-4" style={{ borderTop: '1px solid hsl(var(--border))' }}>
              <div className="flex items-center gap-2 mb-3">
                <Calendar className="w-4 h-4 text-blue-400" />
                <h4 className="text-xs font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
                  PHASE MILESTONES
                </h4>
              </div>
              <div className="flex gap-2 overflow-x-auto pb-2">
                {phase_milestones.map((milestone) => (
                  <MilestoneCard key={milestone.day} milestone={milestone} />
                ))}
              </div>
            </div>
          )}

          {/* Insight Box */}
          <div className="mt-4 p-3 rounded-lg" style={{ backgroundColor: 'rgba(147, 51, 234, 0.1)', border: '1px solid rgba(147, 51, 234, 0.3)' }}>
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-purple-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <span className="font-semibold" style={{ color: 'hsl(var(--foreground))' }}>INSIGHT: </span>
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>
                  {attribution_categories && attribution_categories.surprising.pct > 30
                    ? `${attribution_categories.surprising.pct.toFixed(0)}% "Unknown" attribution = diagnostic gap, not learning failure. Action: Improve attribution tagging before judging learning quality.`
                    : 'Attribution coverage is healthy. Most suppressions are explainable by design or known challenges.'}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="flex items-center justify-between text-[10px] px-2" style={{ color: 'hsl(var(--muted-foreground) / 0.6)' }}>
        <span>Authority: {data._meta.authority}</span>
        <span>Source: {data._meta.source.split('+')[0].trim()}</span>
        <span>Updated: {new Date(data._meta.fetched_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
      </div>
    </div>
  )
}

// Sub-components

function KPICard({
  label,
  value,
  target,
  status,
  icon,
  description,
  suffix,
  isVelocity,
  inverse,
}: {
  label: string
  value: number
  target: number
  status: string
  icon: React.ReactNode
  description: string
  suffix?: string
  isVelocity?: boolean
  inverse?: boolean
}) {
  const isMet = status === 'MET' || status === 'IMPROVING'
  const isOnTrack = status === 'ON_TRACK' || status === 'STABLE'

  return (
    <div className="p-3 rounded-lg group relative" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
      {/* Tooltip */}
      <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-2 p-2 rounded-lg text-xs z-10 whitespace-nowrap" style={{ backgroundColor: 'rgb(30, 30, 35)', border: '1px solid rgb(60, 60, 70)' }}>
        <div className="text-slate-300">{description}</div>
        <div className="text-slate-400 mt-1">Target: {isVelocity ? 'Positive' : inverse ? `<${target}` : `>${(target * 100).toFixed(0)}%`}</div>
      </div>

      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] uppercase tracking-wide" style={{ color: 'hsl(var(--muted-foreground))' }}>{label}</span>
        <div style={{ color: isMet ? 'rgb(34, 197, 94)' : isOnTrack ? 'rgb(251, 191, 36)' : 'rgb(239, 68, 68)' }}>
          {icon}
        </div>
      </div>
      <div className="text-xl font-bold font-mono" style={{ color: 'hsl(var(--foreground))' }}>
        {isVelocity ? (value > 0 ? '+' : '') : ''}{isVelocity || inverse ? value.toFixed(1) : (value * 100).toFixed(0)}{suffix || (isVelocity || inverse ? '' : '%')}
      </div>
      <div className="flex items-center gap-1 mt-1">
        {isMet ? <CheckCircle className="w-3 h-3 text-green-400" /> :
         isOnTrack ? <Minus className="w-3 h-3 text-yellow-400" /> :
         <AlertTriangle className="w-3 h-3 text-red-400" />}
        <span className="text-[10px]" style={{ color: isMet ? 'rgb(34, 197, 94)' : isOnTrack ? 'rgb(251, 191, 36)' : 'rgb(239, 68, 68)' }}>
          {status}
        </span>
      </div>
    </div>
  )
}

function AttributionRow({
  category,
  color,
  bgColor,
  isAlert,
}: {
  category: AttributionCategory
  color: string
  bgColor: string
  isAlert?: boolean
}) {
  return (
    <div className="p-3 rounded-lg" style={{ backgroundColor: bgColor, border: isAlert && category.alert ? `1px solid ${color}` : 'none' }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm" style={{ color }}>{category.label}</span>
          {isAlert && category.alert && (
            <span className="px-1.5 py-0.5 text-[9px] font-bold rounded" style={{ backgroundColor: color, color: 'white' }}>
              HIGH - Needs attention
            </span>
          )}
        </div>
        <span className="text-lg font-bold font-mono" style={{ color }}>{category.pct.toFixed(0)}%</span>
      </div>
      <div className="h-2 rounded-full overflow-hidden mb-2" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
        <div className="h-full rounded-full" style={{ width: `${category.pct}%`, backgroundColor: color }} />
      </div>
      <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
        {category.description}
      </p>
      <div className="flex items-center gap-2 mt-2">
        {category.types.map((type, idx) => (
          <span key={idx} className="text-[10px] px-1.5 py-0.5 rounded" style={{ backgroundColor: 'hsl(var(--secondary))', color: 'hsl(var(--muted-foreground))' }}>
            {type}
          </span>
        ))}
      </div>
    </div>
  )
}

function CalibrationBandCard({ band }: { band: CalibrationBand }) {
  const statusColor = band.status === 'CALIBRATED' ? 'rgb(34, 197, 94)' :
                      band.status === 'OVERCONFIDENT' ? 'rgb(239, 68, 68)' : 'rgb(251, 191, 36)'

  return (
    <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold" style={{ color: 'hsl(var(--foreground))' }}>{band.band}</span>
        <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ backgroundColor: statusColor, color: 'white' }}>
          {band.status}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span style={{ color: 'hsl(var(--muted-foreground))' }}>Conf: </span>
          <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>{band.confidence}%</span>
        </div>
        <div>
          <span style={{ color: 'hsl(var(--muted-foreground))' }}>Acc: </span>
          <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>{band.accuracy}%</span>
        </div>
        <div>
          <span style={{ color: 'hsl(var(--muted-foreground))' }}>Gap: </span>
          <span className="font-mono" style={{ color: band.gap > 10 ? 'rgb(239, 68, 68)' : band.gap > 5 ? 'rgb(251, 191, 36)' : 'rgb(34, 197, 94)' }}>
            {band.gap > 0 ? '+' : ''}{band.gap}pp
          </span>
        </div>
        <div>
          <span style={{ color: 'hsl(var(--muted-foreground))' }}>n=</span>
          <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>{band.samples}</span>
        </div>
      </div>
    </div>
  )
}

function MilestoneCard({ milestone }: { milestone: PhaseMilestone }) {
  const statusColor = milestone.status === 'COMPLETED' ? 'rgb(34, 197, 94)' :
                      milestone.status === 'IN_PROGRESS' ? 'rgb(59, 130, 246)' : 'rgb(148, 163, 184)'

  return (
    <div
      className={`p-2 rounded-lg min-w-[120px] flex-shrink-0 ${milestone.isCurrent ? 'ring-2 ring-blue-400' : ''}`}
      style={{ backgroundColor: 'hsl(var(--secondary))' }}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono font-bold" style={{ color: 'hsl(var(--foreground))' }}>D{milestone.day}</span>
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: statusColor }} />
      </div>
      <p className="text-[10px] line-clamp-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
        {milestone.objective}
      </p>
    </div>
  )
}
