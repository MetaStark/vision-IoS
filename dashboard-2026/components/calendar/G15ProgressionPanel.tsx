/**
 * G1.5 Progression Panel - CEO-VEDTAK-2026-ALPHA-FACTORY
 *
 * Visual progression tracking for Pre-Tier Gradient G1.5 Experiment.
 * CEO must understand experiment state in <10 seconds.
 *
 * Key Metrics:
 * 1. Death Progress (primary trigger: n=30)
 * 2. Throughput Status (daily rate, generators)
 * 3. Spearman Correlation Readiness
 * 4. Validator Pool Status
 * 5. Freeze Compliance
 */

'use client'

import {
  FlaskConical,
  Target,
  TrendingUp,
  TrendingDown,
  Clock,
  Users,
  Shield,
  Skull,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Database,
  Activity,
  Lock,
  Zap,
  BarChart3,
} from 'lucide-react'

interface G15Experiment {
  experimentId: string
  experimentStatus: string
  startTs: string
  endTs: string
  daysElapsed: number
  daysRemaining: number
  todayHypotheses: number
  todayGenerators: number
  todayAvgDepth: number
  totalHypotheses: number
  avgDailyRate: number
  avgDailyGenerators: number
  totalUniqueGenerators?: number
  avgCausalDepth: number
  baselineRate: number
  targetRate: number
  rateStatus: string
  targetGenerators: number
  generatorStatus: string
  deathsWithScore: number
  targetDeaths: number
  deathProgressPct: number
  calibrationTriggerMet: boolean
  endTriggerStatus: string
  weightsFrozen: boolean
  thresholdsFrozen: boolean
  agentRolesFrozen: boolean
  oxygenCriteriaFrozen: boolean
  activeValidators: number
  targetValidators: number
  validatorCapacityStatus: string
  spearman: {
    sampleSize: number
    rho: number | null
    dataStatus: string
    interpretation: string
  }
  staleCandidates: {
    fresh: number
    warning: number
    stale: number
  }
  computedAt: string
}

interface G15Generator {
  generatorId: string
  totalHypotheses: number
  last24h: number
  last7d: number
  avgDepth: number
  avgBirthScore: number | null
  deaths: number
  activeDrafts: number
  lastHypothesisAt: string | null
  volumeSharePct: number
}

interface G15Quartile {
  quartile: number
  label: string
  totalHypotheses: number
  deaths: number
  survivors: number
  avgBirthScore: number
  avgSurvivalHours: number | null
}

interface G15Validator {
  ec: string
  name: string
  role: string
  wave: string
  isActive: boolean
  totalValidations: number
}

interface G15ProgressionPanelProps {
  experiment: G15Experiment | null
  generators: G15Generator[]
  quartiles: G15Quartile[]
  validators: G15Validator[]
}

function StatusBadge({ status, size = 'sm' }: { status: string; size?: 'sm' | 'lg' }) {
  const config: Record<string, { bg: string; text: string; label: string }> = {
    ACTIVE: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'ACTIVE' },
    BELOW_TARGET: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'BELOW TARGET' },
    ON_TARGET: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'ON TARGET' },
    APPROACHING: { bg: 'bg-cyan-500/20', text: 'text-cyan-400', label: 'APPROACHING' },
    SUFFICIENT: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'SUFFICIENT' },
    ADEQUATE: { bg: 'bg-cyan-500/20', text: 'text-cyan-400', label: 'ADEQUATE' },
    LIMITED: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'LIMITED' },
    IN_PROGRESS: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'IN PROGRESS' },
    DEATH_TRIGGER: { bg: 'bg-purple-500/20', text: 'text-purple-400', label: 'DEATH TRIGGER' },
    TIME_TRIGGER: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'TIME TRIGGER' },
    INSUFFICIENT_DATA: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'INSUFFICIENT DATA' },
  }

  const c = config[status] || { bg: 'bg-gray-500/20', text: 'text-gray-400', label: status }
  const sizeClass = size === 'lg' ? 'px-3 py-1.5 text-sm' : 'px-2 py-1 text-xs'

  return (
    <span className={`${sizeClass} ${c.bg} ${c.text} rounded font-semibold`}>
      {c.label}
    </span>
  )
}

