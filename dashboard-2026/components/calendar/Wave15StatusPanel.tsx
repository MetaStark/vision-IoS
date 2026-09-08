'use client'

/**
 * WAVE15 ALPHA DISCOVERY ENGINE STATUS PANEL
 * ==========================================
 * CEO-DIR-2026-WAVE15-DAEMON-WATCHDOG-001
 *
 * Displays real-time status of the Wave15 Autonomous Golden Needle Hunter.
 * Shows hunts completed, needles found, cost, and operating mode.
 */

import { useState, useEffect } from 'react'

interface Wave15Status {
  status: 'RUNNING' | 'STOPPED'
  lastHeartbeat: string | null
  secondsSinceHeartbeat: number | null
  huntsCompleted: number
  needlesFound: number
  totalCostUsd: number
  mode: string
}

interface Props {
  data: Wave15Status | null
}

export default function Wave15StatusPanel({ data }: Props) {
  const [timeSince, setTimeSince] = useState<string>('')

  useEffect(() => {
    if (!data?.secondsSinceHeartbeat) return

    const updateTimeSince = () => {
      const seconds = data.secondsSinceHeartbeat || 0
      if (seconds < 60) {
        setTimeSince(`${Math.round(seconds)}s ago`)
      } else if (seconds < 3600) {
        setTimeSince(`${Math.round(seconds / 60)}m ago`)
      } else {
        const hours = Math.floor(seconds / 3600)
        const mins = Math.round((seconds % 3600) / 60)
        setTimeSince(`${hours}h ${mins}m ago`)
      }
    }

    updateTimeSince()
    const interval = setInterval(updateTimeSince, 30000)
    return () => clearInterval(interval)
  }, [data?.secondsSinceHeartbeat])

  if (!data) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xl">🎯</span>
          <h3 className="text-white font-semibold">Alpha Discovery Engine</h3>
        </div>
        <div className="text-gray-500 text-sm">Loading Wave15 status...</div>
      </div>
    )
  }

  const isRunning = data.status === 'RUNNING'
  const modeColors: Record<string, string> = {
    'THROTTLED': 'text-yellow-400 bg-yellow-900/30',
    'PRE-HEAT': 'text-orange-400 bg-orange-900/30',
    'FULL': 'text-green-400 bg-green-900/30',
    'UNKNOWN': 'text-gray-400 bg-gray-800',
  }

  return (
    <div className={`bg-gray-900 rounded-lg border ${isRunning ? 'border-purple-900/50' : 'border-red-900/50'}`}>
      {/* Header */}
      <div className={`px-4 py-2 border-b ${isRunning ? 'border-purple-900/30 bg-purple-900/10' : 'border-red-900/30 bg-red-900/10'}`}>
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <span className="text-xl">🎯</span>
            <div>
              <h3 className="text-white font-semibold text-sm">Wave15 Alpha Hunter</h3>
              <p className="text-gray-500 text-xs">EC-018 Golden Needle Discovery</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${modeColors[data.mode] || modeColors['UNKNOWN']}`}>
              {data.mode}
            </span>
            <span className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="p-4 grid grid-cols-4 gap-3">
        {/* Hunts Completed */}
        <div className="text-center">
          <div className="text-2xl font-bold text-white">{data.huntsCompleted}</div>
          <div className="text-xs text-gray-500">Hunts</div>
        </div>

        {/* Golden Needles Found */}
        <div className="text-center">
          <div className="text-2xl font-bold text-amber-400">{data.needlesFound}</div>
          <div className="text-xs text-gray-500">Needles</div>
        </div>

        {/* Cost */}
        <div className="text-center">
          <div className="text-2xl font-bold text-green-400">${data.totalCostUsd.toFixed(4)}</div>
          <div className="text-xs text-gray-500">Cost</div>
        </div>

        {/* Efficiency */}
        <div className="text-center">
          <div className="text-2xl font-bold text-purple-400">
            {data.needlesFound > 0
              ? `$${(data.totalCostUsd / data.needlesFound).toFixed(4)}`
              : '—'
            }
          </div>
          <div className="text-xs text-gray-500">Per Needle</div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-gray-800 bg-gray-950/50">
        <div className="flex justify-between text-xs">
          <span className={`${isRunning ? 'text-green-400' : 'text-red-400'}`}>
            {isRunning ? '● Running' : '○ Stopped'}
          </span>
          <span className="text-gray-500">
            Last heartbeat: {timeSince || 'Never'}
          </span>
        </div>
      </div>
    </div>
  )
}
