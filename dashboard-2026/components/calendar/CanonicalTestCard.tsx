/**
 * Canonical Test Card - CEO-DIR-2026-CGT-001 (CEO Modifications)
 *
 * Renders a single canonical test as a human-readable card.
 * NO JSON visible. NO raw field names. CEO understands in <30 seconds.
 *
 * Required Sections:
 * 1. Header (name, owner, status badges)
 * 2. Timeline (start, end, progress bar)
 * 3. Purpose & Logic (collapsible)
 * 4. Measurement (baseline, target, current)
 * 5. Governance (checkpoint, escalation)
 */

'use client'

import { useState } from 'react'
import {
  FlaskConical,
  Clock,
  Target,
  Users,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronDown,
  Calendar,
  Shield,
  Lightbulb,
  BarChart3,
  Activity,
  Database,
} from 'lucide-react'

interface CanonicalTest {
  name: string
  code: string
  owner: string
  status: string
  category: string
  startDate: string
  endDate: string
  // Progress (computed from storage)
  daysElapsed: number
  daysRemaining: number
  requiredDays: number
  progressPct: number
  // Purpose & Logic
  businessIntent?: string
  beneficiarySystem?: string
  hypothesisCode?: string
  // Measurement
  baselineDefinition?: any
  targetMetrics?: any
  successCriteria?: any
  failureCriteria?: any
  // Governance
  midTestCheckpoint?: string
  escalationState?: string
  ceoActionRequired?: boolean
  recommendedActions?: string[]
  verdict?: string
  monitoringAgent?: string
  // CEO-DIR-2026-DAY25-SESSION11: Test Progress (database-verified)
  testProgress?: {
    hypothesesInWindow: number
    falsifiedInWindow: number
    activeInWindow: number
    draftInWindow: number
    deathRateInWindow: number | null
    lastHypothesisInWindow: string | null
    verifiedAt: string
    trajectory: 'ON_TARGET' | 'TOO_BRUTAL' | 'TOO_MILD' | 'INSUFFICIENT_DATA' | 'UNKNOWN'
  } | null
}

interface CanonicalTestCardProps {
  test: CanonicalTest
  onActionClick?: (action: string) => void
}

function StatusBadge({ status, ceoActionRequired }: { status: string; ceoActionRequired?: boolean }) {
  if (ceoActionRequired) {
    return (
      <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-xs font-semibold flex items-center gap-1">
        <AlertTriangle className="h-3 w-3" />
        ACTION REQUIRED
      </span>
    )
  }

  const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
    ACTIVE: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'ACTIVE' },
    ON_TRACK: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'ON TRACK' },
    BEHIND: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'BEHIND' },
    COMPLETED: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'COMPLETED' },
    SUCCESS: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'SUCCESS' },
    FAILURE: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'FAILURE' },
  }

  const config = statusConfig[status] || statusConfig.ACTIVE

  return (
    <span className={`px-2 py-1 ${config.bg} ${config.text} rounded text-xs font-semibold`}>
      {config.label}
    </span>
  )
}

