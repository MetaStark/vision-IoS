'use client'

/**
 * Four-Plane Learning Dashboard
 * CEO-DIR-2026-DAY25-LEARNING-VISIBILITY-002
 *
 * Mandatory separation of learning state into four visual planes:
 * - PLANE 1: LEARNING PERMISSION (Can the system learn?)
 * - PLANE 2: LEARNING ENGINE STATUS (Is the engine running?)
 * - PLANE 3: LEARNING QUALITY (Are hypotheses surviving?)
 * - PLANE 4: LEARNING PRODUCTION (What is being generated?)
 *
 * Key terminology corrections:
 * - "Learning Paused" ONLY when scheduler STOPPED or DEFCON blocks
 * - "Learning Active - No Survivors" when hypotheses die correctly
 * - "Engine Running - Output Rejected" when generation too weak
 */

import { Shield, Cpu, Target, BarChart3, AlertTriangle, CheckCircle, XCircle, Clock, Zap } from 'lucide-react'

export interface LearningPermissionData {
  permitted: boolean
  assetClasses: {
    crypto: { permitted: boolean; learningOnly: boolean }
    equity: { permitted: boolean; learningOnly: boolean }
    forex: { permitted: boolean; learningOnly: boolean }
  }
  constraints: {
    allocationAllowed: boolean
    executionAllowed: boolean
    decisionRights: boolean
  }
  defconStatus: string
  blockingReasons: string[]
}

export interface LearningEngineData {
  schedulerRunning: boolean
  lastCycleTimestamp: string | null
  nextCycleTimestamp: string | null
  cycleIntervalMinutes: number
  hypothesesThisCycle: number
  engineStatus: 'RUNNING' | 'STOPPED' | 'PAUSED' | 'BLOCKED'
  pauseReason: string | null
}

export interface LearningQualityData {
  tier1DeathRate: number
  targetDeathRateMin: number
  targetDeathRateMax: number
  totalEvaluated: number
  totalDead: number
  totalAlive: number
  qualityStatus: 'ON_TARGET' | 'TOO_BRUTAL' | 'TOO_LENIENT' | 'NO_DATA'
  interpretation: string
}

export interface LearningProductionData {
  finnE: { count: number; pct: number }
  finnT: { count: number; pct: number }
  gnS: { count: number; pct: number }
  avgCausalDepth: number
  targetCausalDepth: number
  hypothesesToday: number
  hypotheses7d: number
  dominantGenerator: string | null
  monocultureRisk: boolean
}

interface Props {
  permission: LearningPermissionData | null
  engine: LearningEngineData | null
  quality: LearningQualityData | null
  production: LearningProductionData | null
}

function PlaneHeader({ number, title, icon: Icon, color }: { number: number; title: string; icon: any; color: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className={`flex items-center justify-center w-8 h-8 rounded-full ${color} bg-opacity-20`}>
        <Icon className={`h-4 w-4 ${color.replace('bg-', 'text-')}`} />
      </div>
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-wider">Plane {number}</div>
        <div className="text-sm font-semibold text-white">{title}</div>
      </div>
    </div>
  )
}

