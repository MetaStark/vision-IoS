/**
 * Cinematic Visual Engine Page
 * ADR-022/023/024: Retail Observer Cinematic Engine
 *
 * Authority: STIG (CTO) per EC-003
 * Classification: READ-ONLY
 */

import { Suspense } from 'react'
import { Clapperboard, RefreshCw, AlertCircle, Activity } from 'lucide-react'
import { CinematicViewer } from '@/components/cinematic/CinematicViewer'

export const revalidate = 10

export default function CinematicPage() {
  return (
    <div className="space-y-6 fade-in">
      {/* Page Header */}
      <div className="border-b pb-6" style={{ borderColor: 'hsl(var(--border))' }}>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg" style={{ backgroundColor: 'hsl(280 60% 50%)' }}>
            <Clapperboard className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'hsl(var(--foreground))' }}>
              Visual Cinematic Engine
            </h1>
            <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              ADR-022/023/024 — Dumb Glass Frontend Architecture
            </p>
          </div>
        </div>
        <p className="mt-3 max-w-3xl" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Real-time market visualization using pre-computed Visual State Vectors (VSV).
          All animation parameters are deterministically mapped from indicator data and
          signed by the backend for audit compliance.
        </p>
        <div className="flex items-center gap-4 mt-4 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          <span>Authority: ADR-022, ADR-023, ADR-024</span>
          <span>|</span>
          <span>Mode: READ-ONLY</span>
          <span>|</span>
          <span>Schema: vision_cinematic</span>
        </div>
      </div>

      {/* Main Content */}
      <Suspense fallback={<CinematicSkeleton />}>
        <CinematicViewer />
      </Suspense>
    </div>
  )
}

function CinematicSkeleton() {
  return (
    <div className="space-y-6">
      {/* Controls Skeleton */}
      <div
        className="p-4 rounded-lg animate-pulse"
        style={{ backgroundColor: 'hsl(var(--card))' }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div
              className="h-10 w-40 rounded"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            />
            <div
              className="h-10 w-32 rounded"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            />
          </div>
          <div className="flex items-center gap-2">
            <div
              className="h-6 w-24 rounded-full"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            />
          </div>
        </div>
      </div>

      {/* Canvas Skeleton */}
      <div
        className="rounded-lg overflow-hidden animate-pulse"
        style={{
          backgroundColor: 'hsl(var(--card))',
          aspectRatio: '16/9',
          minHeight: '400px',
        }}
      >
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-center">
            <RefreshCw
              className="w-12 h-12 mx-auto animate-spin"
              style={{ color: 'hsl(var(--muted-foreground))' }}
            />
            <p className="mt-4 text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Loading Visual State Vector...
            </p>
          </div>
        </div>
      </div>

      {/* Metrics Skeleton */}
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-4 rounded-lg animate-pulse"
            style={{ backgroundColor: 'hsl(var(--card))' }}
          >
            <div
              className="h-4 w-20 rounded mb-2"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            />
            <div
              className="h-8 w-16 rounded"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            />
          </div>
        ))}
      </div>
    </div>
  )
}