function DeathProgressGauge({ current, target }: { current: number; target: number }) {
  const pct = Math.min(100, Math.round((current / target) * 100))
  const isComplete = current >= target

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Skull className="h-5 w-5 text-red-400" />
          <span className="text-sm font-medium text-white">Death Progress (Primary Trigger)</span>
        </div>
        <span className={`text-2xl font-bold ${isComplete ? 'text-green-400' : 'text-red-400'}`}>
          {current}/{target}
        </span>
      </div>

      <div className="relative h-6 bg-gray-800 rounded-lg overflow-hidden">
        {/* Progress fill */}
        <div
          className={`absolute h-full transition-all ${isComplete ? 'bg-green-500' : 'bg-red-500'}`}
          style={{ width: `${pct}%` }}
        />
        {/* Center label */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold text-white drop-shadow-lg">
            {pct}%
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-400 text-center">
        {isComplete
          ? 'Calibration trigger met. VEGA Reasoning-Delta report ready.'
          : `Need ${target - current} more scored hypothesis deaths for Spearman analysis.`}
      </p>
    </div>
  )
}

function ThroughputMeter({
  label,
  current,
  baseline,
  target,
  status,
  icon: Icon,
}: {
  label: string
  current: number
  baseline: number
  target: number
  status: string
  icon: any
}) {
  const pctOfTarget = Math.min(100, Math.round((current / target) * 100))
  const baselinePct = Math.round((baseline / target) * 100)

  return (
    <div className="bg-gray-800/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-gray-400" />
          <span className="text-sm text-gray-400">{label}</span>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="flex items-end gap-2 mb-3">
        <span className="text-3xl font-bold text-white">{current.toFixed(1)}</span>
        <span className="text-sm text-gray-500 mb-1">/ {target} target</span>
      </div>

      <div className="relative h-3 bg-gray-700 rounded-full overflow-hidden">
        {/* Baseline marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-yellow-400/50"
          style={{ left: `${baselinePct}%` }}
        />
        {/* Progress fill */}
        <div
          className={`h-full rounded-full transition-all ${
            status === 'ON_TARGET' ? 'bg-green-500' :
            status === 'APPROACHING' ? 'bg-cyan-500' : 'bg-yellow-500'
          }`}
          style={{ width: `${pctOfTarget}%` }}
        />
      </div>

      <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
        <span>0</span>
        <span className="text-yellow-400/70">Baseline: {baseline}</span>
        <span>Target: {target}</span>
      </div>
    </div>
  )
}