function ProgressBar({ elapsed, total, status }: { elapsed: number; total: number; status: string }) {
  const pct = Math.min(100, Math.round((elapsed / total) * 100))
  const isOnTrack = elapsed <= total

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-400">Day {elapsed} of {total}</span>
        <span className={isOnTrack ? 'text-blue-400' : 'text-yellow-400'}>{pct}%</span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            status === 'SUCCESS' ? 'bg-green-500' :
            status === 'FAILURE' ? 'bg-red-500' :
            isOnTrack ? 'bg-blue-500' : 'bg-yellow-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// CEO-DIR-2026-DAY25-SESSION11: Death Rate Gauge for Tier-1 Brutality Test
function DeathRateGauge({
  value,
  minTarget = 60,
  maxTarget = 90,
  trajectory
}: {
  value: number | null
  minTarget?: number
  maxTarget?: number
  trajectory: string
}) {
  const displayValue = value ?? 0
  const isOnTarget = value !== null && value >= minTarget && value <= maxTarget
  const isTooHigh = value !== null && value > maxTarget
  const isTooLow = value !== null && value < minTarget
  const hasData = value !== null

  const trajectoryConfig: Record<string, { bg: string; text: string; label: string }> = {
    ON_TARGET: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'ON TARGET' },
    TOO_BRUTAL: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'TOO BRUTAL' },
    TOO_MILD: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'TOO MILD' },
    INSUFFICIENT_DATA: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'INSUFFICIENT DATA' },
    UNKNOWN: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: 'UNKNOWN' },
  }

  const config = trajectoryConfig[trajectory] || trajectoryConfig.UNKNOWN

  return (
    <div className="space-y-3">
      {/* Trajectory Badge */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-400">Death Rate (Test Window)</span>
        <span className={`px-2 py-1 ${config.bg} ${config.text} rounded text-xs font-semibold`}>
          {config.label}
        </span>
      </div>

      {/* Visual Gauge */}
      <div className="relative h-8 bg-gray-800 rounded-lg overflow-hidden">
        {/* Target Zone (60-90%) */}
        <div
          className="absolute h-full bg-green-500/20 border-l border-r border-green-500/50"
          style={{ left: `${minTarget}%`, width: `${maxTarget - minTarget}%` }}
        />

        {/* Labels */}
        <div className="absolute inset-0 flex items-center justify-between px-2 text-xs text-gray-500">
          <span>0%</span>
          <span className="text-green-400/70">{minTarget}-{maxTarget}% target</span>
          <span>100%</span>
        </div>

        {/* Current Value Marker */}
        {hasData && (
          <div
            className={`absolute top-0 bottom-0 w-1 ${
              isOnTarget ? 'bg-green-400' : isTooHigh ? 'bg-red-400' : 'bg-yellow-400'
            }`}
            style={{ left: `${Math.min(100, displayValue)}%` }}
          >
            <div className={`absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full ${
              isOnTarget ? 'bg-green-400' : isTooHigh ? 'bg-red-400' : 'bg-yellow-400'
            }`} />
          </div>
        )}
      </div>

      {/* Value Display */}
      <div className="flex items-center justify-center">
        <span className={`text-3xl font-bold ${
          !hasData ? 'text-gray-500' :
          isOnTarget ? 'text-green-400' :
          isTooHigh ? 'text-red-400' : 'text-yellow-400'
        }`}>
          {hasData ? `${displayValue.toFixed(1)}%` : 'N/A'}
        </span>
      </div>
    </div>
  )
}