function Plane1Permission({ data }: { data: LearningPermissionData | null }) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 animate-pulse">
        <PlaneHeader number={1} title="LEARNING PERMISSION" icon={Shield} color="bg-blue-500" />
        <div className="h-20 bg-gray-800 rounded" />
      </div>
    )
  }

  const statusColor = data.permitted
    ? 'text-green-400 bg-green-500/10 border-green-500/30'
    : 'text-red-400 bg-red-500/10 border-red-500/30'

  const statusIcon = data.permitted ? <CheckCircle className="h-5 w-5" /> : <XCircle className="h-5 w-5" />

  // Determine which asset classes are learning
  const learningClasses = []
  if (data.assetClasses.crypto.permitted) learningClasses.push('CRYPTO')
  if (data.assetClasses.equity.permitted) learningClasses.push('EQUITY')
  if (data.assetClasses.forex.permitted) learningClasses.push('FOREX')

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <PlaneHeader number={1} title="LEARNING PERMISSION" icon={Shield} color="bg-blue-500" />

      {/* Main Status */}
      <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${statusColor} mb-4`}>
        {statusIcon}
        <div>
          <div className="font-semibold">
            LEARNING PERMISSION: {data.permitted ? 'ACTIVE' : 'BLOCKED'}
            {learningClasses.length > 0 && data.permitted && (
              <span className="text-gray-400 font-normal ml-2">({learningClasses.join(', ')} ONLY)</span>
            )}
          </div>
          {!data.permitted && data.blockingReasons.length > 0 && (
            <div className="text-xs mt-1 opacity-80">Reason: {data.blockingReasons[0]}</div>
          )}
        </div>
      </div>

      {/* Constraints (always visible) */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className={`px-3 py-2 rounded ${!data.constraints.allocationAllowed ? 'bg-gray-800 text-gray-400' : 'bg-red-500/20 text-red-400'}`}>
          <div className="font-mono">allocation_allowed</div>
          <div className="font-bold">{data.constraints.allocationAllowed ? 'TRUE' : 'FALSE'}</div>
        </div>
        <div className={`px-3 py-2 rounded ${!data.constraints.executionAllowed ? 'bg-gray-800 text-gray-400' : 'bg-red-500/20 text-red-400'}`}>
          <div className="font-mono">execution_allowed</div>
          <div className="font-bold">{data.constraints.executionAllowed ? 'TRUE' : 'FALSE'}</div>
        </div>
        <div className={`px-3 py-2 rounded ${!data.constraints.decisionRights ? 'bg-gray-800 text-gray-400' : 'bg-red-500/20 text-red-400'}`}>
          <div className="font-mono">decision_rights</div>
          <div className="font-bold">{data.constraints.decisionRights ? 'TRUE' : 'FALSE'}</div>
        </div>
      </div>

      {/* DEFCON Status */}
      <div className="mt-3 text-xs text-gray-500">
        DEFCON: <span className="text-green-400">{data.defconStatus}</span>
      </div>
    </div>
  )
}

function Plane2Engine({ data }: { data: LearningEngineData | null }) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 animate-pulse">
        <PlaneHeader number={2} title="LEARNING ENGINE STATUS" icon={Cpu} color="bg-amber-500" />
        <div className="h-20 bg-gray-800 rounded" />
      </div>
    )
  }

  // Determine status color and text
  // KEY: "Learning Paused" ONLY if scheduler STOPPED or DEFCON blocks
  let statusColor: string
  let statusText: string
  let statusIcon: JSX.Element

  if (data.engineStatus === 'STOPPED' || data.engineStatus === 'BLOCKED') {
    statusColor = 'text-red-400 bg-red-500/10 border-red-500/30'
    statusText = data.engineStatus === 'BLOCKED' ? 'BLOCKED' : 'STOPPED'
    statusIcon = <XCircle className="h-5 w-5" />
  } else if (data.engineStatus === 'PAUSED') {
    statusColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30'
    statusText = 'PAUSED'
    statusIcon = <AlertTriangle className="h-5 w-5" />
  } else {
    // RUNNING - but may have no output
    if (data.hypothesesThisCycle === 0) {
      statusColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30'
      statusText = 'RUNNING - NO OUTPUT THIS CYCLE'
      statusIcon = <Zap className="h-5 w-5" />
    } else {
      statusColor = 'text-green-400 bg-green-500/10 border-green-500/30'
      statusText = `RUNNING - ${data.hypothesesThisCycle} GENERATED`
      statusIcon = <CheckCircle className="h-5 w-5" />
    }
  }

  const formatTimestamp = (ts: string | null) => {
    if (!ts) return 'N/A'
    try {
      return new Date(ts).toLocaleString()
    } catch {
      return ts
    }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <PlaneHeader number={2} title="LEARNING ENGINE STATUS" icon={Cpu} color="bg-amber-500" />

      {/* Main Status */}
      <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${statusColor} mb-4`}>
        {statusIcon}
        <div>
          <div className="font-semibold">LEARNING ENGINE: {statusText}</div>
          {data.pauseReason && (
            <div className="text-xs mt-1 opacity-80">Reason: {data.pauseReason}</div>
          )}
        </div>
      </div>

      {/* Cycle Information */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-gray-500" />
          <div>
            <div className="text-xs text-gray-500">Last FINN Cycle</div>
            <div className="text-gray-300 font-mono text-xs">{formatTimestamp(data.lastCycleTimestamp)}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-gray-500" />
          <div>
            <div className="text-xs text-gray-500">Next Cycle</div>
            <div className="text-gray-300 font-mono text-xs">{formatTimestamp(data.nextCycleTimestamp)}</div>
          </div>
        </div>
      </div>

      {/* Important clarification */}
      <div className="mt-4 px-3 py-2 bg-gray-800/50 rounded text-xs text-gray-400">
        <strong className="text-gray-300">Note:</strong> "No new hypotheses" does not mean "Learning paused".
        Engine runs every {data.cycleIntervalMinutes} minutes. Output depends on market conditions and data availability.
      </div>
    </div>
  )
}

