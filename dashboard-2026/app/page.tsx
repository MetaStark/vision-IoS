/**
 * FjordHQ Command Center (FCC) - Root Overview Page
 * CEO Directive 2026-FHQ-FCC-AOL-01
 *
 * Authority: ADR-001, ADR-004, ADR-006, ADR-009, ADR-013, ADR-018, ADR-019
 * Classification: CONSTITUTIONAL - Glass Wall Observability Layer
 *
 * This is the authoritative root entrypoint for CEO situational awareness.
 * READ-ONLY: Observes but does not modify system behavior.
 */

import { Suspense } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { ADROverview } from '@/components/fcc/ADROverview'
import { IoSOverview } from '@/components/fcc/IoSOverview'
import { GovernanceDeviations } from '@/components/fcc/GovernanceDeviations'
import { ModuleUnavailable } from '@/components/ModuleErrorBoundary'
import {
  getADRRegistry,
  getADRSummary,
  getIoSRegistry,
  getIoSSummary,
  getGovernanceDeviations,
} from '@/lib/fcc/queries'
import { safeAsync } from '@/lib/db'
import { Shield, Layers, Activity, AlertTriangle, Eye, Network, Cpu } from 'lucide-react'
import Link from 'next/link'

export const revalidate = 10

export default async function FCCOverviewPage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-slate-900 rounded-lg">
            <Eye className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-display">FjordHQ Command Center</h1>
            <p className="text-sm text-slate-500">
              Glass Wall Observability Layer | CEO Directive 2026
            </p>
          </div>
        </div>
        <p className="mt-3 text-slate-600 max-w-3xl">
          Total transparency without friction. This is the CEO's foundation view into all ADRs,
          IoS modules, agent activity, and governance deviations. Read-only observation of the
          autonomous system's internal state.
        </p>
        <div className="flex items-center gap-4 mt-4 text-xs text-slate-500">
          <span>Authority: CEO Directive 2026</span>
          <span>|</span>
          <span>Compliance: ADR-001, ADR-013, ADR-019</span>
          <span>|</span>
          <span>Mode: READ-ONLY</span>
        </div>
      </div>

      {/* Primary Navigation - AOL is AUTHORITATIVE for agent/system status */}
      <div className="p-4 rounded-lg" style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
        <Link
          href="/aol"
          className="flex items-center justify-between p-4 rounded-lg hover:bg-blue-900/20 transition-colors"
        >
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-600 rounded-lg">
              <Cpu className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold text-slate-100">Agent Observability Layer</span>
                <span className="px-2 py-0.5 text-xs font-semibold bg-blue-600 text-white rounded-full">
                  AUTHORITATIVE
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-1">
                System Status (DEFCON, ACI, Regime, Strategy, CEIO) + Agent Telemetry (ARS, CSI, RBR, GII)
              </p>
            </div>
          </div>
          <Activity className="w-5 h-5 text-blue-400" />
        </Link>
      </div>

      {/* Secondary Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <QuickLink
          href="/research"
          icon={<Network className="w-5 h-5" />}
          label="Causal Topology"
          description="Alpha Graph visualization"
        />
        <QuickLink
          href="#adrs"
          icon={<Shield className="w-5 h-5" />}
          label="ADR Registry"
          description="21 ADRs registered"
        />
        <QuickLink
          href="#ios"
          icon={<Layers className="w-5 h-5" />}
          label="IoS Modules"
          description="18 modules active"
        />
      </div>

      {/* Navigation Tabs */}
      <nav className="flex gap-2 border-b border-slate-200 pb-2">
        <TabLink href="#adrs" icon={<Shield className="w-4 h-4" />} label="ADR Registry" />
        <TabLink href="#ios" icon={<Layers className="w-4 h-4" />} label="IoS Modules" />
        <TabLink href="#deviations" icon={<AlertTriangle className="w-4 h-4" />} label="Deviations" />
      </nav>

      {/* ADR Registry Section */}
      <section id="adrs">
        <SectionHeader
          title="ADR Registry"
          subtitle="All Architecture Decision Records with governance tier, status, and VEGA attestation"
          icon={<Shield className="w-5 h-5" />}
        />
        <Suspense fallback={<SkeletonCard />}>
          <ADRSection />
        </Suspense>
      </section>

      {/* IoS Modules Section */}
      <section id="ios">
        <SectionHeader
          title="IoS Module Registry"
          subtitle="Intelligence Operating System modules with runtime status, dependencies, and governance gates"
          icon={<Layers className="w-5 h-5" />}
        />
        <Suspense fallback={<SkeletonCard />}>
          <IoSSection />
        </Suspense>
      </section>

      {/* Governance Deviations Section */}
      <section id="deviations">
        <SectionHeader
          title="Governance Deviations"
          subtitle="Active and resolved governance violations, signature mismatches, and audit gaps"
          icon={<AlertTriangle className="w-5 h-5" />}
        />
        <Suspense fallback={<SkeletonCard />}>
          <DeviationsSection />
        </Suspense>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 pt-6 text-center text-xs text-slate-400">
        <p>FjordHQ Command Center v2.0.0 | Glass Wall Architecture | CEO Directive 2026</p>
        <p className="mt-1">
          This dashboard is read-only. All autonomy is preserved. No system behavior modifications.
        </p>
      </footer>
    </div>
  )
}