function Section({
  title,
  icon: Icon,
  children,
  defaultOpen = false
}: {
  title: string
  icon: any
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="border-t border-gray-700/50 pt-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left text-sm text-gray-400 hover:text-white transition-colors"
      >
        <Icon className="h-4 w-4" />
        <span className="font-medium">{title}</span>
        <ChevronDown className={`h-4 w-4 ml-auto transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div className="mt-3 space-y-3">{children}</div>}
    </div>
  )
}

function InfoRow({ label, value, fallback }: { label: string; value?: string | null; fallback?: string }) {
  const displayValue = value || fallback
  if (!displayValue) return null
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm text-white mt-0.5">{displayValue}</p>
    </div>
  )
}

export function CanonicalTestCard({ test, onActionClick }: CanonicalTestCardProps) {
  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'Not set'
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  // Full timestamp display for CEO-required immutable timestamps
  const formatTimestamp = (dateStr: string) => {
    if (!dateStr) return 'Not set'
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    })
  }

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl overflow-hidden">
      {/* CEO Action Required Banner */}
      {test.ceoActionRequired && (
        <div className="bg-red-500/10 border-b border-red-500/30 px-6 py-3">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="h-5 w-5" />
            <span className="font-semibold">CEO Decision Required</span>
          </div>
          {test.recommendedActions && test.recommendedActions.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {test.recommendedActions.map((action, i) => (
                <button
                  key={i}
                  onClick={() => onActionClick?.(action)}
                  className="px-3 py-1 bg-red-500/20 hover:bg-red-500/30 text-red-300 text-sm rounded transition-colors"
                >
                  {action}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Header - Human-readable test name, no internal IDs */}
      <div className="px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <FlaskConical className="h-5 w-5 text-blue-400 flex-shrink-0" />
              <h3 className="text-lg font-semibold text-white">{test.name}</h3>
            </div>
            <p className="text-sm text-gray-400 mt-1">
              Owner: <span className="text-white">{test.owner}</span>
              {test.monitoringAgent && (
                <> · Monitoring: <span className="text-white">{test.monitoringAgent}</span></>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <StatusBadge status={test.verdict || test.status} ceoActionRequired={test.ceoActionRequired} />
          </div>
        </div>
      </div>

      {/* Timeline - Immutable Timestamps (CEO Mod 2) */}
      <div className="px-6 pb-4">
        <div className="bg-gray-800/50 rounded-lg p-4">
          {/* Explicit Timestamps - First-class fields per CEO requirement */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-700/50">
              <div className="flex items-center gap-2 mb-1">
                <Calendar className="h-4 w-4 text-green-400" />
                <p className="text-xs text-gray-400 font-medium">START (Immutable)</p>
              </div>
              <p className="text-sm text-white font-semibold">{formatTimestamp(test.startDate)}</p>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3 border border-gray-700/50">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="h-4 w-4 text-red-400" />
                <p className="text-xs text-gray-400 font-medium">END (Immutable)</p>
              </div>
              <p className="text-sm text-white font-semibold">{formatTimestamp(test.endDate)}</p>
            </div>
          </div>
          <ProgressBar
            elapsed={test.daysElapsed || 0}
            total={test.requiredDays || 30}
            status={test.verdict || test.status}
          />
        </div>
      </div>

      {/* CEO-DIR-2026-DAY25-SESSION11: Test Progress (Database-Verified) */}
      {test.testProgress && (
        <div className="px-6 pb-4">
          <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/30 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-5 w-5 text-purple-400" />
              <h4 className="font-semibold text-white">Test Progress (Live)</h4>
              <div className="flex items-center gap-1 ml-auto text-xs text-gray-500">
                <Database className="h-3 w-3" />
                <span>DB-Verified: {new Date(test.testProgress.verifiedAt).toLocaleTimeString()}</span>
              </div>
            </div>

            {/* Death Rate Gauge */}
            <DeathRateGauge
              value={test.testProgress.deathRateInWindow}
              minTarget={60}
              maxTarget={90}
              trajectory={test.testProgress.trajectory}
            />

            {/* Window Metrics Grid */}
            <div className="grid grid-cols-4 gap-3 mt-4">
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-white">{test.testProgress.hypothesesInWindow}</p>
                <p className="text-xs text-gray-400 mt-1">In Window</p>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-red-400">{test.testProgress.falsifiedInWindow}</p>
                <p className="text-xs text-gray-400 mt-1">Falsified</p>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-blue-400">{test.testProgress.activeInWindow}</p>
                <p className="text-xs text-gray-400 mt-1">Active</p>
              </div>
              <div className="bg-gray-800/50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-gray-400">{test.testProgress.draftInWindow}</p>
                <p className="text-xs text-gray-400 mt-1">Draft</p>
              </div>
            </div>

            {/* Last Hypothesis Timestamp */}
            {test.testProgress.lastHypothesisInWindow && (
              <div className="mt-4 flex items-center gap-2 text-sm">
                <Clock className="h-4 w-4 text-gray-400" />
                <span className="text-gray-400">Last hypothesis:</span>
                <span className="text-white font-medium">
                  {new Date(test.testProgress.lastHypothesisInWindow).toLocaleString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  })}
                </span>
              </div>
            )}

            {/* CEO Recommendation based on trajectory */}
            {test.testProgress.trajectory === 'TOO_BRUTAL' && (
              <div className="mt-4 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-sm text-red-400">
                  <strong>Recommendation:</strong> Death rate exceeds 90% target. Consider loosening Tier-1 falsification criteria to allow more hypotheses to survive initial testing.
                </p>
              </div>
            )}
            {test.testProgress.trajectory === 'TOO_MILD' && (
              <div className="mt-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                <p className="text-sm text-yellow-400">
                  <strong>Recommendation:</strong> Death rate below 60% target. Consider tightening Tier-1 falsification criteria to filter out low-quality hypotheses.
                </p>
              </div>
            )}
            {test.testProgress.trajectory === 'ON_TARGET' && (
              <div className="mt-4 bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                <p className="text-sm text-green-400">
                  <strong>Status:</strong> Death rate within 60-90% target band. Tier-1 calibration appears optimal.
                </p>
              </div>
            )}
            {test.testProgress.trajectory === 'INSUFFICIENT_DATA' && (
              <div className="mt-4 bg-gray-500/10 border border-gray-500/30 rounded-lg p-3">
                <p className="text-sm text-gray-400">
                  <strong>Note:</strong> No hypotheses have been promoted from DRAFT to ACTIVE status yet. Death rate cannot be calculated until hypotheses are tested.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Collapsible Sections */}
      <div className="px-6 pb-6 space-y-4">
        {/* Purpose & Logic */}
        <Section title="Purpose & Logic" icon={Lightbulb} defaultOpen={true}>
          <InfoRow label="Why are we doing this?" value={test.businessIntent} />
          <InfoRow label="Who benefits if successful?" value={test.beneficiarySystem} />
          <InfoRow
            label="Hypothesis under test"
            value={test.hypothesisCode}
            fallback="System-level validation: Context → Reward causality"
          />
        </Section>

        {/* Measurement */}
        <Section title="Measurement" icon={BarChart3}>
          {test.baselineDefinition && (
            <InfoRow
              label="Baseline (what 'normal' means)"
              value={typeof test.baselineDefinition === 'object'
                ? test.baselineDefinition.beskrivelse || test.baselineDefinition.description || 'Defined'
                : test.baselineDefinition
              }
            />
          )}
          {test.targetMetrics && (
            <InfoRow
              label="Target metrics & expected trajectory"
              value={typeof test.targetMetrics === 'object'
                ? test.targetMetrics.beskrivelse || test.targetMetrics.description || 'Defined'
                : test.targetMetrics
              }
            />
          )}
          <div className="bg-gray-800/30 rounded p-3 mt-2">
            <p className="text-xs text-gray-500 mb-2">Current Status</p>
            <p className="text-sm text-white">
              Day {test.daysElapsed} of {test.requiredDays} — {' '}
              {test.daysElapsed === 0
                ? 'Baseline capture in progress'
                : `${test.daysRemaining} days remaining`
              }
            </p>
          </div>
        </Section>

        {/* Success/Failure Criteria */}
        <Section title="Success & Failure Criteria" icon={Target}>
          {test.successCriteria && (
            <div className="flex items-start gap-2">
              <CheckCircle className="h-4 w-4 text-green-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs text-gray-500">Success if:</p>
                <p className="text-sm text-white">
                  {typeof test.successCriteria === 'object'
                    ? test.successCriteria.beskrivelse || test.successCriteria.description || 'Criteria defined'
                    : test.successCriteria
                  }
                </p>
              </div>
            </div>
          )}
          {test.failureCriteria && (
            <div className="flex items-start gap-2">
              <XCircle className="h-4 w-4 text-red-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs text-gray-500">Failure if:</p>
                <p className="text-sm text-white">
                  {typeof test.failureCriteria === 'object'
                    ? test.failureCriteria.beskrivelse || test.failureCriteria.description || 'Criteria defined'
                    : test.failureCriteria
                  }
                </p>
              </div>
            </div>
          )}
        </Section>

        {/* Governance */}
        <Section title="Governance" icon={Shield}>
          {test.midTestCheckpoint && (
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-purple-400" />
              <div>
                <p className="text-xs text-gray-500">Next Review Checkpoint</p>
                <p className="text-sm text-white">{formatDate(test.midTestCheckpoint)}</p>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2">
            <AlertTriangle className={`h-4 w-4 ${
              test.escalationState === 'ACTION_REQUIRED' ? 'text-red-400' :
              test.escalationState === 'WARNING' ? 'text-yellow-400' :
              'text-gray-400'
            }`} />
            <div>
              <p className="text-xs text-gray-500">Escalation State</p>
              <p className={`text-sm font-medium ${
                test.escalationState === 'ACTION_REQUIRED' ? 'text-red-400' :
                test.escalationState === 'WARNING' ? 'text-yellow-400' :
                'text-green-400'
              }`}>
                {test.escalationState === 'NONE' ? 'No escalation' : test.escalationState}
              </p>
            </div>
          </div>
        </Section>
      </div>
    </div>
  )
}
