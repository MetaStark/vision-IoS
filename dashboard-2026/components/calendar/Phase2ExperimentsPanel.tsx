/**
 * Phase 2 Alpha Satellite Experiments Panel
 * CEO-DIR-2026-CALENDAR-IS-LAW: All running experiments visible in calendar
 *
 * Status colors:
 *   grey   = OBSERVING (no triggers yet)
 *   blue   = MEASURING (has triggers, collecting outcomes)
 *   green  = PROMOTED  (candidate_promotion flagged)
 *   red    = CLOSED    (falsified or stopped)
 */

'use client'

import { Beaker, Clock, TrendingUp, Eye, CheckCircle, XCircle, Activity } from 'lucide-react'

interface Phase2Experiment {
  experimentCode: string
  hypothesisCode: string
  calendarStatus: 'OBSERVING' | 'MEASURING' | 'PROMOTED' | 'CLOSED'
  startTime: string
  expectedEndTime: string
  endTime: string | null
  timeframeHours: number
  triggerCount: number
  outcomeCount: number
  winRatePct: number
  experimentStatus: string
  candidatePromotion: boolean
}

interface Phase2ExperimentsPanelProps {
  experiments: Phase2Experiment[]
}

const STATUS_CONFIG: Record<string, { color: string; bg: string; border: string; icon: any; label: string }> = {
  OBSERVING: {
    color: 'text-gray-400',
    bg: 'bg-gray-500/10',
    border: 'border-gray-500/30',
    icon: Eye,
    label: 'Observing',
  },
  MEASURING: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    icon: Activity,
    label: 'Measuring',
  },
  PROMOTED: {
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    icon: CheckCircle,
    label: 'Promotable',
  },
  CLOSED: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    icon: XCircle,
    label: 'Closed',
  },
}

const TEST_LABELS: Record<string, string> = {
  'EXP_ALPHA_SAT_A_V1.1': 'A: Vol Squeeze',
  'EXP_ALPHA_SAT_B_V1.1': 'B: Regime Align',
  'EXP_ALPHA_SAT_C_V1.1': 'C: Mean Revert',
  'EXP_ALPHA_SAT_D_V1.0': 'D: Breakout',
  'EXP_ALPHA_SAT_E_V1.0': 'E: Trend Pullback',
  'EXP_ALPHA_SAT_F_V1.0': 'F: Panic Bottom',
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleDateString('no-NO', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ts
  }
}

export function Phase2ExperimentsPanel({ experiments }: Phase2ExperimentsPanelProps) {
  if (!experiments || experiments.length === 0) return null

  const measuring = experiments.filter(e => e.calendarStatus === 'MEASURING').length
  const promoted = experiments.filter(e => e.calendarStatus === 'PROMOTED').length
  const totalTriggers = experiments.reduce((s, e) => s + e.triggerCount, 0)
  const totalOutcomes = experiments.reduce((s, e) => s + e.outcomeCount, 0)

  return (
    <div className="rounded-lg border border-cyan-500/20 bg-gray-900/50 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Beaker className="h-4 w-4 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white">Phase 2 Alpha Satellite</h3>
          <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            {experiments.length} tests
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>{totalTriggers} triggers</span>
          <span>{totalOutcomes} outcomes</span>
          {measuring > 0 && <span className="text-blue-400">{measuring} measuring</span>}
          {promoted > 0 && <span className="text-emerald-400">{promoted} promotable</span>}
        </div>
      </div>

      {/* Experiment blocks */}
      <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
        {experiments.map((exp) => {
          const config = STATUS_CONFIG[exp.calendarStatus] || STATUS_CONFIG.OBSERVING
          const Icon = config.icon
          const label = TEST_LABELS[exp.experimentCode] || exp.experimentCode

          return (
            <div
              key={exp.experimentCode}
              className={`rounded-md border ${config.border} ${config.bg} p-3`}
            >
              {/* Test name + status */}
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-white">{label}</span>
                <span className={`flex items-center gap-1 text-xs ${config.color}`}>
                  <Icon className="h-3 w-3" />
                  {config.label}
                </span>
              </div>

              {/* Time block */}
              <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
                <Clock className="h-3 w-3" />
                <span>{formatTime(exp.startTime)}</span>
                <span className="text-gray-600">-</span>
                <span>{exp.endTime ? formatTime(exp.endTime) : formatTime(exp.expectedEndTime)}</span>
                <span className="text-gray-600">({exp.timeframeHours}h)</span>
              </div>

              {/* Metrics row */}
              <div className="flex items-center gap-3 text-xs">
                <span className="text-gray-400">
                  {exp.triggerCount} trig
                </span>
                <span className="text-gray-400">
                  {exp.outcomeCount} out
                </span>
                {exp.outcomeCount > 0 && (
                  <span className={exp.winRatePct >= 45 ? 'text-emerald-400' : 'text-gray-400'}>
                    <TrendingUp className="h-3 w-3 inline mr-0.5" />
                    {exp.winRatePct}%
                  </span>
                )}
                {exp.candidatePromotion && (
                  <span className="text-emerald-400 font-medium">CANDIDATE</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
