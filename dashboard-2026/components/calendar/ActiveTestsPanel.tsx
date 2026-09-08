/**
 * Active Tests Panel - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Section 3: Canonical Test Event Schema display.
 * Tests must explain themselves without CEO archaeology.
 */

'use client'

import { useState } from 'react'
import { FlaskConical, Clock, Users, TrendingUp, TrendingDown, Minus, ChevronDown, Target, CheckCircle, XCircle, AlertTriangle, Link2 } from 'lucide-react'

interface ActiveTest {
  name: string
  code: string
  owner: string
  status: string
  daysElapsed: number
  daysRemaining: number
  currentSamples: number
  targetSamples: number
  sampleStatus: string
  category: string
  // Section 3 required fields
  businessIntent?: string
  beneficiarySystem?: string
  baselineDefinition?: any
  targetMetrics?: any
  expectedTrajectory?: any
  hypothesisCode?: string
  successCriteria?: any
  failureCriteria?: any
  escalationRules?: any
  midTestCheckpoint?: string
  outcome?: string
  startDate?: string
  endDate?: string
}

interface ActiveTestsPanelProps {
  tests: ActiveTest[]
}

function TestCard({ test }: { test: ActiveTest }) {
  const [expanded, setExpanded] = useState(false)
  const progress = test.daysElapsed / (test.daysElapsed + test.daysRemaining) * 100
  const sampleProgress = (test.currentSamples / test.targetSamples) * 100

  return (
    <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
      {/* Test Header */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <h4 className="font-medium text-white">{test.name}</h4>
          <p className="text-xs text-gray-500 mt-0.5">{test.code}</p>
        </div>
        <span
          className={`px-2 py-1 rounded text-xs font-medium ${
            test.status === 'ACTIVE'
              ? 'bg-green-500/20 text-green-400'
              : 'bg-yellow-500/20 text-yellow-400'
          }`}
        >
          {test.status}
        </span>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div className="flex items-center gap-2">
          <Users className="h-4 w-4 text-gray-500" />
          <div>
            <p className="text-xs text-gray-500">Owner</p>
            <p className="text-sm text-white font-mono">{test.owner}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-gray-500" />
          <div>
            <p className="text-xs text-gray-500">Timeline</p>
            <p className="text-sm text-white">
              Day {test.daysElapsed}/{test.daysElapsed + test.daysRemaining}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {test.sampleStatus === 'AHEAD' ? (
            <TrendingUp className="h-4 w-4 text-green-400" />
          ) : test.sampleStatus === 'BEHIND' ? (
            <TrendingDown className="h-4 w-4 text-red-400" />
          ) : (
            <Minus className="h-4 w-4 text-gray-400" />
          )}
          <div>
            <p className="text-xs text-gray-500">Samples</p>
            <p className="text-sm text-white">
              {test.currentSamples}/{test.targetSamples}
            </p>
          </div>
        </div>
      </div>

      {/* Progress Bars */}
      <div className="space-y-2">
        {/* Time Progress */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">Time Progress</span>
            <span className="text-gray-400">{Math.round(progress)}%</span>
          </div>
          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Sample Progress */}
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">Sample Progress</span>
            <span
              className={
                test.sampleStatus === 'BEHIND'
                  ? 'text-red-400'
                  : test.sampleStatus === 'AHEAD'
                  ? 'text-green-400'
                  : 'text-gray-400'
              }
            >
              {Math.round(sampleProgress)}%
            </span>
          </div>
          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                test.sampleStatus === 'BEHIND'
                  ? 'bg-red-500'
                  : test.sampleStatus === 'AHEAD'
                  ? 'bg-green-500'
                  : 'bg-gray-500'
              }`}
              style={{ width: `${Math.min(sampleProgress, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Business Context Section (Section 3 Required) */}
      <div className="mt-4 pt-4 border-t border-gray-700/50">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors w-full"
        >
          <ChevronDown className={`h-4 w-4 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          <span>Business Context (Section 3)</span>
          {test.hypothesisCode && (
            <span className="ml-auto flex items-center gap-1 text-xs text-purple-400">
              <Link2 className="h-3 w-3" />
              {test.hypothesisCode}
            </span>
          )}
        </button>

        {expanded && (
          <div className="mt-4 space-y-4">
            {/* Business Intent */}
            {test.businessIntent && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Target className="h-3 w-3 text-blue-400" />
                  <p className="text-xs text-gray-500">Why are we doing this?</p>
                </div>
                <p className="text-sm text-white pl-5">{test.businessIntent}</p>
              </div>
            )}

            {/* Beneficiary System */}
            {test.beneficiarySystem && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Users className="h-3 w-3 text-green-400" />
                  <p className="text-xs text-gray-500">Who benefits if successful?</p>
                </div>
                <p className="text-sm text-white pl-5">{test.beneficiarySystem}</p>
              </div>
            )}

            {/* Success Criteria */}
            {test.successCriteria && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle className="h-3 w-3 text-green-400" />
                  <p className="text-xs text-gray-500">Success Criteria</p>
                </div>
                <pre className="text-xs text-gray-400 bg-gray-900/50 rounded p-2 ml-5 overflow-auto max-h-24">
                  {typeof test.successCriteria === 'object'
                    ? JSON.stringify(test.successCriteria, null, 2)
                    : test.successCriteria}
                </pre>
              </div>
            )}

            {/* Failure Criteria */}
            {test.failureCriteria && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <XCircle className="h-3 w-3 text-red-400" />
                  <p className="text-xs text-gray-500">Failure Criteria</p>
                </div>
                <pre className="text-xs text-gray-400 bg-gray-900/50 rounded p-2 ml-5 overflow-auto max-h-24">
                  {typeof test.failureCriteria === 'object'
                    ? JSON.stringify(test.failureCriteria, null, 2)
                    : test.failureCriteria}
                </pre>
              </div>
            )}

            {/* Escalation Rules */}
            {test.escalationRules && (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className="h-3 w-3 text-yellow-400" />
                  <p className="text-xs text-gray-500">Escalation Rules</p>
                </div>
                <pre className="text-xs text-gray-400 bg-gray-900/50 rounded p-2 ml-5 overflow-auto max-h-24">
                  {typeof test.escalationRules === 'object'
                    ? JSON.stringify(test.escalationRules, null, 2)
                    : test.escalationRules}
                </pre>
              </div>
            )}

            {/* Baseline Definition */}
            {test.baselineDefinition && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Baseline Definition (what "normal" means)</p>
                <pre className="text-xs text-gray-400 bg-gray-900/50 rounded p-2 overflow-auto max-h-24">
                  {typeof test.baselineDefinition === 'object'
                    ? JSON.stringify(test.baselineDefinition, null, 2)
                    : test.baselineDefinition}
                </pre>
              </div>
            )}

            {/* Target Metrics */}
            {test.targetMetrics && (
              <div>
                <p className="text-xs text-gray-500 mb-1">Target Metrics</p>
                <pre className="text-xs text-gray-400 bg-gray-900/50 rounded p-2 overflow-auto max-h-24">
                  {typeof test.targetMetrics === 'object'
                    ? JSON.stringify(test.targetMetrics, null, 2)
                    : test.targetMetrics}
                </pre>
              </div>
            )}

            {/* Mid-Test Checkpoint */}
            {test.midTestCheckpoint && (
              <div className="flex items-center gap-2 text-xs">
                <Clock className="h-3 w-3 text-purple-400" />
                <span className="text-gray-500">Mid-Test Review:</span>
                <span className="text-white">
                  {new Date(test.midTestCheckpoint).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function ActiveTestsPanel({ tests }: ActiveTestsPanelProps) {
  if (tests.length === 0) {
    return (
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <FlaskConical className="h-5 w-5 text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Active Tests</h3>
        </div>
        <p className="text-gray-500 text-sm">No active tests currently running.</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <FlaskConical className="h-5 w-5 text-blue-400" />
        <h3 className="text-lg font-semibold text-white">Active Tests</h3>
        <span className="ml-auto px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded-full text-xs font-medium">
          {tests.length} active
        </span>
      </div>

      <div className="space-y-4">
        {tests.map((test) => (
          <TestCard key={test.code} test={test} />
        ))}
      </div>
    </div>
  )
}
