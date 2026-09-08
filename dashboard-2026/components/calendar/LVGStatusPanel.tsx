/**
 * LVG Status Panel - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Section 5.5 Correction: LVG Status in Daily Reports.
 * Monitors: Entropy Score, Thrashing Index, Governor Action.
 *
 * CEO-DIR-2026-DAY25 UPDATE: Show cumulative totals, not just daily.
 */

'use client'

import { Gauge, Brain, Activity, AlertTriangle, CheckCircle, XCircle, Pause, Play } from 'lucide-react'

interface LVGStatus {
  hypothesesBornToday: number
  hypothesesKilledToday: number
  entropyScore: number | null
  thrashingIndex: number | null
  governorAction: string
  velocityBrakeActive: boolean
  // Cumulative totals (CEO-DIR-2026-DAY25)
  totalHypotheses?: number
  totalFalsified?: number
  totalActive?: number
  deathRatePct?: number
  lastHypothesisTime?: string
  daemonStatus?: 'RUNNING' | 'STOPPED' | 'UNKNOWN'
}

interface ShadowTierStatus {
  totalSamples: number
  survivedCount: number
  survivalRate: number
  calibrationStatus: string
}

interface LVGStatusPanelProps {
  lvg: LVGStatus
  shadowTier: ShadowTierStatus
}

export function LVGStatusPanel({ lvg, shadowTier }: LVGStatusPanelProps) {
  const getGovernorColor = (action: string) => {
    switch (action) {
      case 'NORMAL':
        return 'text-green-400 bg-green-500/10'
      case 'THROTTLED':
        return 'text-yellow-400 bg-yellow-500/10'
      case 'COOLED_OFF':
        return 'text-red-400 bg-red-500/10'
      default:
        return 'text-gray-400 bg-gray-500/10'
    }
  }

  const getCalibrationColor = (status: string) => {
    if (status.includes('WARNING')) {
      return 'text-yellow-400'
    }
    return 'text-green-400'
  }

  // Determine daemon status based on last hypothesis time
  const getDaemonStatus = () => {
    if (lvg.daemonStatus) return lvg.daemonStatus
    if (!lvg.lastHypothesisTime) return 'UNKNOWN'
    const lastTime = new Date(lvg.lastHypothesisTime)
    const hoursSince = (Date.now() - lastTime.getTime()) / (1000 * 60 * 60)
    return hoursSince < 1 ? 'RUNNING' : 'STOPPED'
  }

  const daemonStatus = getDaemonStatus()

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
      {/* Daemon Status Banner */}
      {daemonStatus === 'STOPPED' && (
        <div className="mb-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <div className="flex items-center gap-2">
            <Pause className="h-4 w-4 text-yellow-400" />
            <span className="text-sm text-yellow-400 font-medium">Learning Paused</span>
          </div>
          <p className="text-xs text-yellow-400/70 mt-1">
            FINN scheduler not running. No new hypotheses being generated.
            {lvg.lastHypothesisTime && (
              <> Last activity: {new Date(lvg.lastHypothesisTime).toLocaleString()}</>
            )}
          </p>
        </div>
      )}

      <div className="flex items-center gap-2 mb-6">
        <Gauge className="h-5 w-5 text-purple-400" />
        <h3 className="text-lg font-semibold text-white">Learning Velocity Governor</h3>
        {lvg.velocityBrakeActive && (
          <span className="ml-auto px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full text-xs font-medium animate-pulse">
            BRAKE ACTIVE
          </span>
        )}
        {daemonStatus === 'RUNNING' && (
          <span className="ml-auto px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full text-xs font-medium flex items-center gap-1">
            <Play className="h-3 w-3" /> ACTIVE
          </span>
        )}
      </div>

      {/* Cumulative Totals (CEO-DIR-2026-DAY25) */}
      {(lvg.totalHypotheses !== undefined || lvg.totalFalsified !== undefined) && (
        <div className="mb-6 p-4 bg-gray-800/30 rounded-lg border border-gray-700/50">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">Cumulative Learning</p>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-2xl font-bold text-white">{lvg.totalHypotheses ?? 0}</p>
              <p className="text-xs text-gray-500">Total Tested</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-red-400">{lvg.totalFalsified ?? 0}</p>
              <p className="text-xs text-gray-500">Falsified</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-amber-400">
                {lvg.deathRatePct !== undefined ? `${lvg.deathRatePct.toFixed(0)}%` : 'N/A'}
              </p>
              <p className="text-xs text-gray-500">Death Rate</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Hypotheses Born */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="h-4 w-4 text-blue-400" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">Born Today</span>
          </div>
          <p className="text-2xl font-bold text-white">{lvg.hypothesesBornToday}</p>
        </div>

        {/* Hypotheses Killed */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="h-4 w-4 text-red-400" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">Killed Today</span>
          </div>
          <p className="text-2xl font-bold text-white">{lvg.hypothesesKilledToday}</p>
        </div>

        {/* Entropy Score */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Entropy Score</span>
          </div>
          <p className="text-lg font-mono text-white">
            {lvg.entropyScore !== null ? lvg.entropyScore.toFixed(3) : 'N/A'}
          </p>
          <p className="text-xs text-gray-500 mt-1">Low = groupthink risk</p>
        </div>

        {/* Thrashing Index */}
        <div className="bg-gray-800/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-gray-500 uppercase tracking-wider">Thrashing Index</span>
          </div>
          <p className="text-lg font-mono text-white">
            {lvg.thrashingIndex !== null ? lvg.thrashingIndex.toFixed(3) : 'N/A'}
          </p>
          <p className="text-xs text-gray-500 mt-1">High = instability</p>
        </div>
      </div>

      {/* Governor Action */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-400">Governor Action</span>
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${getGovernorColor(
              lvg.governorAction
            )}`}
          >
            {lvg.governorAction}
          </span>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all ${
              lvg.governorAction === 'NORMAL'
                ? 'bg-green-500 w-1/3'
                : lvg.governorAction === 'THROTTLED'
                ? 'bg-yellow-500 w-2/3'
                : 'bg-red-500 w-full'
            }`}
          />
        </div>
      </div>

      {/* Shadow Tier Status (Section 6.3) */}
      <div className="border-t border-gray-800 pt-4">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-sm text-gray-400">Symmetry Watch (Shadow Tier)</span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-gray-500 mb-1">Samples</p>
            <p className="text-lg font-mono text-white">
              {shadowTier.survivedCount}/{shadowTier.totalSamples}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">Survival Rate</p>
            <p className="text-lg font-mono text-white">{shadowTier.survivalRate}%</p>
          </div>
        </div>

        <div className="mt-3 flex items-center gap-2">
          {shadowTier.calibrationStatus.includes('WARNING') ? (
            <>
              <AlertTriangle className="h-4 w-4 text-yellow-400" />
              <span className="text-xs text-yellow-400">{shadowTier.calibrationStatus}</span>
            </>
          ) : (
            <>
              <CheckCircle className="h-4 w-4 text-green-400" />
              <span className="text-xs text-green-400">Calibration: {shadowTier.calibrationStatus}</span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