function Plane3Quality({ data }: { data: LearningQualityData | null }) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 animate-pulse">
        <PlaneHeader number={3} title="LEARNING QUALITY" icon={Target} color="bg-red-500" />
        <div className="h-20 bg-gray-800 rounded" />
      </div>
    )
  }

  // Determine status
  let statusColor: string
  let statusText: string

  switch (data.qualityStatus) {
    case 'ON_TARGET':
      statusColor = 'text-green-400 bg-green-500/10 border-green-500/30'
      statusText = 'ON TARGET'
      break
    case 'TOO_BRUTAL':
      statusColor = 'text-red-400 bg-red-500/10 border-red-500/30'
      statusText = 'TOO BRUTAL'
      break
    case 'TOO_LENIENT':
      statusColor = 'text-amber-400 bg-amber-500/10 border-amber-500/30'
      statusText = 'TOO LENIENT'
      break
    default:
      statusColor = 'text-gray-400 bg-gray-500/10 border-gray-500/30'
      statusText = 'NO DATA'
  }

  const deathRatePct = data.tier1DeathRate * 100

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <PlaneHeader number={3} title="LEARNING QUALITY" icon={Target} color="bg-red-500" />

      {/* Main Status */}
      <div className={`flex items-center gap-3 px-4 py-3 rounded-lg border ${statusColor} mb-4`}>
        <Target className="h-5 w-5" />
        <div>
          <div className="font-semibold">LEARNING QUALITY: {statusText}</div>
          <div className="text-xs mt-1 opacity-80">{data.interpretation}</div>
        </div>
      </div>

      {/* Death Rate Gauge */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-2">
          <span className="text-xs text-gray-500">Tier-1 Death Rate</span>
          <span className={`text-lg font-bold ${deathRatePct >= 60 && deathRatePct <= 90 ? 'text-green-400' : 'text-red-400'}`}>
            {deathRatePct.toFixed(1)}%
          </span>
        </div>
        {/* Visual gauge with target zone */}
        <div className="h-3 bg-gray-700 rounded-full overflow-hidden relative">
          {/* Target zone indicator */}
          <div
            className="absolute h-full bg-green-500/30"
            style={{ left: '60%', width: '30%' }}
          />
          {/* Current value */}
          <div
            className={`h-full ${deathRatePct >= 60 && deathRatePct <= 90 ? 'bg-green-500' : 'bg-red-500'}`}
            style={{ width: `${Math.min(deathRatePct, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-600 mt-1">
          <span>0%</span>
          <span className="text-green-500">Target: {data.targetDeathRateMin}-{data.targetDeathRateMax}%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="bg-gray-800/50 rounded p-2">
          <div className="text-gray-500">Evaluated</div>
          <div className="text-white font-bold">{data.totalEvaluated}</div>
        </div>
        <div className="bg-gray-800/50 rounded p-2">
          <div className="text-gray-500">Dead</div>
          <div className="text-red-400 font-bold">{data.totalDead}</div>
        </div>
        <div className="bg-gray-800/50 rounded p-2">
          <div className="text-gray-500">Alive</div>
          <div className="text-green-400 font-bold">{data.totalAlive}</div>
        </div>
      </div>

      {/* Clarification */}
      <div className="mt-4 px-3 py-2 bg-gray-800/50 rounded text-xs text-gray-400">
        <strong className="text-gray-300">Note:</strong> 0 active hypotheses can be the CORRECT state.
        High death rate = system functioning, but over-calibrated. This is "Fail-Closed Calibration State".
      </div>
    </div>
  )
}

function Plane4Production({ data }: { data: LearningProductionData | null }) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 animate-pulse">
        <PlaneHeader number={4} title="LEARNING PRODUCTION" icon={BarChart3} color="bg-purple-500" />
        <div className="h-20 bg-gray-800 rounded" />
      </div>
    )
  }

  const total = data.finnE.count + data.finnT.count + data.gnS.count
  const depthOnTarget = data.avgCausalDepth >= data.targetCausalDepth

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <PlaneHeader number={4} title="LEARNING PRODUCTION" icon={BarChart3} color="bg-purple-500" />

      {/* Generator Distribution Header */}
      <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
        LEARNING PRODUCTION (7d)
      </div>

      {/* Generator Bars */}
      <div className="space-y-2 mb-4">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-blue-400">FINN-E (Error Repair)</span>
            <span className="text-gray-400">{data.finnE.pct.toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500" style={{ width: `${data.finnE.pct}%` }} />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-purple-400">FINN-T (World-Model)</span>
            <span className="text-gray-400">{data.finnT.pct.toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-purple-500" style={{ width: `${data.finnT.pct}%` }} />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-cyan-400">GN-S (Shadow Discovery)</span>
            <span className="text-gray-400">{data.gnS.pct.toFixed(1)}%</span>
          </div>
          <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-cyan-500" style={{ width: `${data.gnS.pct}%` }} />
          </div>
        </div>
      </div>

      {/* Monoculture Warning */}
      {data.monocultureRisk && (
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-400 mb-4">
          <AlertTriangle className="h-4 w-4" />
          <span>Monoculture Risk: {data.dominantGenerator} at {Math.max(data.finnE.pct, data.finnT.pct, data.gnS.pct).toFixed(0)}% (threshold 60%)</span>
        </div>
      )}

      {/* Causal Depth + Today Stats */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="bg-gray-800/50 rounded p-3">
          <div className="text-xs text-gray-500 mb-1">Avg Causal Depth</div>
          <div className={`text-xl font-bold ${depthOnTarget ? 'text-green-400' : 'text-amber-400'}`}>
            {data.avgCausalDepth.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500">Target: {">="}{data.targetCausalDepth}</div>
        </div>
        <div className="bg-gray-800/50 rounded p-3">
          <div className="text-xs text-gray-500 mb-1">Hypotheses Today</div>
          <div className="text-xl font-bold text-white">{data.hypothesesToday}</div>
          <div className="text-xs text-gray-500">7d total: {data.hypotheses7d}</div>
        </div>
      </div>

      {/* Clarification */}
      <div className="mt-4 px-3 py-2 bg-gray-800/50 rounded text-xs text-gray-400">
        This panel is <strong className="text-gray-300">diagnostic</strong>, not normative.
        It shows HOW the system learns, not whether learning is good or bad.
      </div>
    </div>
  )
}

export function LearningFourPlanes({ permission, engine, quality, production }: Props) {
  return (
    <div className="space-y-6">
      {/* Visual Firebreak Banner */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-lg px-4 py-3 text-center">
        <div className="text-xs uppercase tracking-wider text-gray-400 font-semibold">
          THIS PANEL SHOWS LEARNING ONLY
        </div>
        <div className="text-xs text-gray-500 mt-1">
          NO SIGNALS &bull; NO DECISIONS &bull; NO ALLOCATION
        </div>
      </div>

      {/* Four Planes Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Plane1Permission data={permission} />
        <Plane2Engine data={engine} />
        <Plane3Quality data={quality} />
        <Plane4Production data={production} />
      </div>
    </div>
  )
}
