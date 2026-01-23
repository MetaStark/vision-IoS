/**
 * Dashboard 2026 - Main Page
 * Three-Zone Layout: Hero Panel → Signal Grid → Indicator Matrix
 *
 * Authority: Dashboard UX Specification 2026 v2.0, FINN Voice Guidelines v1.0
 * North Star: 3-30-3 Framework
 * - 3 seconds: CIO Understanding (Hero Panel)
 * - 30 seconds: Narrative Completion (Signal Grid)
 * - 3 minutes: Full Diagnostic (Indicator Matrix)
 *
 * Design: Bloomberg 2026, not Tableau 2020
 * - Minimalist black/charcoal theme
 * - Semantic color system (green/red/blue/yellow)
 * - 1px glow on hover
 * - Soft easing 150ms
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import { HeroPanel } from '@/components/dashboard/HeroPanel'
import { SignalGrid } from '@/components/dashboard/SignalGrid'
import { IndicatorMatrix } from '@/components/dashboard/IndicatorMatrix'
import { ACITrianglePanel } from '@/components/dashboard/ACITrianglePanel'
import { RefreshCw, Play, Pause } from 'lucide-react'

// Auto-refresh configuration
const REFRESH_INTERVAL_MS = 30000 // 30 seconds
const REFRESH_INTERVALS = [
  { label: '15s', value: 15000 },
  { label: '30s', value: 30000 },
  { label: '1m', value: 60000 },
  { label: '5m', value: 300000 },
  { label: 'Off', value: 0 },
]

export default function DashboardPage() {
  const [listingId, setListingId] = useState('LST_BTC_XCRYPTO')
  const [lastRefresh, setLastRefresh] = useState(new Date())
  const [mounted, setMounted] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshInterval, setRefreshInterval] = useState(REFRESH_INTERVAL_MS)
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL_MS / 1000)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Only show timestamp on client-side to avoid hydration mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  // Manual refresh handler
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    setRefreshKey(prev => prev + 1)
    setLastRefresh(new Date())
    setCountdown(refreshInterval / 1000)
    // Brief visual feedback
    setTimeout(() => setIsRefreshing(false), 500)
  }, [refreshInterval])

  // Auto-refresh effect
  useEffect(() => {
    if (!autoRefresh || refreshInterval === 0) return

    const interval = setInterval(() => {
      handleRefresh()
    }, refreshInterval)

    return () => clearInterval(interval)
  }, [autoRefresh, refreshInterval, handleRefresh])

  // Countdown timer
  useEffect(() => {
    if (!autoRefresh || refreshInterval === 0) return

    const ticker = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) return refreshInterval / 1000
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(ticker)
  }, [autoRefresh, refreshInterval])

  // Reset countdown when interval changes
  useEffect(() => {
    setCountdown(refreshInterval / 1000)
  }, [refreshInterval])

  return (
    <div className="min-h-screen bg-black">
      {/* Top navigation bar */}
      <div className="border-b border-gray-800 bg-gray-950/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-[1800px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Left: Brand */}
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-bold text-white">
                FjordHQ <span className="text-gray-600">|</span>{' '}
                <span className="text-blue-400">FINN Intelligence</span>
              </h1>
              <div className="text-xs text-gray-600">
                Dashboard 2026 · ACE Alpha System
              </div>
            </div>

            {/* Right: Controls */}
            <div className="flex items-center gap-4">
              {/* Asset selector (future multi-asset support) */}
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500 uppercase tracking-wide">
                  Asset
                </label>
                <select
                  value={listingId}
                  onChange={(e) => setListingId(e.target.value)}
                  className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-300 focus:outline-none focus:border-blue-600"
                >
                  <option value="LST_BTC_XCRYPTO">BTC-USD</option>
                  {/* Future: ETH, SOL, SPX, etc. */}
                  <option value="LST_ETH_XCRYPTO" disabled>
                    ETH-USD (Coming soon)
                  </option>
                  <option value="LST_SOL_XCRYPTO" disabled>
                    SOL-USD (Coming soon)
                  </option>
                </select>
              </div>

              {/* Auto-refresh controls */}
              <div className="flex items-center gap-2 border-l border-gray-800 pl-4">
                {/* Auto-refresh toggle */}
                <button
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-xs transition-colors ${
                    autoRefresh
                      ? 'bg-green-900/50 text-green-400 border border-green-800'
                      : 'bg-gray-900 text-gray-500 border border-gray-700'
                  }`}
                  title={autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
                >
                  {autoRefresh ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
                  Auto
                </button>

                {/* Interval selector */}
                <select
                  value={refreshInterval}
                  onChange={(e) => setRefreshInterval(Number(e.target.value))}
                  className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-400 focus:outline-none focus:border-blue-600"
                >
                  {REFRESH_INTERVALS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>

                {/* Countdown */}
                {autoRefresh && refreshInterval > 0 && (
                  <div className="text-xs text-gray-500 tabular-nums w-8">
                    {countdown}s
                  </div>
                )}
              </div>

              {/* Manual refresh button */}
              <button
                onClick={handleRefresh}
                disabled={isRefreshing}
                className={`flex items-center gap-2 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-800 hover:border-gray-600 transition-colors ${
                  isRefreshing ? 'opacity-50' : ''
                }`}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                Refresh
              </button>

              {/* Last update */}
              <div className="text-xs text-gray-600">
                {mounted ? `Updated: ${lastRefresh.toLocaleTimeString()}` : 'Loading...'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main content: Three-zone layout */}
      <div className="max-w-[1800px] mx-auto px-6 py-8 space-y-8">
        {/* ZONE 1: Hero Panel (3-second understanding) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-blue-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Zone 1: What's Happening Now? (3 seconds)
            </h2>
          </div>
          <HeroPanel listingId={listingId} refreshKey={refreshKey} />
        </section>

        {/* ZONE 2: Signal Grid (30-second comprehension) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-green-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Zone 2: Why Is This Happening? (30 seconds)
            </h2>
          </div>
          <SignalGrid listingId={listingId} refreshKey={refreshKey} />
        </section>

        {/* ZONE 3: Indicator Matrix (3-minute verification) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-yellow-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Zone 3: How Can I Verify This? (3 minutes)
            </h2>
          </div>
          <IndicatorMatrix listingId={listingId} refreshKey={refreshKey} />
        </section>

        {/* ZONE 4: ACI Constraint Triangle (Governance) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-purple-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Zone 4: Cognitive Governance (ACI Triangle)
            </h2>
          </div>
          <ACITrianglePanel refreshKey={refreshKey} />
        </section>

        {/* Footer */}
        <footer className="border-t border-gray-900 pt-8 pb-4">
          <div className="flex items-center justify-between text-xs text-gray-600">
            <div className="flex items-center gap-4">
              <span>© 2025 FjordHQ Technical Officer</span>
              <span className="text-gray-800">|</span>
              <span>ACE Phase 0-6 Operational</span>
              <span className="text-gray-800">|</span>
              <span>FINN Intelligence v1.0</span>
            </div>
            <div className="flex items-center gap-4">
              <a
                href="/docs/Dashboard_UX_Specification_2026.md"
                className="hover:text-blue-400 transition-colors"
              >
                UX Spec
              </a>
              <a
                href="/docs/FINN_Voice_Guidelines.md"
                className="hover:text-blue-400 transition-colors"
              >
                FINN Voice
              </a>
              <a
                href="/docs/Dashboard_Executive_Narrative.md"
                className="hover:text-blue-400 transition-colors"
              >
                Executive Summary
              </a>
            </div>
          </div>

          {/* Brand promise */}
          <div className="mt-6 text-center">
            <div className="text-sm text-gray-500 italic">
              "FINN speaks like your most trusted analyst - direct, contextual, and always verifiable."
            </div>
            <div className="text-xs text-gray-700 mt-2">
              Authority: ADR-042 (FINN Intelligence), ADR-045 (Dashboard Integration)
            </div>
          </div>
        </footer>
      </div>
    </div>
  )
}
