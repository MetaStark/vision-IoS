/**
 * Research & Causal Topology Module
 * CEO Directive 2026 - Pillar III Implementation
 *
 * Authority: ADR-001, ADR-013, ADR-017
 * Classification: CONSTITUTIONAL - Glass Wall Observability Layer
 *
 * This module provides:
 * - Alpha Graph visualization (Causal Topology)
 * - Backtest results viewer
 * - Strategy performance analysis
 * - Feature performance tables
 */

import { Suspense } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { getAlphaGraphData, getGraphStatistics } from '@/lib/fcc/alpha-graph-engine'
import { AlphaGraphCanvas } from './AlphaGraphCanvas'
import {
  FlaskConical,
  Network,
  Activity,
  Zap,
  TrendingUp,
  Link2,
  BarChart3,
  BookOpen,
  Lightbulb,
} from 'lucide-react'
import Link from 'next/link'

export const revalidate = 30

export default async function ResearchPage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div className="border-b border-slate-200 pb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-purple-600 rounded-lg">
            <FlaskConical className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-display">Research & Causal Topology</h1>
            <p className="text-sm text-slate-500">
              CEO Directive 2026 | Pillar III | Alpha Graph Visualization
            </p>
          </div>
        </div>
        <p className="mt-3 text-slate-600 max-w-3xl">
          Visualize causal relationships between assets, macro factors, and market indicators.
          Explore the Alpha Graph topology that powers FjordHQ's signal generation.
        </p>
        <div className="flex items-center gap-4 mt-4 text-xs text-slate-500">
          <span>Compliance: ADR-013, ADR-017</span>
          <span>|</span>
          <span>Mode: READ-ONLY</span>
        </div>
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <QuickCard
          icon={<Network className="w-5 h-5" />}
          label="Alpha Graph"
          description="Causal topology"
          href="#graph"
          active
        />
        <QuickCard
          icon={<BarChart3 className="w-5 h-5" />}
          label="Backtests"
          description="Strategy results"
          href="#backtests"
        />
        <QuickCard
          icon={<TrendingUp className="w-5 h-5" />}
          label="Features"
          description="Feature performance"
          href="#features"
        />
        <QuickCard
          icon={<BookOpen className="w-5 h-5" />}
          label="Lessons"
          description="Research notes"
          href="#lessons"
        />
      </div>

      {/* Alpha Graph Section */}
      <section id="graph">
        <div className="flex items-center gap-2 mb-4">
          <Network className="w-5 h-5 text-cyan-600" />
          <h2 className="text-xl font-semibold text-slate-900">Alpha Graph - Causal Topology</h2>
          <StatusBadge variant="pass">LIVE</StatusBadge>
        </div>
        <Suspense fallback={<GraphSkeleton />}>
          <AlphaGraphSection />
        </Suspense>
      </section>

      {/* Backtest Results Section */}
      <section id="backtests">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-purple-600" />
          <h2 className="text-xl font-semibold text-slate-900">Backtest Results</h2>
          <StatusBadge variant="info">Coming Soon</StatusBadge>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <BarChart3 className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">
              Strategy performance analysis will be available in Phase 4 Sprint 4.1
            </p>
            <p className="text-sm text-slate-400 mt-2">
              Tables: strategy_baseline_results, btc_backtest_trades
            </p>
          </CardContent>
        </Card>
      </section>

      {/* Feature Performance Section */}
      <section id="features">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-5 h-5 text-green-600" />
          <h2 className="text-xl font-semibold text-slate-900">Feature Performance</h2>
          <StatusBadge variant="info">Coming Soon</StatusBadge>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <TrendingUp className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">
              Feature performance metrics will be available in Phase 4
            </p>
            <p className="text-sm text-slate-400 mt-2">
              Source: vision_signals.alpha_graph_nodes feature weights
            </p>
          </CardContent>
        </Card>
      </section>

      {/* Lessons Learned Section */}
      <section id="lessons">
        <div className="flex items-center gap-2 mb-4">
          <Lightbulb className="w-5 h-5 text-amber-600" />
          <h2 className="text-xl font-semibold text-slate-900">Research Lessons</h2>
          <StatusBadge variant="info">Coming Soon</StatusBadge>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <Lightbulb className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">
              Research notes and lessons learned will be available in Phase 4
            </p>
          </CardContent>
        </Card>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 pt-6 text-center text-xs text-slate-400">
        <p>Research & Causal Topology v1.0.0 | CEO Directive 2026 Pillar III</p>
        <p className="mt-1">
          Glass Wall Architecture | READ-ONLY Mode
        </p>
      </footer>
    </div>
  )
}

