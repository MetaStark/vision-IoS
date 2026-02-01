/**
 * IoS-013 Signal Overview
 * CEO-DIR-2026-024 + CEO-DIR-2026-025: Database-Verified Dashboard Integrity
 *
 * Features:
 * - Factor breakdown per asset (not generic explanations)
 * - Brier/Skill panel with discrepancy tracking
 * - LVI status visibility
 * - Murphy decomposition drill-down
 */

'use client'

import { useState, useEffect, useMemo } from 'react'
import { ArrowUpDown, Filter, RefreshCw, ChevronDown, ChevronRight, AlertTriangle, CheckCircle, XCircle } from 'lucide-react'

interface FactorBreakdown {
  base_confidence: number
  regime_factor: number
  skill_factor: number
  causal_factor: number
  macro_bonus: number
  event_penalty: number
  composite_multiplier: number
  technical_signals: string[]
}

interface SignalRow {
  asset_id: string
  calibration_status: string
  direction: string
  confidence_score: number
  regime_context: string
  factors: FactorBreakdown
}

interface BrierData {
  avg_brier_forecast_skill_metrics: number | null
  avg_brier_v_brier_summary: number | null
  skill_factor_used: number
  skill_formula: string
  forecast_count: number
  discrepancy_exists: boolean
  discrepancy_delta: number | null
  last_computed: string | null
}

interface MurphyDecomposition {
  avg_reliability: number | null
  avg_resolution: number | null
  avg_uncertainty: number | null
  sample_count: number
  computed_at: string | null
}

interface LVIStatus {
  is_active: boolean
  system_avg_lvi: number | null
  regime_avg_lvi: number | null
  total_assets_with_lvi: number
  last_computed: string | null
  missing_reason: string | null
}

interface SystemStatus {
  status: 'ACTIVE' | 'STALE' | 'DEGRADED'
  total_assets: number
  calibrated_assets: number
  last_updated: string
}

interface SignalData {
  system_status: SystemStatus
  signals: SignalRow[]
  brier: BrierData
  murphy: MurphyDecomposition
  lvi: LVIStatus
  db_reconciliation: {
    query_timestamp: string
    source_table: string
    row_count_match: boolean
  }
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'ACTIVE': return 'text-green-400'
    case 'STALE': return 'text-yellow-400'
    case 'DEGRADED': return 'text-red-400'
    default: return 'text-gray-400'
  }
}

function getCalibrationBadge(status: string): { bg: string; text: string } {
  if (status === 'CALIBRATED') {
    return { bg: 'bg-green-900/50', text: 'text-green-300' }
  }
  return { bg: 'bg-yellow-900/50', text: 'text-yellow-300' }
}

function getDirectionDisplay(direction: string): { label: string; color: string } {
  switch (direction) {
    case 'LONG': return { label: 'LONG', color: 'text-green-400' }
    case 'SHORT': return { label: 'SHORT', color: 'text-red-400' }
    default: return { label: 'UNDEFINED', color: 'text-gray-500' }
  }
}

function getRegimeColor(regime: string): string {
  switch (regime) {
    case 'RISK_ON': return 'text-green-400'
    case 'RISK_OFF': return 'text-red-400'
    case 'NEUTRAL': return 'text-blue-400'
    default: return 'text-gray-400'
  }
}

