/**
 * Dual Progress Bars - CEO-DIR-2026-058
 *
 * CRITICAL DISTINCTION:
 * - System Maturity: FMCL, safety gates, governance (can reach 100%)
 * - Market Learning: Holdout performance improvement (starts at 0%)
 *
 * Per CEO-DIR-2026-058: "Learning Maturity = 100%" was conceptually wrong.
 * Now correctly split into two separate tracks.
 */

'use client'

import { useState, useEffect } from 'react'
import { Shield, Brain, Lock, AlertTriangle } from 'lucide-react'

interface DualProgressBarProps {
  systemMaturity: number
  marketLearning: number
  marketLearningStatus: string
  labelLocked: boolean
  holdoutFrozen: boolean
  holdoutVerified: boolean
  lastUpdated?: string
}

const SYSTEM_ANCHORS = [
  { value: 28, label: 'Baseline', color: 'text-gray-500' },
  { value: 80, label: 'Verified', color: 'text-blue-400' },
  { value: 90, label: 'QG-F6', color: 'text-yellow-400' },
  { value: 100, label: 'Ready', color: 'text-green-400' },
]

const LEARNING_ANCHORS = [
  { value: 0, label: 'Baseline', color: 'text-gray-500' },
  { value: 25, label: '1 Δ', color: 'text-blue-400' },
  { value: 50, label: '2 Δ', color: 'text-yellow-400' },
  { value: 100, label: 'Proven', color: 'text-green-400' },
]

// Legacy export for backwards compatibility
export function LearningProgressBar({
  currentValue,
  lastUpdated
}: {
  currentValue: number
  lastUpdated?: string
}) {
  // Render just system maturity if using old interface
  return (
    <DualProgressBars
      systemMaturity={currentValue}
      marketLearning={0}
      marketLearningStatus="BLOCKED: Legacy view"
      labelLocked={false}
      holdoutFrozen={false}
      holdoutVerified={false}
      lastUpdated={lastUpdated}
    />
  )
}

export function DualProgressBars({
  systemMaturity,
  marketLearning,
  marketLearningStatus,
  labelLocked,
  holdoutFrozen,
  holdoutVerified,
  lastUpdated,
}: DualProgressBarProps) {
  const [animatedSystem, setAnimatedSystem] = useState(0)
  const [animatedLearning, setAnimatedLearning] = useState(0)

  useEffect(() => {
    const timer = setTimeout(() => {
      setAnimatedSystem(systemMaturity)
      setAnimatedLearning(marketLearning)
    }, 100)
    return () => clearTimeout(timer)
  }, [systemMaturity, marketLearning])

  const getSystemColor = () => {
    if (systemMaturity >= 90) return 'bg-green-500'
    if (systemMaturity >= 80) return 'bg-blue-500'
    if (systemMaturity >= 50) return 'bg-yellow-500'
    return 'bg-gray-500'
  }

  const getLearningColor = () => {
    if (marketLearning > 0) return 'bg-purple-500'
    return 'bg-gray-700'
  }

  const isBlocked = !labelLocked || !holdoutFrozen || !holdoutVerified

  return (
    <div className="space-y-6">
      {/* System Maturity (formerly "Learning Maturity") */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Shield className="h-5 w-5 text-blue-400" />
            <div>
              <h3 className="text-lg font-semibold text-white">
                System Maturity
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                FMCL • Safety Gates • Governance Integrity
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-white">
              {systemMaturity}%
            </div>
            <p className="text-xs text-gray-500">
              CEO-DIR-2026-052–056
            </p>
          </div>
        </div>

        {/* System Progress Bar */}
        <div className="relative">
          <div className="h-6 bg-gray-800 rounded-full overflow-hidden relative">
            <div
              className={`h-full ${getSystemColor()} transition-all duration-1000 ease-out rounded-full`}
              style={{ width: `${animatedSystem}%` }}
            />
            {SYSTEM_ANCHORS.map((anchor) => (
              <div
                key={anchor.value}
                className="absolute top-0 bottom-0 w-0.5 bg-gray-600"
                style={{ left: `${anchor.value}%` }}
              />
            ))}
          </div>
          <div className="relative mt-2">
            {SYSTEM_ANCHORS.map((anchor) => (
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
      </div>

      {/* Market Learning (NEW - CEO-DIR-2026-058) */}
      <div className={`bg-gray-900 border rounded-lg p-6 ${isBlocked ? 'border-yellow-500/50' : 'border-gray-800'}`}>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Brain className="h-5 w-5 text-purple-400" />
            <div>
              <h3 className="text-lg font-semibold text-white">
                Market Learning
              </h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Holdout Performance • Out-of-Sample Skill
              </p>
            </div>
          </div>
          <div className="text-right">
            <div className={`text-3xl font-bold ${marketLearning > 0 ? 'text-purple-400' : 'text-gray-500'}`}>
              {marketLearning}%
            </div>
            <p className="text-xs text-gray-500">
              CEO-DIR-2026-058
            </p>
          </div>
        </div>

        {/* Prerequisites Check */}
        <div className="mb-4 p-3 bg-gray-800/50 rounded-lg">
          <div className="text-xs text-gray-400 mb-2">Prerequisites:</div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              {labelLocked ? (
                <Lock className="h-3.5 w-3.5 text-green-400" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" />
              )}
              <span className={`text-xs ${labelLocked ? 'text-green-400' : 'text-yellow-400'}`}>
                Label Locked
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              {holdoutFrozen ? (
                <Lock className="h-3.5 w-3.5 text-green-400" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" />
              )}
              <span className={`text-xs ${holdoutFrozen ? 'text-green-400' : 'text-yellow-400'}`}>
                Holdout Frozen
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              {holdoutVerified ? (
                <Lock className="h-3.5 w-3.5 text-green-400" />
              ) : (
                <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" />
              )}
              <span className={`text-xs ${holdoutVerified ? 'text-green-400' : 'text-yellow-400'}`}>
                Isolation Verified
              </span>
            </div>
          </div>
        </div>

        {/* Learning Progress Bar */}
        <div className="relative">
          <div className="h-6 bg-gray-800 rounded-full overflow-hidden relative">
            <div
              className={`h-full ${getLearningColor()} transition-all duration-1000 ease-out rounded-full`}
              style={{ width: `${animatedLearning}%` }}
            />
            {LEARNING_ANCHORS.map((anchor) => (
              <div
                key={anchor.value}
                className="absolute top-0 bottom-0 w-0.5 bg-gray-600"
                style={{ left: `${anchor.value}%` }}
              />
            ))}
          </div>
          <div className="relative mt-2">
            {LEARNING_ANCHORS.map((anchor) => (
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

        {/* Status Label */}
        <div className="mt-4 pt-3 border-t border-gray-800">
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full ${isBlocked ? 'bg-yellow-500' : marketLearning > 0 ? 'bg-purple-500 animate-pulse' : 'bg-gray-600'}`} />
            <span className="text-sm text-gray-400">
              {marketLearningStatus}
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      {lastUpdated && (
        <div className="text-xs text-gray-600 text-right">
          Updated: {lastUpdated}
        </div>
      )}
    </div>
  )
}