// ============================================================================
// Alpha Graph Section
// ============================================================================

async function AlphaGraphSection() {
  const [graphData, stats] = await Promise.all([
    getAlphaGraphData(),
    getGraphStatistics(),
  ])

  return (
    <div className="space-y-4">
      {/* Stats Bar */}
      <div className="flex items-center gap-6 p-4 bg-slate-50 rounded-lg border border-slate-200">
        <StatBadge
          icon={<Activity className="w-4 h-4" />}
          label="Nodes"
          value={stats.total_nodes}
          color="cyan"
        />
        <StatBadge
          icon={<Link2 className="w-4 h-4" />}
          label="Edges"
          value={stats.total_edges}
          color="purple"
        />
        <StatBadge
          icon={<Zap className="w-4 h-4" />}
          label="Avg Degree"
          value={stats.avg_degree.toFixed(1)}
          color="amber"
        />
        <StatBadge
          icon={<TrendingUp className="w-4 h-4" />}
          label="Density"
          value={(stats.density * 100).toFixed(1) + '%'}
          color="green"
        />
        {stats.most_connected_node && (
          <StatBadge
            icon={<Network className="w-4 h-4" />}
            label="Hub"
            value={stats.most_connected_node.id.substring(0, 12) + '...'}
            color="rose"
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-slate-500">
        <span className="font-medium">Edge Types:</span>
        <LegendItem color="#06B6D4" label="LEADS" />
        <LegendItem color="#22C55E" label="AMPLIFIES" />
        <LegendItem color="#EF4444" label="INVERSE" />
        <LegendItem color="#8B5CF6" label="CORRELATES" />
      </div>

      {/* Graph Canvas */}
      <div className="relative rounded-lg overflow-hidden border border-slate-200" style={{ height: '600px' }}>
        <AlphaGraphCanvas data={graphData} />
      </div>

      {/* Data Info */}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>Data sources: {graphData.metadata.data_sources.join(', ') || 'N/A'}</span>
        <span>Last updated: {graphData.metadata.last_updated}</span>
      </div>
    </div>
  )
}

// ============================================================================
// UI Components
// ============================================================================

function QuickCard({
  icon,
  label,
  description,
  href,
  active,
}: {
  icon: React.ReactNode
  label: string
  description: string
  href: string
  active?: boolean
}) {
  return (
    <a
      href={href}
      className={`p-4 rounded-lg border transition-all ${
        active
          ? 'bg-cyan-50 border-cyan-200 hover:border-cyan-300'
          : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded ${active ? 'bg-cyan-100' : 'bg-slate-100'}`}>
          {icon}
        </div>
        {active && (
          <span className="px-2 py-0.5 text-xs font-semibold bg-cyan-100 text-cyan-700 rounded-full">
            Active
          </span>
        )}
      </div>
      <p className="font-medium text-slate-900">{label}</p>
      <p className="text-xs text-slate-500">{description}</p>
    </a>
  )
}

function StatBadge({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: string | number
  color: 'cyan' | 'purple' | 'amber' | 'green' | 'rose'
}) {
  const colorClasses = {
    cyan: 'text-cyan-600 bg-cyan-50',
    purple: 'text-purple-600 bg-purple-50',
    amber: 'text-amber-600 bg-amber-50',
    green: 'text-green-600 bg-green-50',
    rose: 'text-rose-600 bg-rose-50',
  }

  return (
    <div className="flex items-center gap-2">
      <div className={`p-1.5 rounded ${colorClasses[color]}`}>
        {icon}
      </div>
      <div>
        <div className="text-slate-500 text-xs">{label}</div>
        <div className={`font-mono font-semibold ${colorClasses[color].split(' ')[0]}`}>
          {value}
        </div>
      </div>
    </div>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className="w-4 h-0.5"
        style={{ backgroundColor: color }}
      />
      <span>{label}</span>
    </div>
  )
}

function GraphSkeleton() {
  return (
    <div className="space-y-4">
      <div className="h-16 bg-slate-100 rounded-lg animate-pulse" />
      <div className="h-[600px] bg-slate-100 rounded-lg animate-pulse flex items-center justify-center">
        <Network className="w-12 h-12 text-slate-300" />
      </div>
    </div>
  )
}
