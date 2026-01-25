/**
 * Learning Observability Dashboard - CEO-DIR-2026-057 & CEO-DIR-2026-058
 * "ACI Learning in Motion" - Executive Dashboard
 *
 * CEO-DIR-2026-058 UPDATE:
 * Dashboard now shows TWO separate progress bars:
 * - System Maturity (FMCL, safety, governance) - can reach 100%
 * - Market Learning (holdout performance) - starts at 0%
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, BookOpen, Brain, AlertCircle } from 'lucide-react'
import {
  DualProgressBars,
  DailyDeltaPanel,
  MechanismPanel,
  CognitiveActivityMeters,
  EvidenceClock,
  ResearchTrinityPanel,
  LearningTrajectoryCharts,
  LearningFourPlanes,
} from '@/components/learning'
import type { LearningTrajectoryData, LearningFourPlanesData } from '@/components/learning'
import type {
  DailyLearningItem,
  LearningMechanism,
  SearchActivityData,
  ReasoningIntensityData,
  LearningYieldData,
  EvidenceClockData,
} from '@/components/learning'

interface MarketLearningData {
  progress: number
  status: string
  labelLocked: boolean
  labelVersion: string | null
  labelHash: string | null
  holdoutCount: number
  holdoutFrozen: boolean
  holdoutVerified: boolean
  latestBrier: number | null
  latestDelta: number | null
  latestDirection: string | null
  totalEvaluations: number
  significantImprovements: number
}

interface ResearchTrinityData {
  finnE: { count: number; share: number }
  finnT: { count: number; share: number }
  gnS: { count: number; share: number }
  totalHypotheses: number
  tier1DeathRate: number
  errorConversionRate: number
  avgCausalDepth: number
  learningHealth: 'GREEN' | 'AMBER' | 'RED'
}

interface LearningData {
  progress: number
  systemMaturity: number
  marketLearning: MarketLearningData
  researchTrinity: ResearchTrinityData | null
  learningTrajectory: LearningTrajectoryData | null
  fourPlanes: LearningFourPlanesData | null // CEO-DIR-2026-DAY25-LEARNING-VISIBILITY-002
  evidenceClock: EvidenceClockData
  fmclDistribution: string
  highSeverityClosed: number
  highSeverityTotal: number
  dailyDelta: DailyLearningItem[]
  mechanisms: LearningMechanism[]
  searchActivity: SearchActivityData
  reasoningIntensity: ReasoningIntensityData
  learningYield: LearningYieldData
  llmBalance: number
  activeProviders: string
  lastUpdated: string
  source: string
}

export default function LearningDashboardPage() {
  const [mounted, setMounted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<LearningData | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/learning')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const json = await response.json()
      if (json.error) {
        throw new Error(json.details || json.error)
      }
      setData(json)
    } catch (err) {
      console.error('Failed to fetch learning data:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setMounted(true)
    fetchData()
  }, [fetchData])

  const handleRefresh = () => {
    fetchData()
  }

  const today = new Date().toISOString().split('T')[0]

  // Default values while loading
  const progress = data?.progress ?? 80
  const dailyItems = data?.dailyDelta ?? []
  const mechanisms = data?.mechanisms ?? []
  const searchActivity = data?.searchActivity ?? {
    queriesPerDay: 0,
    domainsCovered: [],
    trend: 'stable' as const,
  }
  const reasoningIntensity = data?.reasoningIntensity ?? {
    callsPerDay: 0,
    tierUsed: 'tier2' as const,
    purposes: [],
    costToday: 0,
    balance: undefined,
    provider: undefined,
  }
  // Add balance from top-level data to reasoningIntensity
  if (data?.llmBalance !== undefined) {
    reasoningIntensity.balance = data.llmBalance
    reasoningIntensity.provider = data.activeProviders
  }
  const learningYield = data?.learningYield ?? {
    failureModesClosed: 0,
    invariantsCreated: 0,
    suppressionRegretReduced: 0,
    trend: 'stable' as const,
  }

  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-950/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Left: Title */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <BookOpen className="h-6 w-6 text-blue-400" />
                <h1 className="text-xl font-bold text-white">
                  ACI Learning in Motion
                </h1>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-gray-600">CEO-DIR-2026-057</span>
                {data?.source === 'database' && (
                  <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full">
                    LIVE DATA
                  </span>
                )}
                {data?.source === 'error' && (
                  <span className="px-2 py-0.5 bg-red-500/20 text-red-400 rounded-full">
                    ERROR
                  </span>
                )}
              </div>
            </div>

            {/* Right: Controls */}
            <div className="flex items-center gap-4">
              {data?.llmBalance !== undefined && (
                <div className="text-xs text-gray-500">
                  LLM Balance: <span className="text-green-400 font-mono">
                    {data.activeProviders === 'serper'
                      ? `${data.llmBalance.toLocaleString()} credits`
                      : `$${data.llmBalance.toFixed(2)}`}
                  </span>
                  {data.activeProviders && (
                    <span className="text-gray-600 ml-1">({data.activeProviders})</span>
                  )}
                </div>
              )}
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-800 hover:border-gray-600 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <div className="text-xs text-gray-600">
                {mounted && data?.lastUpdated
                  ? `Updated: ${new Date(data.lastUpdated).toLocaleTimeString()}`
                  : 'Loading...'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="max-w-[1800px] mx-auto px-6 pt-4">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-red-400 font-medium">Failed to load live data</p>
              <p className="text-xs text-red-400/70 mt-1">{error}</p>
              <p className="text-xs text-gray-500 mt-2">Displaying cached/default values</p>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="max-w-[1800px] mx-auto px-6 py-8 space-y-8">
        {/* Zone 1: Dual Progress Bars (CEO-DIR-2026-058) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-blue-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Dual-Track Progress (CEO-DIR-2026-046/058)
            </h2>
            {data?.fmclDistribution && (
              <span className="text-xs text-gray-600 font-mono ml-2">
                FMCL: {data.fmclDistribution}
              </span>
            )}
          </div>
          <DualProgressBars
            systemMaturity={data?.systemMaturity ?? data?.progress ?? 0}
            marketLearning={data?.marketLearning?.progress ?? 0}
            marketLearningStatus={data?.marketLearning?.status ?? 'Loading...'}
            labelLocked={data?.marketLearning?.labelLocked ?? false}
            holdoutFrozen={data?.marketLearning?.holdoutFrozen ?? false}
            holdoutVerified={data?.marketLearning?.holdoutVerified ?? false}
            lastUpdated={mounted && data?.lastUpdated
              ? new Date(data.lastUpdated).toLocaleDateString()
              : undefined}
          />
        </section>

        {/* Zone 1.2: Four-Plane Learning Dashboard (CEO-DIR-2026-DAY25-LEARNING-VISIBILITY-002) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-amber-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Four-Plane Learning State (CEO-DIR-2026-DAY25-LEARNING-VISIBILITY-002)
            </h2>
          </div>
          <LearningFourPlanes data={data?.fourPlanes ?? null} />
        </section>

        {/* Zone 1.5: Research Trinity Panel (CEO-DIR-2026-LEARNING-OBSERVABILITY) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-indigo-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Research Trinity (CEO-DIR-2026-LEARNING-OBSERVABILITY)
            </h2>
          </div>
          <ResearchTrinityPanel data={data?.researchTrinity ?? null} />
        </section>

        {/* Zone 1.6: Learning Trajectory Charts (CEO-DIR-2026-DAY25-VISUAL-TRUTH) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-emerald-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Learning Trajectory (CEO-DIR-2026-DAY25-VISUAL-TRUTH)
            </h2>
          </div>
          <LearningTrajectoryCharts data={data?.learningTrajectory ?? null} />
        </section>

        {/* Zone 2: Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* What Did We Learn Today? */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-green-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Daily Learning Delta
              </h2>
            </div>
            <DailyDeltaPanel date={today} items={dailyItems} />
          </section>

          {/* How Did We Learn It? */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-yellow-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Learning Mechanisms
              </h2>
            </div>
            <MechanismPanel mechanisms={mechanisms} />
          </section>
        </div>

        {/* Zone 3: Two-column - Cognitive Activity + Evidence Clock */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Cognitive Activity Meters (2/3 width) */}
          <section className="lg:col-span-2">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-purple-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Cognitive Resource Utilization
              </h2>
            </div>
            <CognitiveActivityMeters
              searchActivity={searchActivity}
              reasoningIntensity={reasoningIntensity}
              learningYield={learningYield}
            />
          </section>

          {/* Evidence Clock (1/3 width) - CEO-DIR-2026-059 */}
          <section>
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-cyan-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Evidence Clock (CEO-DIR-2026-059)
              </h2>
            </div>
            <EvidenceClock data={data?.evidenceClock ?? null} />
          </section>
        </div>

        {/* CEO Guidance Panel */}
        <section className="bg-gray-900/50 border border-gray-800 rounded-lg p-6">
          <div className="flex items-start gap-4">
            <Brain className="h-6 w-6 text-blue-400 flex-shrink-0 mt-1" />
            <div>
              <h3 className="text-lg font-semibold text-white mb-2">
                CEO Guidance: LLM Utilization Context
              </h3>
              <div className="text-sm text-gray-400 space-y-2">
                <p>
                  <strong className="text-gray-300">Current Phase:</strong> Structural repair complete.
                  All {data?.highSeverityTotal || 16} HIGH severity failure modes CLOSED.
                  FMCL loop functional.
                </p>
                <p>
                  <strong className="text-gray-300">Why low spend is correct (for now):</strong> Heavy
                  LLM reasoning before learning infrastructure would have produced confident nonsense
                  and reinforced bad priors.
                </p>
                <p>
                  <strong className="text-gray-300">Next Step (CEO-DIR-2026-058 Preview):</strong> Tier-1
                  cognitive burst for diagnosis only. $1-$3/day. Zero signal generation increase.
                  Pending 2-3 days of visible learning on this dashboard.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-gray-900 pt-8 pb-4">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <div className="flex items-center gap-4">
              <span>CEO-DIR-2026-057</span>
              <span className="text-gray-800">|</span>
              <span>Learning Observability Dashboard</span>
              <span className="text-gray-800">|</span>
              <span>STIG Implementation</span>
              {data?.source === 'database' && (
                <>
                  <span className="text-gray-800">|</span>
                  <span className="text-green-500">Connected to PostgreSQL</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-4">
              <span>HIGH Closed: {data?.highSeverityClosed || 0}/{data?.highSeverityTotal || 0}</span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  )
}
