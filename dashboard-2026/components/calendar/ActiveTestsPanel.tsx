/**
 * Active Tests Panel - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Section 3: Canonical Test Event Schema display.
 * Tests must explain themselves without CEO archaeology.
 */

'use client'

import { FlaskConical, Clock, Users, TrendingUp, TrendingDown, Minus } from 'lucide-react'

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
}

interface ActiveTestsPanelProps {
  tests: ActiveTest[]
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
        {tests.map((test) => {
          const progress = test.daysElapsed / (test.daysElapsed + test.daysRemaining) * 100
          const sampleProgress = (test.currentSamples / test.targetSamples) * 100

          return (
            <div
              key={test.code}
              className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50"
            >
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
            </div>
          )
        })}
      </div>
    </div>
  )
}