// ============================================================================
// Data Fetching Sections with Graceful Degradation
// CD-EXEC-PERMANENT-UPTIME: Module failures must not crash dashboard
// ============================================================================

async function ADRSection() {
  try {
    const [adrs, summary] = await Promise.all([
      getADRRegistry(),
      getADRSummary(),
    ])
    return <ADROverview adrs={adrs} summary={summary} />
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    console.error('[ADR-SECTION] Failed:', msg)
    return <ModuleUnavailable moduleName="ADR Registry" error={msg} />
  }
}

async function IoSSection() {
  try {
    const [modules, summary] = await Promise.all([
      getIoSRegistry(),
      getIoSSummary(),
    ])
    return <IoSOverview modules={modules} summary={summary} />
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    console.error('[IOS-SECTION] Failed:', msg)
    return <ModuleUnavailable moduleName="IoS Module Registry" error={msg} />
  }
}

async function DeviationsSection() {
  try {
    const deviations = await getGovernanceDeviations()
    return <GovernanceDeviations deviations={deviations} />
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    console.error('[DEVIATIONS-SECTION] Failed:', msg)
    return <ModuleUnavailable moduleName="Governance Deviations" error={msg} />
  }
}

// ============================================================================
// UI Components
// ============================================================================

function SectionHeader({
  title,
  subtitle,
  icon,
}: {
  title: string
  subtitle: string
  icon: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-3 mb-6">
      <div className="p-2 bg-slate-100 rounded-lg">{icon}</div>
      <div>
        <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
        <p className="text-sm text-slate-500">{subtitle}</p>
      </div>
    </div>
  )
}

function TabLink({
  href,
  icon,
  label,
}: {
  href: string
  icon: React.ReactNode
  label: string
}) {
  return (
    <a
      href={href}
      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-50 rounded-lg transition-colors"
    >
      {icon}
      {label}
    </a>
  )
}

function QuickLink({
  href,
  icon,
  label,
  description,
  badge,
}: {
  href: string
  icon: React.ReactNode
  label: string
  description: string
  badge?: string
}) {
  return (
    <Link
      href={href}
      className="p-4 rounded-lg border border-slate-200 hover:border-slate-300 hover:bg-slate-50 transition-all group"
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-slate-100 rounded group-hover:bg-slate-200 transition-colors">
          {icon}
        </div>
        {badge && (
          <span className="px-2 py-0.5 text-xs font-semibold bg-blue-100 text-blue-700 rounded-full">
            {badge}
          </span>
        )}
      </div>
      <p className="font-medium text-slate-900">{label}</p>
      <p className="text-xs text-slate-500">{description}</p>
    </Link>
  )
}
