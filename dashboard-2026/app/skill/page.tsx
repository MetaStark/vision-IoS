/**
 * Alpha Epistemology - Skill & Governance Dashboard
 * CEO Directive: CD-G2-C-DASH-SKILL-SCORECARD-2025-12-13
 *
 * Classification: G2-C Read-Only Observability - Non-Executing
 * Authority: ADR-004, ADR-012, ADR-013, IoS-010
 *
 * This tab gamifies Governance + Skill - not raw PnL.
 * All metrics are read-only projections from canonical database sources.
 */

import { Suspense } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { queryMany, queryOne } from '@/lib/db'
import {
  Brain,
  Target,
  Gauge,
  Shield,
  Clock,
  DollarSign,
  Award,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Timer,
  Zap,
  Activity,
  Info,
} from 'lucide-react'

export const revalidate = 30 // 30-second refresh

// ============================================================================
// Types
// ============================================================================

interface StrategyMetrics {
  strategy_id: string
  timeframe: string
  fss_score: number | null
  ci_width: number | null
  brier_score: number | null
  sample_size: number
  status: 'NOT_ENOUGH_DATA' | 'EMERGING' | 'SIGNIFICANT'
}

interface GovernanceMetrics {
  ttl_compliance_rate: number
  ttl_compliance_badge: 'GREEN' | 'YELLOW' | 'RED'
  llm_spend_today: number
  llm_budget_daily: number
  llm_efficiency_badge: 'GREEN' | 'YELLOW' | 'RED'
  fortress_streak_days: number
  fortress_badge: 'GREEN' | 'YELLOW' | 'RED'
}

interface LeaderboardEntry {
  strategy_id: string
  metric_value: number | null
  sample_size: number
  rank: number
}

// ============================================================================
// Minimum Sample Size (Anti-P-Hacking)
// ============================================================================

const MIN_SAMPLE_SIZE = 30 // Fixed, not adjustable from dashboard

// ============================================================================
// Main Page
// ============================================================================

export default async function SkillDashboardPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: 'hsl(var(--foreground))' }}>
            Alpha Epistemology
          </h1>
          <p className="text-sm mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Skill & Governance Scorecard | G2-C Read-Only Observability
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
          <Info className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground))' }} />
          <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Min Sample Size: {MIN_SAMPLE_SIZE} | No PnL Headlines
          </span>
        </div>
      </div>

      {/* Top Row: 5 Strategy Tiles */}
      <div className="grid grid-cols-5 gap-4">
        <Suspense fallback={<SkeletonCard />}>
          <StrategyTile strategyId="STRAT_SEC_V1" label="SEC" timeframe="Seconds" />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <StrategyTile strategyId="STRAT_HOUR_V1" label="HOUR" timeframe="Hours" />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <StrategyTile strategyId="STRAT_DAY_V1" label="DAY" timeframe="Days" />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <StrategyTile strategyId="STRAT_WEEK_V1" label="WEEK" timeframe="Weeks" />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <GovernanceTile />
        </Suspense>
      </div>

      {/* Middle Section: Leaderboards */}
      <div className="grid grid-cols-3 gap-6">
        <Suspense fallback={<SkeletonCard />}>
          <LeaderboardPanel
            title="The Alchemist"
            subtitle="Skill Ranking (FSS)"
            icon={Brain}
            metricName="FSS Score"
          />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <LeaderboardPanel
            title="The Oracle"
            subtitle="Calibration Ranking"
            icon={Target}
            metricName="Brier Score"
            lowerIsBetter
          />
        </Suspense>
        <Suspense fallback={<SkeletonCard />}>
          <LeaderboardPanel
            title="The Stabilizer"
            subtitle="Reliability Ranking"
            icon={Gauge}
            metricName="CI Width"
            lowerIsBetter
          />
        </Suspense>
      </div>

      {/* Bottom Section: Calibration Curves */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            Calibration Curves
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-6">
            <Suspense fallback={<SkeletonCard />}>
              <CalibrationChart strategyId="STRAT_SEC_V1" label="SEC" />
            </Suspense>
            <Suspense fallback={<SkeletonCard />}>
              <CalibrationChart strategyId="STRAT_HOUR_V1" label="HOUR" />
            </Suspense>
            <Suspense fallback={<SkeletonCard />}>
              <CalibrationChart strategyId="STRAT_DAY_V1" label="DAY" />
            </Suspense>
            <Suspense fallback={<SkeletonCard />}>
              <CalibrationChart strategyId="STRAT_WEEK_V1" label="WEEK" />
            </Suspense>
          </div>
        </CardContent>
      </Card>

      {/* Data Provenance Footer */}
      <Suspense fallback={null}>
        <DataProvenanceFooter />
      </Suspense>
    </div>
  )
}

