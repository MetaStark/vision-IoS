/**
 * Learning Progress Bar - CEO-DIR-2026-057
 * Primary visual showing learning maturity from 0% to 100%
 *
 * Anchors (fixed):
 * - 28% - Pre-FMCL baseline
 * - 80% - Current verified state
 * - 90% - QG-F6 eligible
 * - 100% - Paper trading authorized
 */

'use client'

import { useState, useEffect } from 'react'

interface LearningProgressBarProps {
  currentValue: number
  lastUpdated?: string
}

const ANCHORS = [
  { value: 28, label: 'Baseline', color: 'text-gray-500', description: 'Pre-FMCL' },
  { value: 80, label: 'Verified', color: 'text-blue-400', description: 'Current' },
  { value: 90, label: 'QG-F6', color: 'text-yellow-400', description: 'Eligible' },
  { value: 100, label: 'Paper', color: 'text-green-400', description: 'Authorized' },
]

export function LearningProgressBar({ currentValue, lastUpdated }: LearningProgressBarProps) {
  const [animatedValue, setAnimatedValue] = useState(0)

  useEffect(() => {
    // Animate progress bar on load
    const timer = setTimeout(() => {
      setAnimatedValue(currentValue)
    }, 100)
    return () => clearTimeout(timer)
  }, [currentValue])

  // Determine color based on current value
  const getProgressColor = () => {
    if (currentValue >= 90) return 'bg-green-500'
    if (currentValue >= 80) return 'bg-blue-500'
    if (currentValue >= 50) return 'bg-yellow-500'
    return 'bg-gray-500'
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Learning Maturity - Current Cycle
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            CEO-DIR-2026-057 | Cognitive Observability
          </p>
        </div>
        <div className="text-right">
          <div className="text-3xl font-bold text-white">
            {currentValue}%
          </div>
          {lastUpdated && (
            <p className="text-xs text-gray-500">
              Updated: {lastUpdated}
            </p>
          )}
        </div>
      </div>

      {/* Progress Bar Container */}
      <div className="relative">
        {/* Background track */}
        <div className="h-8 bg-gray-800 rounded-full overflow-hidden relative">
          {/* Animated fill */}
          <div
            className={`h-full ${getProgressColor()} transition-all duration-1000 ease-out rounded-full`}
            style={{ width: `${animatedValue}%` }}
          />

          {/* Anchor markers */}
          {ANCHORS.map((anchor) => (
            <div
              key={anchor.value}
              className="absolute top-0 bottom-0 w-0.5 bg-gray-600"
              style={{ left: `${anchor.value}%` }}
            />
          ))}
        </div>

        {/* Anchor labels */}
        <div className="relative mt-2">
          {ANCHORS.map((anchor) => (
            <div
              key={anchor.value}
              className="absolute transform -translate-x-1/2 text-center"
              style={{ left: `${anchor.value}%` }}
            >
              <div className={`text-xs font-medium ${anchor.color}`}>
                {anchor.value}%
              </div>
              <div className="text-[10px] text-gray-600">
                {anchor.label}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Status indicator */}
      <div className="mt-6 pt-4 border-t border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${getProgressColor()} animate-pulse`} />
            <span className="text-sm text-gray-400">
              {currentValue >= 90 ? 'QG-F6 Eligible' :
               currentValue >= 80 ? 'Learning Verified' :
               currentValue >= 50 ? 'In Progress' : 'Building Foundation'}
            </span>
          </div>
          <div className="text-xs text-gray-600">
            Next milestone: {
              currentValue < 80 ? '80% (Verified)' :
              currentValue < 90 ? '90% (QG-F6)' :
              currentValue < 100 ? '100% (Paper Trading)' : 'Complete'
            }
          </div>
        </div>
      </div>
    </div>
  )
}
