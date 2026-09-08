/**
 * Metacognitive Observability Dashboard
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - Glass Wall Observability
 *
 * "When the system learns - CEO sees. When learning fails - CEO knows."
 *
 * Three simultaneous perspectives:
 * 1. COGNITIVE: Chain-of-Query efficiency, abort rate, CV per regime
 * 2. ECONOMIC: IGR, Scent-to-Gain, EVPI Proxy, Calibration
 * 3. EPISTEMIC: Boundary health, Belief-Policy divergence, Suppressions
 *
 * Plus:
 * - Weekly Learning Pulse (Regret/Wisdom trends)
 * - Audit-Hardening Status (G4+ Compliance)
 */

import { Suspense } from 'react'
import { SkeletonCard } from '@/components/ui/Skeleton'
import {
  CognitivePerspective,
  EconomicPerspective,
  EpistemicPerspective,
  WeeklyLearningPulse,
  AuditHardeningStatus,
  BoardDashboard,
} from '@/components/metacognitive'
import {
  Brain,
  Eye,
  Shield,
  Activity,
  LayoutDashboard,
} from 'lucide-react'

export const revalidate = 5 // 5-second server-side revalidation

export default function MetacognitivePage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div className="pb-6" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg" style={{ backgroundColor: 'hsl(var(--primary))' }}>
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-display">METACOGNITIVE OBSERVABILITY</h1>
            <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              CEO Directive | Glass Wall | Audit-Hardening
            </p>
          </div>
        </div>
        <p className="mt-3 max-w-4xl text-lg font-medium" style={{ color: 'hsl(var(--foreground))' }}>
          "When the system learns — CEO sees. When learning fails — CEO knows."
        </p>
        <p className="mt-2 max-w-3xl" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Three simultaneous perspectives on system learning: Cognitive efficiency, Economic value,
          and Epistemic integrity. Real-time metrics from production database views.
          <strong> No placeholders. No synthetic values. Backend truth only.</strong>
        </p>
        <div className="flex items-center gap-4 mt-4 text-xs" style={{ color: 'hsl(var(--muted-foreground) / 0.7)' }}>
          <span>Authority: ADR-004, ADR-011, ADR-014, ADR-016, IoS-005</span>
          <span>|</span>
          <span>Refresh: 5-10s polling</span>
          <span>|</span>
          <span>Mode: READ-ONLY (Glass Wall)</span>
          <span>|</span>
          <span className="px-2 py-0.5 rounded text-green-400 bg-green-900/30">OBSERVABILITY ACTIVE</span>
        </div>
      </div>

      {/* Board-Grade Dashboard - Primary View */}
      <div className="pb-6" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
        <div className="flex items-center gap-2 mb-4">
          <LayoutDashboard className="w-5 h-5 text-orange-400" />
          <h2 className="text-lg font-bold">BOARD DASHBOARD</h2>
          <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: 'rgba(251, 146, 60, 0.2)', color: 'rgb(251, 146, 60)' }}>
            CEO-DIR-2026-036
          </span>
        </div>
        <Suspense fallback={<SkeletonCard />}>
          <BoardDashboard />
        </Suspense>
      </div>

      {/* Perspective Legend */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))', border: '1px solid hsl(var(--border))' }}>
        <PerspectiveLegend
          icon={<Brain className="w-5 h-5 text-purple-400" />}
          title="1. KOGNITIV"
          description="Chain-of-Query efficiency, abort rate, CV per regime"
          color="rgba(147, 51, 234, 0.3)"
        />
        <PerspectiveLegend
          icon={<Activity className="w-5 h-5 text-green-400" />}
          title="2. OKONOMISK"
          description="IGR, EVPI Proxy, Scent-to-Gain, Calibration"
          color="rgba(34, 197, 94, 0.3)"
        />
        <PerspectiveLegend
          icon={<Shield className="w-5 h-5 text-blue-400" />}
          title="3. EPISTEMISK"
          description="Boundary health, Belief-Policy divergence"
          color="rgba(96, 165, 250, 0.3)"
        />
      </div>

      {/* Three-Perspective Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Suspense fallback={<SkeletonCard />}>
          <CognitivePerspective />
        </Suspense>

        <Suspense fallback={<SkeletonCard />}>
          <EconomicPerspective />
        </Suspense>

        <Suspense fallback={<SkeletonCard />}>
          <EpistemicPerspective />
        </Suspense>
      </div>

      {/* Weekly Learning Pulse - Full Width */}
      <Suspense fallback={<SkeletonCard />}>
        <WeeklyLearningPulse />
      </Suspense>

      {/* Audit-Hardening Status - Full Width */}
      <Suspense fallback={<SkeletonCard />}>
        <AuditHardeningStatus />
      </Suspense>

      {/* Footer */}
      <footer className="pt-6 text-center text-xs" style={{ borderTop: '1px solid hsl(var(--border))', color: 'hsl(var(--muted-foreground) / 0.6)' }}>
        <p>Metacognitive Observability v1.0.0 | CEO Directive 2026-01-09</p>
        <p className="mt-1">
          STIG Meta-Analysis: CV per regime, EVPI Proxy, IGR implemented per technical recommendation.
        </p>
        <p className="mt-1">
          Source Views: v_chain_of_query_efficiency, v_regime_variance_metrics, v_information_gain_ratio,
          mv_evpi_proxy, v_audit_hardening_status, weekly_learning_metrics
        </p>
      </footer>
    </div>
  )
}

function PerspectiveLegend({
  icon,
  title,
  description,
  color,
}: {
  icon: React.ReactNode
  title: string
  description: string
  color: string
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg" style={{ backgroundColor: color }}>
      <div className="p-2 rounded-lg" style={{ backgroundColor: 'hsl(var(--background))' }}>
        {icon}
      </div>
      <div>
        <span className="font-semibold text-sm" style={{ color: 'hsl(var(--foreground))' }}>{title}</span>
        <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{description}</p>
      </div>
    </div>
  )
}
