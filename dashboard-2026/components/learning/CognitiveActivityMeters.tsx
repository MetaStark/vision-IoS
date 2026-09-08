/**
 * Cognitive Activity Meters - CEO-DIR-2026-057
 * Three non-financial gauges showing cognitive resource utilization
 *
 * 1. Search Activity (Serper)
 * 2. Reasoning Intensity (LLM)
 * 3. Learning Yield
 */

'use client'

import { Search, Brain, Target, TrendingUp, Globe, Zap } from 'lucide-react'

export interface SearchActivityData {
  queriesPerDay: number
  domainsCovered: string[]
  trend: 'up' | 'down' | 'stable'
}

export interface ReasoningIntensityData {
  callsPerDay: number
  tierUsed: 'tier1' | 'tier2'
  purposes: string[]
  costToday: number
  balance?: number
  provider?: string
}

export interface LearningYieldData {
  failureModesClosed: number
  invariantsCreated: number
  suppressionRegretReduced: number
  trend: 'up' | 'down' | 'stable'
}

interface CognitiveActivityMetersProps {
  searchActivity: SearchActivityData
  reasoningIntensity: ReasoningIntensityData
  learningYield: LearningYieldData
}

function Gauge({
  value,
  max,
  label,
  color,
}: {
  value: number
  max: number
  label: string
  color: string
}) {
  const percentage = Math.min((value / max) * 100, 100)
  const circumference = 2 * Math.PI * 40 // radius = 40

  return (
    <div className="relative w-24 h-24">
      <svg className="w-24 h-24 transform -rotate-90" viewBox="0 0 100 100">
        {/* Background circle */}
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="transparent"
          stroke="currentColor"
          strokeWidth="8"
          className="text-gray-800"
        />
        {/* Progress circle */}
        <circle
          cx="50"
          cy="50"
          r="40"
          fill="transparent"
          stroke="currentColor"
          strokeWidth="8"
          strokeLinecap="round"
          className={color}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - (percentage / 100) * circumference}
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-bold text-white">{value}</span>
        <span className="text-[10px] text-gray-500 uppercase">{label}</span>
      </div>
    </div>
  )
}

function TrendIndicator({ trend }: { trend: 'up' | 'down' | 'stable' }) {
  if (trend === 'up') {
    return <TrendingUp className="h-4 w-4 text-green-400" />
  }
  if (trend === 'down') {
    return <TrendingUp className="h-4 w-4 text-red-400 rotate-180" />
  }
  return <div className="h-4 w-4 text-gray-400">-</div>
}

export function CognitiveActivityMeters({
  searchActivity,
  reasoningIntensity,
  learningYield,
}: CognitiveActivityMetersProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Cognitive Activity Meters
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Non-Financial Resource Utilization
          </p>
        </div>
      </div>

      {/* Three Meters Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Search Activity (Serper) */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-4">
            <Search className="h-5 w-5 text-purple-400" />
            <span className="text-sm font-medium text-white">Search Activity</span>
            <span className="text-xs text-purple-400 ml-auto">Serper</span>
          </div>

          <div className="flex items-center justify-center mb-4">
            <Gauge
              value={searchActivity.queriesPerDay}
              max={100}
              label="/day"
              color="text-purple-400"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Queries/day</span>
              <span className="text-gray-300 font-mono">{searchActivity.queriesPerDay}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Domains</span>
              <div className="flex items-center gap-1">
                <Globe className="h-3 w-3 text-gray-500" />
                <span className="text-gray-300">{searchActivity.domainsCovered.length}</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {searchActivity.domainsCovered.slice(0, 4).map((domain) => (
                <span
                  key={domain}
                  className="text-[10px] px-2 py-0.5 bg-gray-900 text-purple-400 rounded"
                >
                  {domain}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Reasoning Intensity (LLM) */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-4">
            <Brain className="h-5 w-5 text-blue-400" />
            <span className="text-sm font-medium text-white">Reasoning Intensity</span>
            <span className="text-xs text-blue-400 ml-auto">LLM</span>
          </div>

          {/* LLM Balance - Prominent Display */}
          {reasoningIntensity.balance !== undefined && (
            <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg">
              <div className="text-center">
                <div className="text-2xl font-bold text-green-400 font-mono">
                  ${reasoningIntensity.balance.toFixed(2)}
                </div>
                <div className="text-xs text-green-400/70 mt-1">
                  {reasoningIntensity.provider || 'DeepSeek'} Balance (Live)
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center justify-center mb-4">
            <Gauge
              value={reasoningIntensity.callsPerDay}
              max={50}
              label="/day"
              color="text-blue-400"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Calls/day</span>
              <span className="text-gray-300 font-mono">{reasoningIntensity.callsPerDay}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Tier Used</span>
              <span className={`font-mono ${
                reasoningIntensity.tierUsed === 'tier1' ? 'text-yellow-400' : 'text-gray-400'
              }`}>
                {reasoningIntensity.tierUsed.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Cost Today</span>
              <span className="text-green-400 font-mono">
                ${reasoningIntensity.costToday.toFixed(2)}
              </span>
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {reasoningIntensity.purposes.slice(0, 3).map((purpose) => (
                <span
                  key={purpose}
                  className="text-[10px] px-2 py-0.5 bg-gray-900 text-blue-400 rounded"
                >
                  {purpose}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Learning Yield */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-4">
            <Target className="h-5 w-5 text-green-400" />
            <span className="text-sm font-medium text-white">Learning Yield</span>
            <TrendIndicator trend={learningYield.trend} />
          </div>

          <div className="flex items-center justify-center mb-4">
            <Gauge
              value={learningYield.failureModesClosed}
              max={20}
              label="closed"
              color="text-green-400"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">FM Closed</span>
              <span className="text-green-400 font-mono">{learningYield.failureModesClosed}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Invariants</span>
              <span className="text-blue-400 font-mono">+{learningYield.invariantsCreated}</span>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-500">Regret Reduced</span>
              <span className="text-yellow-400 font-mono">
                {learningYield.suppressionRegretReduced > 0 ? '-' : ''}{learningYield.suppressionRegretReduced}%
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-800">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <span>Updated: Real-time</span>
          <span>Source: fhq_governance.cognitive_activity_log</span>
        </div>
      </div>
    </div>
  )
}
