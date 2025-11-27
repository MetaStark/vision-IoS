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

import { useState, useEffect } from 'react'
import { HeroPanel } from '@/components/dashboard/HeroPanel'
import { SignalGrid } from '@/components/dashboard/SignalGrid'
import { IndicatorMatrix } from '@/components/dashboard/IndicatorMatrix'
import { RefreshCw } from 'lucide-react'

export default function DashboardPage() {
  const [listingId, setListingId] = useState('LST_BTC_XCRYPTO')
  const [lastRefresh, setLastRefresh] = useState(new Date())
  const [mounted, setMounted] = useState(false)

  // Only show timestamp on client-side to avoid hydration mismatch
  useEffect(() => {
    setMounted(true)
  }, [])

  const handleRefresh = () => {
    setLastRefresh(new Date())
    // Force re-render of all components by changing key
    window.location.reload()
  }

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

              {/* Refresh button */}
              <button
                onClick={handleRefresh}
                className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-800 hover:border-gray-600 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
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
          <HeroPanel listingId={listingId} />
        </section>

        {/* ZONE 2: Signal Grid (30-second comprehension) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-green-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Zone 2: Why Is This Happening? (30 seconds)
            </h2>
          </div>
          <SignalGrid listingId={listingId} />
        </section>

        {/* ZONE 3: Indicator Matrix (3-minute verification) */}
        <section>
          <div className="mb-3 flex items-center gap-2">
            <div className="h-1 w-1 rounded-full bg-yellow-500" />
            <h2 className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
              Zone 3: How Can I Verify This? (3 minutes)
            </h2>
          </div>
          <IndicatorMatrix listingId={listingId} />
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
