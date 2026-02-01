/**
 * FjordHQ Calendar Dashboard - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Calendar-as-Law Doctrine: If something matters, it exists as a canonical calendar event.
 * CEO must understand system state in <30 seconds.
 *
 * Section 2: FjordHQ Calendar - Dashboard Authority Layer
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Calendar as CalendarIcon, AlertCircle, CheckCircle, XCircle } from 'lucide-react'
import {
  CalendarGrid,
  CEOSummaryPanel,
  ActiveTestsPanel,
  CEOAlertsPanel,
  LVGStatusPanel,
  EconomicEventsPanel,
  CanonicalTestCard,
  LearningVisibilityPanel,
  G15ProgressionPanel,
  SurvivalAnalysisPanel,
  Phase2ExperimentsPanel,
  // Wave15StatusPanel - SUSPENDED until G1.5 completes (2026-02-07)
} from '@/components/calendar'

interface CalendarEvent {
  id: string
  name: string
  category: string
  date: string
  endDate?: string
  status: string
  owner: string
  details: any
  color: string
  day: number
  month: number
  year: number
}

interface EconomicEvent {
  id: string
  name: string
  typeCode: string
  timestamp: string
  consensus: number | null
  previous: number | null
  actual: number | null
  surprise: number | null
  impactRank: number
  category: string
  status: string
}

interface CanonicalTest {
  id: string
  code: string
  name: string
  owner: string
  status: string
  category: string
  startDate: string
  endDate: string
  daysElapsed: number
  daysRemaining: number
  requiredDays: number
  progressPct: number
  businessIntent?: string
  beneficiarySystem?: string
  hypothesisCode?: string
  baselineDefinition?: any
  targetMetrics?: any
  successCriteria?: any
  failureCriteria?: any
  monitoringAgent?: string
  escalationState?: string
  ceoActionRequired?: boolean
  recommendedActions?: string[]
  midTestCheckpoint?: string
  verdict?: string
}

interface CalendarData {
  events: CalendarEvent[]
  activeTests: any[]
  canonicalTests: CanonicalTest[]
  alerts: any[]
  observationWindows: any[]
  economicEvents: EconomicEvent[]
  lvgStatus: any
  shadowTier: any
  governanceChecks: any[]
  // CEO-DIR-2026-WAVE15-DAEMON-WATCHDOG-001: Wave15 Alpha Hunter Status
  wave15Status?: {
    status: 'RUNNING' | 'STOPPED'
    lastHeartbeat: string | null
    secondsSinceHeartbeat: number | null
    huntsCompleted: number
    needlesFound: number
    totalCostUsd: number
    mode: string
  }
  // CEO-DIR-2026-DAY25: Learning Visibility
  learningMetrics?: any[]
  learningSummary?: any
  generatorPerformance?: any[]
  // CEO-VEDTAK-2026-ALPHA-FACTORY: G1.5 Experiment Progression
  g15Experiment?: any
  g15Generators?: any[]
  g15Quartiles?: any[]
  g15Validators?: any[]
  // CEO-DIR-2026-CALENDAR-IS-LAW: Phase 2 Alpha Satellite experiments
  phase2Experiments?: any[]
  // Regime state for CEO summary
  regime?: {
    currentRegime: string
    confidence: number
    transitionState: string
    microRegime: string | null
    momentum: string | null
    avgStress: number | null
  } | null
  currentDate: {
    today: string
    year: number
    month: number
    monthName: string
  }
  lastUpdated: string
  source: string
}

export default function CalendarPage() {
  const [mounted, setMounted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<CalendarData | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null)
  const [selectedDay, setSelectedDay] = useState<{
    day: number
    month: number
    year: number
    events: CalendarEvent[]
  } | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/calendar')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      const json = await response.json()
      if (json.error) {
        throw new Error(json.details || json.error)
      }
      setData(json)
    } catch (err) {
      console.error('Failed to fetch calendar data:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setMounted(true)
    fetchData()
  }, [fetchData])

  const handleEventClick = (event: CalendarEvent) => {
    setSelectedEvent(event)
  }

  const handleAlertClick = (alert: any) => {
    // TODO: Implement alert modal/drawer
    console.log('Alert clicked:', alert)
  }

  const handleDayClick = (day: number, month: number, year: number, events: CalendarEvent[]) => {
    setSelectedDay({ day, month, year, events })
  }

  // Default values
  const currentYear = data?.currentDate?.year || new Date().getFullYear()
  const currentMonth = data?.currentDate?.month || new Date().getMonth() + 1

  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-950/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Left: Title */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <CalendarIcon className="h-6 w-6 text-purple-400" />
                <h1 className="text-xl font-bold text-white">FjordHQ Calendar</h1>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-gray-600">CEO-DIR-2026-CGT-001</span>
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
              {/* Governance Status */}
              {data?.governanceChecks && (
                <div className="flex items-center gap-2">
                  {data.governanceChecks.map((check: any) => (
                    <div
                      key={check.name}
                      className={`flex items-center gap-1 px-2 py-1 rounded text-xs ${
                        check.status === 'PASS'
                          ? 'bg-green-500/10 text-green-400'
                          : check.status === 'WARNING'
                          ? 'bg-yellow-500/10 text-yellow-400'
                          : 'bg-red-500/10 text-red-400'
                      }`}
                      title={check.discrepancy || check.name}
                    >
                      {check.status === 'PASS' ? (
                        <CheckCircle className="h-3 w-3" />
                      ) : check.status === 'WARNING' ? (
                        <AlertCircle className="h-3 w-3" />
                      ) : (
                        <XCircle className="h-3 w-3" />
                      )}
                      <span className="hidden sm:inline">{check.name.split(' ')[0]}</span>
                    </div>
                  ))}
                </div>
              )}
              <button
                onClick={fetchData}
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
              <p className="text-sm text-red-400 font-medium">Failed to load calendar data</p>
              <p className="text-xs text-red-400/70 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="max-w-[1800px] mx-auto px-6 py-8 space-y-8">
        {/* CEO 30-Second Summary */}
        {data && (
          <CEOSummaryPanel
            canonicalTests={data.canonicalTests || []}
            economicEvents={data.economicEvents || []}
            lvgStatus={data.lvgStatus || { deathRatePct: 0, daemonStatus: 'STOPPED', totalHypotheses: 0, totalActive: 0 }}
            alerts={data.alerts || []}
            governanceChecks={data.governanceChecks || []}
            regime={data.regime || null}
          />
        )}

        {/* CEO-VEDTAK-2026-ALPHA-FACTORY: G1.5 Experiment Progression Panel */}
        {data?.g15Experiment && (
          <div>
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-purple-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                G1.5 Experiment Progression (CEO-VEDTAK-2026-ALPHA-FACTORY)
              </h2>
            </div>
            <G15ProgressionPanel
              experiment={data.g15Experiment}
              generators={data.g15Generators || []}
              quartiles={data.g15Quartiles || []}
              validators={data.g15Validators || []}
            />
          </div>
        )}

        {/* CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001 Section 5: Survival Analysis */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-amber-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              G1.5 Survival Analysis (CEO-DIR-2026-G1.5-GENERATION-VARIANCE-001)
            </h2>
          </div>
          <SurvivalAnalysisPanel />
        </div>

        {/* CEO-DIR-2026-CALENDAR-IS-LAW: Phase 2 Alpha Satellite Experiments */}
        {data?.phase2Experiments && data.phase2Experiments.length > 0 && (
          <div>
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-cyan-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Phase 2 Alpha Satellite (CEO-DIR-2026-CALENDAR-IS-LAW)
              </h2>
            </div>
            <Phase2ExperimentsPanel experiments={data.phase2Experiments} />
          </div>
        )}

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Calendar Grid (2/3 width) */}
          <div className="xl:col-span-2">
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-purple-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Monthly Calendar View (Section 2)
              </h2>
            </div>
            <CalendarGrid
              events={data?.events || []}
              testPeriods={(data?.canonicalTests || []).map(t => ({
                id: t.code,
                name: t.name,
                startDate: t.startDate,
                endDate: t.endDate,
                color: '#60a5fa'
              }))}
              currentYear={currentYear}
              currentMonth={currentMonth}
              onEventClick={handleEventClick}
              onDayClick={handleDayClick}
            />
          </div>

          {/* Right Sidebar (1/3 width) */}
          <div className="space-y-6">
            {/* CEO Alerts */}
            <div>
              <div className="mb-3 flex items-center gap-2">
                <div className="h-1 w-1 rounded-full bg-yellow-500" />
                <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                  CEO Action Required (Section 4.3)
                </h2>
              </div>
              <CEOAlertsPanel
                alerts={data?.alerts || []}
                onAlertClick={handleAlertClick}
              />
            </div>

            {/* LVG Status */}
            <div>
              <div className="mb-3 flex items-center gap-2">
                <div className="h-1 w-1 rounded-full bg-purple-500" />
                <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                  LVG Status (Section 5.5)
                </h2>
              </div>
              <LVGStatusPanel
                lvg={data?.lvgStatus || {
                  hypothesesBornToday: 0,
                  hypothesesKilledToday: 0,
                  entropyScore: null,
                  thrashingIndex: null,
                  governorAction: 'NORMAL',
                  velocityBrakeActive: false,
                }}
                shadowTier={data?.shadowTier || {
                  totalSamples: 0,
                  survivedCount: 0,
                  survivalRate: 0,
                  calibrationStatus: 'NORMAL',
                }}
              />
            </div>

            {/* Wave15 Alpha Discovery - SUSPENDED until G1.5 completes (2026-02-07) */}
          </div>
        </div>

        {/* CEO-DIR-2026-DAY25: Learning Visibility Section */}
        {data?.learningSummary && (
          <div>
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-purple-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Learning Visibility (CEO-DIR-2026-DAY25)
              </h2>
            </div>
            <LearningVisibilityPanel
              metrics={data.learningMetrics || []}
              summary={data.learningSummary}
              generators={data.generatorPerformance || []}
            />
          </div>
        )}

        {/* Economic Calendar Section (IoS-016) */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-amber-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Economic Calendar (Section 2 - IoS-016)
            </h2>
          </div>
          <EconomicEventsPanel events={data?.economicEvents || []} />
        </div>

        {/* Canonical Tests Section (CEO Modification - No JSON) */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-blue-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Canonical Tests (Migration 342)
            </h2>
            <span className="ml-2 text-xs text-gray-600">
              {data?.canonicalTests?.filter(t => t.status === 'ACTIVE').length || 0} active
            </span>
          </div>
          <div className="space-y-4">
            {data?.canonicalTests && data.canonicalTests.length > 0 ? (
              data.canonicalTests.map((test) => (
                <CanonicalTestCard
                  key={test.id}
                  test={test}
                  onActionClick={(action) => {
                    console.log('CEO Action:', action, 'for test:', test.code)
                  }}
                />
              ))
            ) : (
              <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6 text-center">
                <p className="text-gray-500 text-sm">No canonical tests registered.</p>
              </div>
            )}
          </div>
        </div>

        {/* Observation Windows */}
        {data?.observationWindows && data.observationWindows.length > 0 && (
          <div>
            <div className="mb-3 flex items-center gap-2">
              <div className="h-1 w-1 rounded-full bg-purple-500" />
              <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
                Observation Windows (Section 8)
              </h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data.observationWindows.map((window: any) => (
                <div
                  key={window.name}
                  className="bg-gray-900/50 border border-purple-500/20 rounded-xl p-6"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-medium text-white">{window.name}</h3>
                    {window.volumeScaling && (
                      <span className="px-2 py-0.5 bg-green-500/20 text-green-400 rounded text-xs">
                        Volume Scaling Active
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-4 mb-4">
                    <div>
                      <p className="text-xs text-gray-500">Progress</p>
                      <p className="text-lg font-mono text-white">
                        {window.currentDays}/{window.requiredDays}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Criteria Met</p>
                      <p className={`text-lg font-mono ${window.criteriaMet ? 'text-green-400' : 'text-gray-400'}`}>
                        {window.criteriaMet ? 'YES' : 'NO'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500">Drift Alerts</p>
                      <p className={`text-lg font-mono ${window.driftAlerts > 0 ? 'text-yellow-400' : 'text-gray-400'}`}>
                        {window.driftAlerts}
                      </p>
                    </div>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-500 rounded-full transition-all"
                      style={{
                        width: `${(window.currentDays / window.requiredDays) * 100}%`,
                      }}
                    />
                  </div>

                  {/* Rich Details (Section 8 Required) */}
                  {window.expectedImprovement && (
                    <div className="mt-4 pt-4 border-t border-gray-700/50">
                      <p className="text-xs text-gray-500 mb-1">Expected Improvement</p>
                      <p className="text-sm text-white">{window.expectedImprovement}</p>
                    </div>
                  )}

                  {window.improvementMetrics && typeof window.improvementMetrics === 'object' && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500 mb-2">Improvement Metrics</p>
                      <div className="grid grid-cols-2 gap-2">
                        {Object.entries(window.improvementMetrics).map(([key, val]) => (
                          <div key={key} className="flex items-center justify-between bg-gray-800/50 rounded px-2 py-1.5">
                            <span className="text-xs text-gray-500">{key.replace(/_/g, ' ')}</span>
                            <span className="text-xs text-white font-mono">{String(val)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {window.startingConsensusState && typeof window.startingConsensusState === 'object' && (
                    <div className="mt-3">
                      <p className="text-xs text-gray-500 mb-2">Starting Consensus State</p>
                      <div className="grid grid-cols-2 gap-2">
                        {Object.entries(window.startingConsensusState).map(([key, val]) => (
                          <div key={key} className="flex items-center justify-between bg-gray-800/50 rounded px-2 py-1.5">
                            <span className="text-xs text-gray-500">{key.replace(/_/g, ' ')}</span>
                            <span className="text-xs text-white font-mono">{val === null ? 'N/A' : String(val)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="border-t border-gray-900 pt-8 pb-4">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <div className="flex items-center gap-4">
              <span>CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001</span>
              <span className="text-gray-800">|</span>
              <span>FjordHQ Calendar Dashboard</span>
              <span className="text-gray-800">|</span>
              <span>STIG Implementation (EC-003)</span>
              {data?.source === 'database' && (
                <>
                  <span className="text-gray-800">|</span>
                  <span className="text-green-500">Connected to PostgreSQL</span>
                </>
              )}
            </div>
            <div className="flex items-center gap-4">
              <span>
                Events: {data?.events?.length || 0} | Economic: {data?.economicEvents?.length || 0} | Tests: {data?.activeTests?.length || 0}
              </span>
            </div>
          </div>
        </footer>
      </div>

      {/* Event Detail Modal - No JSON for CEO view */}
      {selectedEvent && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedEvent(null)}
        >
          <div
            className="bg-gray-900 border border-gray-700 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <div className="sticky top-0 bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
              <span className="text-sm text-gray-400">Event Details</span>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-gray-500 hover:text-white text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6">
              {/* For Canonical Tests - use CanonicalTestCard */}
              {selectedEvent.category === 'CANONICAL_TEST' && data?.canonicalTests ? (
                (() => {
                  const canonicalTest = data.canonicalTests.find(t => t.id === selectedEvent.id)
                  if (canonicalTest) {
                    return (
                      <CanonicalTestCard
                        test={canonicalTest}
                        onActionClick={(action) => {
                          console.log('CEO Action:', action)
                        }}
                      />
                    )
                  }
                  return null
                })()
              ) : (
                /* For other event types - clean display without JSON */
                <div className="space-y-4">
                  <div>
                    <h3 className="text-xl font-semibold text-white">{selectedEvent.name}</h3>
                    <p className="text-sm text-gray-400 mt-1">{selectedEvent.owner}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-gray-800/50 rounded-lg p-4">
                      <p className="text-xs text-gray-500">Date</p>
                      <p className="text-sm text-white mt-1">
                        {new Date(selectedEvent.date).toLocaleDateString('en-US', {
                          weekday: 'long',
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric'
                        })}
                      </p>
                    </div>
                    <div className="bg-gray-800/50 rounded-lg p-4">
                      <p className="text-xs text-gray-500">Status</p>
                      <p
                        className="text-sm font-medium mt-1"
                        style={{ color: selectedEvent.color }}
                      >
                        {selectedEvent.status}
                      </p>
                    </div>
                  </div>

                  {/* Economic Event specific display */}
                  {selectedEvent.category === 'ECONOMIC_EVENT' && selectedEvent.details && (
                    <div className="bg-gray-800/50 rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500">Event Time</span>
                        <span className="text-sm text-white">{selectedEvent.details.event_time}</span>
                      </div>
                      {selectedEvent.details.consensus !== null && (
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-500">Consensus</span>
                          <span className="text-sm text-white">{selectedEvent.details.consensus}</span>
                        </div>
                      )}
                      {selectedEvent.details.previous !== null && (
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-500">Previous</span>
                          <span className="text-sm text-white">{selectedEvent.details.previous}</span>
                        </div>
                      )}
                      {selectedEvent.details.actual !== null && (
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-500">Actual</span>
                          <span className="text-sm text-white font-semibold">{selectedEvent.details.actual}</span>
                        </div>
                      )}
                      {selectedEvent.details.impact_rank && (
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-gray-500">Impact</span>
                          <span className={`text-sm font-medium ${
                            selectedEvent.details.impact_rank >= 4 ? 'text-red-400' :
                            selectedEvent.details.impact_rank >= 3 ? 'text-amber-400' : 'text-gray-400'
                          }`}>
                            {selectedEvent.details.impact_rank}/5
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Day Detail Modal - Corporate Standard: Click date to see all events */}
      {selectedDay && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedDay(null)}
        >
          <div
            className="bg-gray-900 border border-gray-700 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  {new Date(selectedDay.year, selectedDay.month - 1, selectedDay.day).toLocaleDateString('en-US', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  {selectedDay.events.length} event{selectedDay.events.length !== 1 ? 's' : ''}
                </p>
              </div>
              <button
                onClick={() => setSelectedDay(null)}
                className="text-gray-500 hover:text-white text-2xl leading-none p-2"
              >
                &times;
              </button>
            </div>

            {/* Events List */}
            <div className="overflow-y-auto flex-1 p-4">
              {selectedDay.events.length === 0 ? (
                <div className="text-center py-12">
                  <p className="text-gray-500">No events scheduled for this day.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {selectedDay.events.map((event) => (
                    <button
                      key={event.id}
                      onClick={() => {
                        setSelectedDay(null)
                        setSelectedEvent(event)
                      }}
                      className="w-full text-left bg-gray-800/50 hover:bg-gray-800 border border-gray-700/50 hover:border-gray-600 rounded-lg p-4 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div
                          className="w-1 h-full min-h-[40px] rounded-full flex-shrink-0"
                          style={{ backgroundColor: event.color }}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-white truncate">{event.name}</span>
                            <span
                              className="text-xs px-2 py-0.5 rounded-full flex-shrink-0"
                              style={{ backgroundColor: event.color + '30', color: event.color }}
                            >
                              {event.category.replace(/_/g, ' ')}
                            </span>
                          </div>
                          <div className="flex items-center gap-4 mt-2 text-sm text-gray-400">
                            <span>{event.owner}</span>
                            <span className="text-gray-600">•</span>
                            <span
                              className="font-medium"
                              style={{ color: event.color }}
                            >
                              {event.status}
                            </span>
                          </div>
                        </div>
                        <div className="text-gray-500 text-sm">
                          →
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-gray-800 px-6 py-3 bg-gray-900/50">
              <p className="text-xs text-gray-500 text-center">
                Click an event for full details
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
