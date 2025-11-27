/**
 * Market Data Page (Sprint 1.3)
 * Multi-asset OHLCV charting with indicators
 * Bloomberg-minimal institutional design
 * MBB-grade: Complete integration + lineage
 */

import { Suspense } from 'react'
import { MarketDataClient } from './MarketDataClient'
import { SkeletonCard } from '@/components/ui/Skeleton'

export const revalidate = 300 // Revalidate every 5 minutes

export default async function MarketDataPage() {
  return (
    <div className="space-y-6 fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-display">Market Data</h1>
        <p className="text-slate-600 mt-2">
          Multi-asset OHLCV charts with technical indicators. Bloomberg-grade precision.
        </p>
      </div>

      {/* Market Data Client Component */}
      <Suspense fallback={<SkeletonCard />}>
        <MarketDataClient />
      </Suspense>
    </div>
  )
}