function FreezeComplianceGrid({
  weights,
  thresholds,
  agentRoles,
  oxygen,
}: {
  weights: boolean
  thresholds: boolean
  agentRoles: boolean
  oxygen: boolean
}) {
  const items = [
    { label: 'Weights', frozen: weights },
    { label: 'Thresholds', frozen: thresholds },
    { label: 'Agent Roles', frozen: agentRoles },
    { label: 'Oxygen', frozen: oxygen },
  ]

  const allFrozen = items.every(i => i.frozen)

  return (
    <div className="bg-gray-800/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Lock className="h-4 w-4 text-purple-400" />
          <span className="text-sm font-medium text-white">Freeze Compliance</span>
        </div>
        {allFrozen ? (
          <span className="flex items-center gap-1 text-xs text-green-400">
            <CheckCircle className="h-3 w-3" />
            ALL FROZEN
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs text-red-400">
            <AlertTriangle className="h-3 w-3" />
            VIOLATION
          </span>
        )}
      </div>

      <div className="grid grid-cols-4 gap-2">
        {items.map(item => (
          <div
            key={item.label}
            className={`text-center p-2 rounded ${
              item.frozen ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'
            }`}
          >
            {item.frozen ? (
              <CheckCircle className="h-4 w-4 text-green-400 mx-auto" />
            ) : (
              <XCircle className="h-4 w-4 text-red-400 mx-auto" />
            )}
            <p className="text-xs text-gray-400 mt-1">{item.label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function SpearmanReadiness({
  sampleSize,
  rho,
  dataStatus,
  interpretation,
}: {
  sampleSize: number
  rho: number | null
  dataStatus: string
  interpretation: string
}) {
  const requiredSamples = 30
  const pct = Math.min(100, Math.round((sampleSize / requiredSamples) * 100))

  return (
    <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/30 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-purple-400" />
          <span className="text-sm font-medium text-white">Spearman Correlation Readiness</span>
        </div>
        <StatusBadge status={dataStatus} />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-3">
        <div className="text-center">
          <p className="text-3xl font-bold text-white">{sampleSize}</p>
          <p className="text-xs text-gray-400">Samples (need 30)</p>
        </div>
        <div className="text-center">
          <p className={`text-3xl font-bold ${
            rho === null ? 'text-gray-500' :
            rho > 0.3 ? 'text-green-400' :
            rho > 0.1 ? 'text-yellow-400' : 'text-red-400'
          }`}>
            {rho !== null ? rho.toFixed(4) : 'N/A'}
          </p>
          <p className="text-xs text-gray-400">Spearman rho</p>
        </div>
      </div>

      {/* Progress bar to 30 samples */}
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden mb-3">
        <div
          className={`h-full rounded-full transition-all ${pct >= 100 ? 'bg-green-500' : 'bg-purple-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      <p className="text-sm text-gray-400">{interpretation}</p>
    </div>
  )
}

function ValidatorGrid({ validators }: { validators: G15Validator[] }) {
  const originalCount = validators.filter(v => v.wave === 'ORIGINAL').length
  const expansionCount = validators.filter(v => v.wave === 'G1.5_EXPANSION').length

  return (
    <div className="bg-gray-800/50 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-cyan-400" />
          <span className="text-sm font-medium text-white">Validator Pool</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">{validators.length} active</span>
          <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">SUFFICIENT</span>
        </div>
      </div>

      <div className="space-y-2">
        {validators.map(v => (
          <div
            key={v.ec}
            className={`flex items-center justify-between p-2 rounded ${
              v.wave === 'ORIGINAL' ? 'bg-gray-700/50' : 'bg-cyan-500/10 border border-cyan-500/30'
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`text-sm font-mono ${v.wave === 'G1.5_EXPANSION' ? 'text-cyan-400' : 'text-white'}`}>
                {v.ec}
              </span>
              {v.wave === 'G1.5_EXPANSION' && (
                <span className="text-xs bg-cyan-500/20 text-cyan-400 px-1.5 py-0.5 rounded">NEW</span>
              )}
            </div>
            <span className="text-xs text-gray-500">{v.totalValidations} validations</span>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-700/50 text-xs">
        <span className="text-gray-500">Original: {originalCount}</span>
        <span className="text-cyan-400">G1.5 Expansion: +{expansionCount}</span>
      </div>
    </div>
  )
}

export function G15ProgressionPanel({
  experiment,
  generators,
  quartiles,
  validators,
}: G15ProgressionPanelProps) {
  if (!experiment) {
    return (
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <FlaskConical className="h-5 w-5 text-purple-400" />
          <h3 className="text-lg font-semibold text-white">G1.5 Experiment</h3>
        </div>
        <p className="text-gray-500 text-sm">No G1.5 experiment data available.</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900/50 border border-purple-500/30 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-500/20 to-blue-500/20 px-6 py-4 border-b border-purple-500/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/20 rounded-lg">
              <FlaskConical className="h-6 w-6 text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">
                Pre-Tier Gradient G1.5: Empirical Calibration
              </h3>
              <p className="text-sm text-gray-400">
                {experiment.experimentId} | Day {experiment.daysElapsed} of 14
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={experiment.experimentStatus} size="lg" />
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Database className="h-3 w-3" />
              <span>Verified: {new Date(experiment.computedAt).toLocaleTimeString()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-6 space-y-6">
        {/* Death Progress - Primary Metric */}
        <DeathProgressGauge
          current={experiment.deathsWithScore}
          target={experiment.targetDeaths}
        />

        {/* Throughput Meters */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ThroughputMeter
            label="Daily Hypothesis Rate"
            current={experiment.avgDailyRate}
            baseline={experiment.baselineRate}
            target={experiment.targetRate}
            status={experiment.rateStatus}
            icon={TrendingUp}
          />
          <ThroughputMeter
            label="Generator Diversity"
            current={experiment.totalUniqueGenerators || experiment.avgDailyGenerators}
            baseline={2}
            target={experiment.targetGenerators}
            status={experiment.generatorStatus}
            icon={Zap}
          />
        </div>

        {/* Spearman Correlation Readiness */}
        <SpearmanReadiness
          sampleSize={experiment.spearman.sampleSize}
          rho={experiment.spearman.rho}
          dataStatus={experiment.spearman.dataStatus}
          interpretation={experiment.spearman.interpretation}
        />

        {/* Two Column: Freeze Compliance + Validators */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FreezeComplianceGrid
            weights={experiment.weightsFrozen}
            thresholds={experiment.thresholdsFrozen}
            agentRoles={experiment.agentRolesFrozen}
            oxygen={experiment.oxygenCriteriaFrozen}
          />
          <ValidatorGrid validators={validators} />
        </div>

        {/* Generator Performance (if any) */}
        {generators.length > 0 && (
          <div className="bg-gray-800/50 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="h-4 w-4 text-green-400" />
              <span className="text-sm font-medium text-white">Generator Performance (Since G1.5 Start)</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-700">
                    <th className="pb-2">Generator</th>
                    <th className="pb-2 text-right">Total</th>
                    <th className="pb-2 text-right">24h</th>
                    <th className="pb-2 text-right">Deaths</th>
                    <th className="pb-2 text-right">Avg Score</th>
                    <th className="pb-2 text-right">Share</th>
                  </tr>
                </thead>
                <tbody>
                  {generators.map(g => (
                    <tr key={g.generatorId} className="border-b border-gray-700/50">
                      <td className="py-2 font-mono text-white">{g.generatorId}</td>
                      <td className="py-2 text-right text-white">{g.totalHypotheses}</td>
                      <td className="py-2 text-right text-cyan-400">{g.last24h}</td>
                      <td className="py-2 text-right text-red-400">{g.deaths}</td>
                      <td className="py-2 text-right text-purple-400">
                        {g.avgBirthScore ? g.avgBirthScore.toFixed(1) : 'N/A'}
                      </td>
                      <td className="py-2 text-right text-gray-400">{g.volumeSharePct.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Stale Candidates Alert */}
        {(experiment.staleCandidates.warning > 0 || experiment.staleCandidates.stale > 0) && (
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-400" />
              <span className="text-sm font-medium text-yellow-400">Stale Hypothesis Alert</span>
            </div>
            <p className="text-sm text-gray-400 mt-2">
              {experiment.staleCandidates.warning} hypotheses approaching stale threshold (36-48h).
              {experiment.staleCandidates.stale > 0 && ` ${experiment.staleCandidates.stale} candidates for STALE marking.`}
            </p>
          </div>
        )}

        {/* Timeline Footer */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-700/50 text-sm">
          <div className="flex items-center gap-2 text-gray-400">
            <Clock className="h-4 w-4" />
            <span>Started: {new Date(experiment.startTs).toLocaleDateString()}</span>
          </div>
          <div className="flex items-center gap-2 text-gray-400">
            <Target className="h-4 w-4" />
            <span>End: {new Date(experiment.endTs).toLocaleDateString()} ({experiment.daysRemaining}d remaining)</span>
          </div>
        </div>
      </div>
    </div>
  )
}