// ============================================================================
// Strategy Tile Component
// ============================================================================

async function StrategyTile({ strategyId, label, timeframe }: { strategyId: string; label: string; timeframe: string }) {
  // Query skill metrics from canonical source
  const metrics = await queryOne<{
    sharpe_ratio: number | null
    win_rate: number | null
    total_trades: number
    calculated_at: string | null
  }>(`
    SELECT
      sharpe_ratio::float,
      win_rate::float,
      total_trades,
      calculated_at::text
    FROM fhq_execution.g2c_skill_metrics
    WHERE strategy_id = $1
      AND canonical_skill_source = true
    ORDER BY calculated_at DESC
    LIMIT 1
  `, [strategyId])

  // Query forecast metrics for Brier/calibration
  // Note: Using 'MODEL' scope for strategy metrics
  const forecastMetrics = await queryOne<{
    brier_score_mean: number | null
    calibration_error: number | null
    hit_rate_confidence_low: number | null
    hit_rate_confidence_high: number | null
    forecast_count: number
    resolved_count: number
  }>(`
    SELECT
      brier_score_mean::float,
      calibration_error::float,
      hit_rate_confidence_low::float,
      hit_rate_confidence_high::float,
      forecast_count,
      resolved_count
    FROM fhq_research.forecast_skill_metrics
    WHERE metric_scope = 'MODEL'
      AND scope_value = $1
    ORDER BY computed_at DESC
    LIMIT 1
  `, [strategyId])

  // Compute FSS (FjordHQ Skill Score) - composite of Sharpe + Win Rate
  const fss = metrics?.sharpe_ratio && metrics?.win_rate
    ? (metrics.sharpe_ratio * 0.6 + metrics.win_rate * 0.4)
    : null

  // Compute CI width
  const ciWidth = forecastMetrics?.hit_rate_confidence_low && forecastMetrics?.hit_rate_confidence_high
    ? forecastMetrics.hit_rate_confidence_high - forecastMetrics.hit_rate_confidence_low
    : null

  // Sample size
  const sampleSize = metrics?.total_trades || forecastMetrics?.resolved_count || 0

  // Status determination
  let status: 'NOT_ENOUGH_DATA' | 'EMERGING' | 'SIGNIFICANT' = 'NOT_ENOUGH_DATA'
  if (sampleSize >= MIN_SAMPLE_SIZE && ciWidth !== null && ciWidth < 0.2) {
    status = 'SIGNIFICANT'
  } else if (sampleSize >= 10) {
    status = 'EMERGING'
  }

  const statusColors = {
    NOT_ENOUGH_DATA: { bg: 'hsl(var(--muted))', text: 'hsl(var(--muted-foreground))' },
    EMERGING: { bg: 'hsl(45 93% 47% / 0.2)', text: 'hsl(45 93% 47%)' },
    SIGNIFICANT: { bg: 'hsl(142 76% 36% / 0.2)', text: 'hsl(142 76% 36%)' },
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{label}</CardTitle>
          <span
            className="px-2 py-0.5 text-xs font-medium rounded-full"
            style={{
              backgroundColor: statusColors[status].bg,
              color: statusColors[status].text,
            }}
          >
            {status.replace(/_/g, ' ')}
          </span>
        </div>
        <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          {timeframe} Timeframe
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* FSS */}
        <div className="flex items-center justify-between">
          <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>FSS</span>
          <span className="font-mono font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
            {fss !== null ? fss.toFixed(3) : '—'}
          </span>
        </div>

        {/* CI Width */}
        <div className="flex items-center justify-between">
          <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>95% CI Width</span>
          <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>
            {ciWidth !== null ? ciWidth.toFixed(3) : '—'}
          </span>
        </div>

        {/* Brier Score */}
        <div className="flex items-center justify-between">
          <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>Brier Score</span>
          <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>
            {forecastMetrics?.brier_score_mean != null ? forecastMetrics.brier_score_mean.toFixed(3) : '—'}
          </span>
        </div>

        {/* Sample Size */}
        <div className="flex items-center justify-between">
          <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>Sample Size</span>
          <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>
            {sampleSize} / {MIN_SAMPLE_SIZE}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Governance Tile Component
// ============================================================================

async function GovernanceTile() {
  // TTL Compliance: count expired vs attempted DecisionPlans
  const ttlMetrics = await queryOne<{
    total_plans: number
    expired_count: number
  }>(`
    SELECT
      COUNT(*) as total_plans,
      COUNT(*) FILTER (WHERE valid_until < NOW()) as expired_count
    FROM fhq_governance.decision_log
    WHERE decision_type LIKE 'G2C%'
      AND created_at > NOW() - INTERVAL '24 hours'
  `)

  const ttlComplianceRate = ttlMetrics && ttlMetrics.total_plans > 0
    ? ((ttlMetrics.total_plans - ttlMetrics.expired_count) / ttlMetrics.total_plans) * 100
    : 100

  let ttlBadge: 'GREEN' | 'YELLOW' | 'RED' = 'GREEN'
  if (ttlComplianceRate < 98) ttlBadge = 'RED'
  else if (ttlComplianceRate < 99.5) ttlBadge = 'YELLOW'

  // LLM Budget
  const llmMetrics = await queryOne<{
    spend_today: number
  }>(`
    SELECT COALESCE(SUM(total_cost_usd), 0)::float as spend_today
    FROM fhq_governance.telemetry_cost_ledger
    WHERE ledger_date = CURRENT_DATE
  `)

  const llmSpendToday = llmMetrics?.spend_today || 0
  const llmBudgetDaily = 5.00 // ADR-012 G2-C constraint

  let llmBadge: 'GREEN' | 'YELLOW' | 'RED' = 'GREEN'
  if (llmSpendToday >= llmBudgetDaily * 0.9) llmBadge = 'RED'
  else if (llmSpendToday >= llmBudgetDaily * 0.7) llmBadge = 'YELLOW'

  // Fortress Streak
  const lastFailure = await queryOne<{
    detected_at: string
  }>(`
    SELECT detected_at::text
    FROM fhq_execution.g2c_failure_events
    WHERE failure_type IN ('HALT_TRIGGER', 'CIRCUIT_BREAKER', 'RISK_BREACH')
    ORDER BY detected_at DESC
    LIMIT 1
  `)

  let fortressStreakDays = 0
  if (!lastFailure?.detected_at) {
    // No failures ever - count from first G2C decision
    const firstDecision = await queryOne<{ created_at: string }>(`
      SELECT MIN(created_at)::text as created_at
      FROM fhq_governance.decision_log
      WHERE decision_type LIKE 'G2C%'
    `)
    if (firstDecision?.created_at) {
      const daysSinceStart = Math.floor((Date.now() - new Date(firstDecision.created_at).getTime()) / (1000 * 60 * 60 * 24))
      fortressStreakDays = daysSinceStart
    }
  } else {
    const daysSinceFailure = Math.floor((Date.now() - new Date(lastFailure.detected_at).getTime()) / (1000 * 60 * 60 * 24))
    fortressStreakDays = daysSinceFailure
  }

  let fortressBadge: 'GREEN' | 'YELLOW' | 'RED' = 'GREEN'
  if (fortressStreakDays <= 1) fortressBadge = 'RED'
  else if (fortressStreakDays < 7) fortressBadge = 'YELLOW'

  const badgeColors = {
    GREEN: { bg: 'hsl(142 76% 36% / 0.2)', text: 'hsl(142 76% 36%)', icon: CheckCircle },
    YELLOW: { bg: 'hsl(45 93% 47% / 0.2)', text: 'hsl(45 93% 47%)', icon: AlertTriangle },
    RED: { bg: 'hsl(0 84% 60% / 0.2)', text: 'hsl(0 84% 60%)', icon: XCircle },
  }

  return (
    <Card className="border-2 border-primary/30">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            GOVERNANCE
          </CardTitle>
        </div>
        <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Scorecard Badges
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* The Architect - TTL Compliance */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Timer className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground))' }} />
            <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>Architect</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">{ttlComplianceRate.toFixed(1)}%</span>
            {(() => {
              const BadgeIcon = badgeColors[ttlBadge].icon
              return <BadgeIcon className="w-4 h-4" style={{ color: badgeColors[ttlBadge].text }} />
            })()}
          </div>
        </div>

        {/* The Gatekeeper - LLM Budget */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground))' }} />
            <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>Gatekeeper</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">${llmSpendToday.toFixed(2)}/${llmBudgetDaily}</span>
            {(() => {
              const BadgeIcon = badgeColors[llmBadge].icon
              return <BadgeIcon className="w-4 h-4" style={{ color: badgeColors[llmBadge].text }} />
            })()}
          </div>
        </div>

        {/* The Fortress - Zero-Anomaly Streak */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground))' }} />
            <span className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>Fortress</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">{fortressStreakDays}d streak</span>
            {(() => {
              const BadgeIcon = badgeColors[fortressBadge].icon
              return <BadgeIcon className="w-4 h-4" style={{ color: badgeColors[fortressBadge].text }} />
            })()}
          </div>
        </div>

        {/* 7-day target marker */}
        {fortressStreakDays >= 7 && (
          <div className="mt-2 pt-2 border-t flex items-center gap-2" style={{ borderColor: 'hsl(var(--border))' }}>
            <Award className="w-4 h-4" style={{ color: 'hsl(142 76% 36%)' }} />
            <span className="text-xs font-medium" style={{ color: 'hsl(142 76% 36%)' }}>
              7-Day Fortress Achieved
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Leaderboard Panel Component
// ============================================================================

async function LeaderboardPanel({
  title,
  subtitle,
  icon: Icon,
  metricName,
  lowerIsBetter = false,
}: {
  title: string
  subtitle: string
  icon: any
  metricName: string
  lowerIsBetter?: boolean
}) {
  // Query all strategies with their metrics
  const strategies = await queryMany<{
    strategy_id: string
    sharpe_ratio: number | null
    win_rate: number | null
    total_trades: number
  }>(`
    SELECT
      strategy_id,
      sharpe_ratio::float,
      win_rate::float,
      total_trades
    FROM fhq_execution.g2c_skill_metrics
    WHERE canonical_skill_source = true
    ORDER BY strategy_id
  `)

  // If no data, show placeholder
  if (!strategies.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Icon className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
            {title}
          </CardTitle>
          <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{subtitle}</p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-8" style={{ color: 'hsl(var(--muted-foreground))' }}>
            <AlertTriangle className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm">Insufficient Data</p>
            <p className="text-xs mt-1">Awaiting skill evaluations</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Compute FSS for each strategy and sort
  const rankedStrategies = strategies
    .map((s) => ({
      strategy_id: s.strategy_id,
      fss: s.sharpe_ratio && s.win_rate ? s.sharpe_ratio * 0.6 + s.win_rate * 0.4 : null,
      sample_size: s.total_trades,
    }))
    .filter((s) => s.fss !== null && s.sample_size >= MIN_SAMPLE_SIZE)
    .sort((a, b) => lowerIsBetter ? (a.fss! - b.fss!) : (b.fss! - a.fss!))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Icon className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          {title}
        </CardTitle>
        <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{subtitle}</p>
      </CardHeader>
      <CardContent>
        {rankedStrategies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8" style={{ color: 'hsl(var(--muted-foreground))' }}>
            <AlertTriangle className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm">No Qualified Strategies</p>
            <p className="text-xs mt-1">Min sample: {MIN_SAMPLE_SIZE}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {rankedStrategies.map((s, idx) => (
              <div
                key={s.strategy_id}
                className="flex items-center justify-between p-2 rounded-lg"
                style={{ backgroundColor: idx === 0 ? 'hsl(var(--primary) / 0.1)' : 'transparent' }}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="w-6 h-6 flex items-center justify-center rounded-full text-sm font-bold"
                    style={{
                      backgroundColor: idx === 0 ? 'hsl(var(--primary))' : 'hsl(var(--muted))',
                      color: idx === 0 ? 'white' : 'hsl(var(--muted-foreground))',
                    }}
                  >
                    {idx + 1}
                  </span>
                  <span className="font-medium">{s.strategy_id.replace('STRAT_', '').replace('_V1', '')}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="font-mono text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    n={s.sample_size}
                  </span>
                  <span className="font-mono font-semibold">{s.fss!.toFixed(3)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Calibration Chart Component
// ============================================================================

async function CalibrationChart({ strategyId, label }: { strategyId: string; label: string }) {
  // Query reliability diagram data (using MODEL scope for strategies)
  const metrics = await queryOne<{
    reliability_diagram: any
    resolved_count: number
    calibration_error: number | null
  }>(`
    SELECT
      reliability_diagram,
      resolved_count,
      calibration_error::float
    FROM fhq_research.forecast_skill_metrics
    WHERE metric_scope = 'MODEL'
      AND scope_value = $1
    ORDER BY computed_at DESC
    LIMIT 1
  `, [strategyId])

  const hasData = metrics && metrics.resolved_count && metrics.resolved_count >= 10 && metrics.reliability_diagram
  const calibrationError = metrics?.calibration_error

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-medium">{label}</span>
        {calibrationError !== null && calibrationError !== undefined && (
          <span className="text-xs font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>
            CE: {calibrationError.toFixed(3)}
          </span>
        )}
      </div>
      <div
        className="h-32 rounded-lg flex items-center justify-center"
        style={{ backgroundColor: 'hsl(var(--muted) / 0.3)' }}
      >
        {hasData ? (
          <CalibrationCurveVisual data={metrics.reliability_diagram} />
        ) : (
          <div className="text-center" style={{ color: 'hsl(var(--muted-foreground))' }}>
            <Activity className="w-6 h-6 mx-auto mb-1 opacity-50" />
            <p className="text-xs">Insufficient Data</p>
            <p className="text-xs opacity-70">n={metrics?.resolved_count || 0}/{MIN_SAMPLE_SIZE}</p>
          </div>
        )}
      </div>
    </div>
  )
}

// Simple SVG calibration curve visualization
function CalibrationCurveVisual({ data }: { data: any }) {
  // If data is available, render a simple calibration curve
  // For now, show placeholder indicating data exists
  if (!data || !data.buckets) {
    return (
      <div className="text-center" style={{ color: 'hsl(var(--muted-foreground))' }}>
        <p className="text-xs">Calibration data available</p>
        <p className="text-xs opacity-70">Visual coming soon</p>
      </div>
    )
  }

  // Simple bucket visualization
  const buckets = data.buckets as { predicted: number; actual: number; count: number }[]

  return (
    <svg viewBox="0 0 100 100" className="w-full h-full p-2">
      {/* Perfect calibration line */}
      <line x1="10" y1="90" x2="90" y2="10" stroke="hsl(var(--muted-foreground))" strokeWidth="1" strokeDasharray="2,2" />

      {/* Actual calibration points */}
      {buckets.map((bucket, idx) => {
        const x = 10 + bucket.predicted * 80
        const y = 90 - bucket.actual * 80
        const radius = Math.min(Math.max(bucket.count / 10, 2), 6)
        return (
          <circle
            key={idx}
            cx={x}
            cy={y}
            r={radius}
            fill="hsl(var(--primary))"
            opacity={0.8}
          />
        )
      })}
    </svg>
  )
}

// ============================================================================
// Data Provenance Footer
// ============================================================================

async function DataProvenanceFooter() {
  const now = new Date().toISOString()

  return (
    <div
      className="text-xs p-4 rounded-lg space-y-1"
      style={{ backgroundColor: 'hsl(var(--muted) / 0.3)', color: 'hsl(var(--muted-foreground))' }}
    >
      <p className="font-semibold">Data Provenance</p>
      <div className="grid grid-cols-2 gap-x-8 gap-y-1">
        <p>Skill Metrics: <code>fhq_execution.g2c_skill_metrics</code></p>
        <p>Forecast Metrics: <code>fhq_research.forecast_skill_metrics</code></p>
        <p>Decision Log: <code>fhq_governance.decision_log</code></p>
        <p>Failure Events: <code>fhq_execution.g2c_failure_events</code></p>
        <p>Cost Ledger: <code>fhq_governance.telemetry_cost_ledger</code></p>
        <p>Last Updated: <code>{now}</code></p>
      </div>
      <p className="mt-2 opacity-70">
        Directive: CD-G2-C-DASH-SKILL-SCORECARD-2025-12-13 | Min Sample Size: {MIN_SAMPLE_SIZE} (fixed)
      </p>
    </div>
  )
}