function formatTimestamp(ts: string) {
  const date = new Date(ts)
  return date.toLocaleString('no-NO', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function FactorExplanation({ factors, confidence }: { factors: FactorBreakdown; confidence: number }) {
  // Deterministic rendering of factor fields
  const parts: string[] = []

  // Base confidence analysis
  if (factors.base_confidence === 0) {
    parts.push('Base=0 (ingen teknisk signal)')
  } else {
    parts.push(`Base=${factors.base_confidence.toFixed(2)}`)
  }

  // Regime factor
  parts.push(`Regime×${factors.regime_factor.toFixed(2)}`)

  // Skill factor
  parts.push(`Skill=${factors.skill_factor.toFixed(2)}`)

  // Causal factor
  if (factors.causal_factor !== 0.5) {
    parts.push(`Causal=${factors.causal_factor.toFixed(2)}`)
  }

  // Macro bonus
  if (factors.macro_bonus !== 0) {
    parts.push(`Macro${factors.macro_bonus > 0 ? '+' : ''}${factors.macro_bonus.toFixed(2)}`)
  }

  // Event penalty
  if (factors.event_penalty !== 0) {
    parts.push(`Event-${Math.abs(factors.event_penalty).toFixed(2)}`)
  }

  // Composite multiplier
  if (factors.composite_multiplier > 0) {
    parts.push(`→ ×${factors.composite_multiplier.toFixed(3)}`)
  }

  return (
    <span className="text-xs text-gray-500 font-mono">
      {parts.join(' · ')}
    </span>
  )
}

function FactorBreakdownRow({ factors }: { factors: FactorBreakdown }) {
  return (
    <div className="grid grid-cols-7 gap-2 text-xs font-mono py-1 px-2 bg-gray-900/30 rounded">
      <div className="text-center">
        <div className="text-gray-500">Base</div>
        <div className={factors.base_confidence === 0 ? 'text-red-400' : 'text-gray-300'}>
          {factors.base_confidence.toFixed(3)}
        </div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Regime</div>
        <div className="text-blue-400">{factors.regime_factor.toFixed(2)}</div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Skill</div>
        <div className="text-purple-400">{factors.skill_factor.toFixed(2)}</div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Causal</div>
        <div className="text-cyan-400">{factors.causal_factor.toFixed(2)}</div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Macro</div>
        <div className={factors.macro_bonus > 0 ? 'text-green-400' : factors.macro_bonus < 0 ? 'text-red-400' : 'text-gray-500'}>
          {factors.macro_bonus > 0 ? '+' : ''}{factors.macro_bonus.toFixed(2)}
        </div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Event</div>
        <div className={factors.event_penalty !== 0 ? 'text-orange-400' : 'text-gray-500'}>
          {factors.event_penalty !== 0 ? `-${Math.abs(factors.event_penalty).toFixed(2)}` : '0.00'}
        </div>
      </div>
      <div className="text-center">
        <div className="text-gray-500">Mult</div>
        <div className="text-yellow-400">{factors.composite_multiplier.toFixed(3)}</div>
      </div>
    </div>
  )
}

export default function IoS013SignalsPage() {
  const [data, setData] = useState<SignalData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterCalibrated, setFilterCalibrated] = useState(false)
  const [sortDesc, setSortDesc] = useState(true)
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [showMurphy, setShowMurphy] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch('/api/ios013/signals')
      if (!response.ok) throw new Error('Failed to fetch')
      const result = await response.json()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const filteredSignals = useMemo(() => {
    if (!data?.signals) return []
    let signals = [...data.signals]
    if (filterCalibrated) {
      signals = signals.filter(s => s.calibration_status === 'CALIBRATED')
    }
    signals.sort((a, b) => {
      const diff = b.confidence_score - a.confidence_score
      return sortDesc ? diff : -diff
    })
    return signals
  }, [data?.signals, filterCalibrated, sortDesc])

  const toggleRow = (assetId: string) => {
    const newSet = new Set(expandedRows)
    if (newSet.has(assetId)) {
      newSet.delete(assetId)
    } else {
      newSet.add(assetId)
    }
    setExpandedRows(newSet)
  }

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-black p-8">
        <div className="text-gray-400 animate-pulse">Loading IoS-013 signals...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-black p-8">
        <div className="text-red-400">Error: {error}</div>
        <button onClick={fetchData} className="mt-4 px-4 py-2 bg-gray-800 text-gray-300 rounded hover:bg-gray-700">
          Retry
        </button>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-950/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-white">
                IoS-013 <span className="text-gray-600">–</span>{' '}
                <span className="text-blue-400">Signal Overview</span>
              </h1>
              <p className="text-xs text-gray-500 mt-1">
                CEO-DIR-2026-024/025 · Database-Verified · Factor Breakdown
              </p>
            </div>
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-800 hover:border-gray-600 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-[1800px] mx-auto px-6 py-6 space-y-6">
        {/* System Status Line */}
        <div className="p-4 bg-gray-900/50 border border-gray-800 rounded-lg">
          <div className="flex items-center gap-4 text-sm font-mono">
            <span className="text-gray-400">IoS-013</span>
            <span className={`font-bold ${getStatusColor(data.system_status.status)}`}>
              {data.system_status.status}
            </span>
            <span className="text-gray-600">·</span>
            <span className="text-gray-300">{data.system_status.total_assets} assets</span>
            <span className="text-gray-600">·</span>
            <span className="text-green-400">{data.system_status.calibrated_assets} CALIBRATED</span>
            <span className="text-gray-600">·</span>
            <span className="text-gray-500">
              updated {formatTimestamp(data.system_status.last_updated)}
            </span>
            <span title={data.db_reconciliation.row_count_match ? "DB row count match" : "DB row count mismatch"}>
              {data.db_reconciliation.row_count_match ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500" />
              )}
            </span>
          </div>
        </div>

        {/* Brier / Skill Panel */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Brier Score */}
          <div className="p-4 bg-gray-900/50 border border-gray-800 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-400">Brier Score</h3>
              {data.brier.discrepancy_exists && (
                <span className="flex items-center gap-1 text-xs text-yellow-400">
                  <AlertTriangle className="h-3 w-3" />
                  DISCREPANCY
                </span>
              )}
            </div>
            <div className="space-y-2 text-sm font-mono">
              <div className="flex justify-between">
                <span className="text-gray-500">forecast_skill_metrics:</span>
                <span className="text-gray-300">{data.brier.avg_brier_forecast_skill_metrics?.toFixed(4) ?? 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">v_brier_summary:</span>
                <span className="text-gray-300">{data.brier.avg_brier_v_brier_summary?.toFixed(4) ?? 'N/A'}</span>
              </div>
              {data.brier.discrepancy_exists && (
                <div className="flex justify-between text-yellow-400">
                  <span>Delta:</span>
                  <span>{data.brier.discrepancy_delta?.toFixed(4)}</span>
                </div>
              )}
              <div className="pt-2 border-t border-gray-800">
                <span className="text-gray-500 text-xs">n={data.brier.forecast_count.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Skill Factor */}
          <div className="p-4 bg-gray-900/50 border border-gray-800 rounded-lg">
            <h3 className="text-sm font-semibold text-gray-400 mb-2">Skill Factor</h3>
            <div className="space-y-2 text-sm font-mono">
              <div className="flex justify-between">
                <span className="text-gray-500">Current:</span>
                <span className="text-purple-400 text-lg font-bold">{data.brier.skill_factor_used.toFixed(4)}</span>
              </div>
              <div className="text-xs text-gray-600 mt-2">
                Formula: {data.brier.skill_formula}
              </div>
              <div className="text-xs text-gray-600">
                Last computed: {data.brier.last_computed ? formatTimestamp(data.brier.last_computed) : 'N/A'}
              </div>
            </div>
          </div>

          {/* LVI Status */}
          <div className="p-4 bg-gray-900/50 border border-gray-800 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-400">LVI Status</h3>
              {data.lvi.is_active ? (
                <span className="text-xs text-green-400 font-semibold">ACTIVE</span>
              ) : (
                <span className="text-xs text-red-400 font-semibold">NOT ACTIVE</span>
              )}
            </div>
            {data.lvi.is_active ? (
              <div className="space-y-2 text-sm font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-500">System avg:</span>
                  <span className="text-cyan-400">{data.lvi.system_avg_lvi?.toFixed(4) ?? 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Regime avg:</span>
                  <span className="text-cyan-400">{data.lvi.regime_avg_lvi?.toFixed(4) ?? 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Assets:</span>
                  <span className="text-gray-300">{data.lvi.total_assets_with_lvi}</span>
                </div>
              </div>
            ) : (
              <div className="text-sm text-red-400">
                {data.lvi.missing_reason || 'Unknown reason'}
              </div>
            )}
          </div>
        </div>

        {/* Murphy Decomposition (Collapsible) */}
        <div className="p-4 bg-gray-900/50 border border-gray-800 rounded-lg">
          <button
            onClick={() => setShowMurphy(!showMurphy)}
            className="flex items-center gap-2 text-sm font-semibold text-gray-400 hover:text-gray-300"
          >
            {showMurphy ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            Murphy Decomposition (Reliability / Resolution / Uncertainty)
          </button>
          {showMurphy && (
            <div className="mt-4 grid grid-cols-4 gap-4 text-sm font-mono">
              <div>
                <div className="text-gray-500">Reliability</div>
                <div className="text-lg text-orange-400">{data.murphy.avg_reliability?.toFixed(4) ?? 'N/A'}</div>
              </div>
              <div>
                <div className="text-gray-500">Resolution</div>
                <div className="text-lg text-green-400">{data.murphy.avg_resolution?.toFixed(4) ?? 'N/A'}</div>
              </div>
              <div>
                <div className="text-gray-500">Uncertainty</div>
                <div className="text-lg text-blue-400">{data.murphy.avg_uncertainty?.toFixed(4) ?? 'N/A'}</div>
              </div>
              <div>
                <div className="text-gray-500">Samples</div>
                <div className="text-lg text-gray-300">{data.murphy.sample_count}</div>
              </div>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setSortDesc(!sortDesc)}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-800 transition-colors"
          >
            <ArrowUpDown className="h-4 w-4" />
            Confidence {sortDesc ? '(high→low)' : '(low→high)'}
          </button>
          <button
            onClick={() => setFilterCalibrated(!filterCalibrated)}
            className={`flex items-center gap-2 px-3 py-1.5 border rounded text-sm transition-colors ${
              filterCalibrated
                ? 'bg-green-900/30 border-green-700 text-green-300'
                : 'bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800'
            }`}
          >
            <Filter className="h-4 w-4" />
            {filterCalibrated ? 'CALIBRATED only' : 'Show all'}
          </button>
          <span className="text-xs text-gray-600">
            {filteredSignals.length} of {data.signals.length} assets
          </span>
        </div>

        {/* Signal Table with Factor Breakdown */}
        <div className="border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-900/80 border-b border-gray-800">
                <th className="px-2 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider w-8"></th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Asset</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Calibration</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Signal</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Confidence</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Regime</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider">Factor Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50">
              {filteredSignals.map((signal) => {
                const calibBadge = getCalibrationBadge(signal.calibration_status)
                const dirDisplay = getDirectionDisplay(signal.direction)
                const isExpanded = expandedRows.has(signal.asset_id)

                return (
                  <>
                    <tr
                      key={signal.asset_id}
                      className="hover:bg-gray-900/30 transition-colors cursor-pointer"
                      onClick={() => toggleRow(signal.asset_id)}
                    >
                      <td className="px-2 py-3 text-gray-500">
                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono font-semibold text-white">{signal.asset_id}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${calibBadge.bg} ${calibBadge.text}`}>
                          {signal.calibration_status === 'CALIBRATED' ? 'CALIBRATED' : 'NOT CALIBRATED'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-mono font-semibold ${dirDisplay.color}`}>{dirDisplay.label}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-gray-300">{signal.confidence_score.toFixed(4)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-mono ${getRegimeColor(signal.regime_context)}`}>{signal.regime_context}</span>
                      </td>
                      <td className="px-4 py-3">
                        <FactorExplanation factors={signal.factors} confidence={signal.confidence_score} />
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${signal.asset_id}-expanded`} className="bg-gray-950/50">
                        <td colSpan={7} className="px-4 py-3">
                          <div className="space-y-2">
                            <div className="text-xs text-gray-500 uppercase tracking-wider">Factor Breakdown</div>
                            <FactorBreakdownRow factors={signal.factors} />
                            {signal.factors.technical_signals.length > 0 && (
                              <div className="text-xs">
                                <span className="text-gray-500">Technical signals: </span>
                                <span className="text-gray-400">{signal.factors.technical_signals.join(', ')}</span>
                              </div>
                            )}
                            {signal.confidence_score === 0 && (
                              <div className="text-xs text-red-400">
                                Confidence=0 because: {signal.factors.base_confidence === 0 ? 'base_confidence=0 (no technical signal)' : 'composite multiplier resulted in zero'}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="text-xs text-gray-600 text-center space-y-1">
          <div>CEO-DIR-2026-024/025 · Source: {data.db_reconciliation.source_table}</div>
          <div>Query timestamp: {data.db_reconciliation.query_timestamp}</div>
        </div>
      </div>
    </div>
  )
}
