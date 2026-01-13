'use client'

/**
 * System Health & Governance Dashboard
 * CEO-DIR-2026-042 through 045 Implementation
 *
 * Displays:
 * - Agent heartbeats/liveness status
 * - Gap closure status
 * - DEFCON state
 * - Monitoring baseline
 * - Learning loop health
 */

import { useEffect, useState } from 'react'
import {
  Heart,
  Shield,
  Activity,
  Database,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Brain,
  Zap
} from 'lucide-react'

interface Agent {
  id: string
  component: string
  status: string
  healthScore: number
  healthSource: string
  livenessBasis: string
  lastHeartbeat: string
  ageSeconds: number
  fresh: boolean
}

interface Gap {
  id: string
  name: string
  status: string
  detail: string
}

interface SystemHealthData {
  timestamp: string
  summary: {
    totalAgents: number
    healthyAgents: number
    defconLevel: number
    gapsClosed: number
    totalGaps: number
  }
  agents: Agent[]
  defcon: {
    level: number
    reason: string
    setBy: string
    setAt: string
    daysSinceSet: number
  } | null
  monitoring: Record<string, number>
  learning: {
    outcomeLedgerCount: number
    canonicalOutcomesCount: number
  }
  forecasts: {
    total24h: number
    lastHour: number
    hourlyRate: number
  }
  priceFreshness: Array<{
    marketType: string
    latest: string
    minutesStale: number
  }>
  gaps: Gap[]
}

function StatusIcon({ status }: { status: string }) {
  if (['CLOSED', 'EVALUATED', 'ATTESTED', 'ALIVE'].includes(status)) {
    return <CheckCircle2 className="w-5 h-5 text-green-500" />
  }
  if (['DEGRADED', 'AT_RISK', 'IDLE-BY-DESIGN'].includes(status)) {
    return <AlertTriangle className="w-5 h-5 text-yellow-500" />
  }
  return <XCircle className="w-5 h-5 text-red-500" />
}

function DefconBadge({ level }: { level: number }) {
  const colors: Record<number, string> = {
    5: 'bg-green-500/20 text-green-400 border-green-500',
    4: 'bg-blue-500/20 text-blue-400 border-blue-500',
    3: 'bg-yellow-500/20 text-yellow-400 border-yellow-500',
    2: 'bg-orange-500/20 text-orange-400 border-orange-500',
    1: 'bg-red-500/20 text-red-400 border-red-500',
  }
  const labels: Record<number, string> = {
    5: 'GREEN',
    4: 'BLUE',
    3: 'YELLOW',
    2: 'ORANGE',
    1: 'RED',
  }

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-bold border ${colors[level] || colors[5]}`}>
      DEFCON {level} - {labels[level] || 'UNKNOWN'}
    </span>
  )
}

function AgentCard({ agent }: { agent: Agent }) {
  return (
    <div className={`p-4 rounded-lg border ${
      agent.fresh && agent.healthScore >= 0.5
        ? 'bg-green-500/5 border-green-500/30'
        : agent.healthScore >= 0.5
        ? 'bg-yellow-500/5 border-yellow-500/30'
        : 'bg-red-500/5 border-red-500/30'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-bold text-lg">{agent.id}</span>
          <span className="text-xs px-2 py-0.5 bg-[hsl(var(--secondary))] rounded">
            {agent.component}
          </span>
        </div>
        <StatusIcon status={agent.status} />
      </div>
      <div className="space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-[hsl(var(--muted-foreground))]">Status</span>
          <span className={`font-medium ${
            agent.status === 'ALIVE' ? 'text-green-400' :
            agent.status === 'IDLE-BY-DESIGN' ? 'text-yellow-400' :
            'text-red-400'
          }`}>{agent.status}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[hsl(var(--muted-foreground))]">Health</span>
          <span>{(agent.healthScore * 100).toFixed(0)}%</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[hsl(var(--muted-foreground))]">Source</span>
          <span className="text-xs">{agent.healthSource}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[hsl(var(--muted-foreground))]">Heartbeat</span>
          <span className={agent.fresh ? 'text-green-400' : 'text-red-400'}>
            {agent.ageSeconds}s ago
          </span>
        </div>
      </div>
      {agent.livenessBasis && (
        <p className="mt-2 text-xs text-[hsl(var(--muted-foreground))] border-t border-[hsl(var(--border))] pt-2">
          {agent.livenessBasis}
        </p>
      )}
    </div>
  )
}

function GapCard({ gap }: { gap: Gap }) {
  return (
    <div className={`p-3 rounded-lg border flex items-center gap-3 ${
      ['CLOSED', 'EVALUATED', 'ATTESTED'].includes(gap.status)
        ? 'bg-green-500/5 border-green-500/30'
        : gap.status === 'DEGRADED'
        ? 'bg-yellow-500/5 border-yellow-500/30'
        : 'bg-red-500/5 border-red-500/30'
    }`}>
      <StatusIcon status={gap.status} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-[hsl(var(--muted-foreground))]">{gap.id}</span>
          <span className="font-medium">{gap.name}</span>
        </div>
        <p className="text-xs text-[hsl(var(--muted-foreground))]">{gap.detail}</p>
      </div>
      <span className={`px-2 py-1 rounded text-xs font-medium ${
        ['CLOSED', 'EVALUATED', 'ATTESTED'].includes(gap.status)
          ? 'bg-green-500/20 text-green-400'
          : gap.status === 'DEGRADED'
          ? 'bg-yellow-500/20 text-yellow-400'
          : 'bg-red-500/20 text-red-400'
      }`}>
        {gap.status}
      </span>
    </div>
  )
}

export default function SystemHealthPage() {
  const [data, setData] = useState<SystemHealthData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function fetchData() {
    setLoading(true)
    try {
      const res = await fetch('/api/health/system')
      if (!res.ok) throw new Error('Failed to fetch system health')
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 animate-spin text-[hsl(var(--primary))]" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">
            System Health & Governance
          </h1>
          <p className="text-[hsl(var(--muted-foreground))]">
            CEO-DIR-2026-042 through 045 Implementation
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-white rounded-lg hover:opacity-90 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-500/20 border border-red-500 text-red-400 p-4 rounded-lg">
          {error}
        </div>
      )}

      {data && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* DEFCON Status */}
            <div className="p-4 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-5 h-5 text-blue-400" />
                <span className="font-semibold">DEFCON Status</span>
              </div>
              <div className="flex items-center justify-center py-2">
                <DefconBadge level={data.summary.defconLevel} />
              </div>
              {data.defcon && (
                <p className="text-xs text-center text-[hsl(var(--muted-foreground))] mt-2">
                  Set {data.defcon.daysSinceSet} days ago
                </p>
              )}
            </div>

            {/* Agent Health */}
            <div className={`p-4 rounded-lg border ${
              data.summary.healthyAgents === data.summary.totalAgents
                ? 'bg-green-500/10 border-green-500'
                : 'bg-yellow-500/10 border-yellow-500'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Heart className="w-5 h-5" />
                <span className="font-semibold">Agent Health</span>
              </div>
              <p className="text-2xl font-bold">
                {data.summary.healthyAgents}/{data.summary.totalAgents}
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Agents healthy
              </p>
            </div>

            {/* Gap Closure */}
            <div className={`p-4 rounded-lg border ${
              data.summary.gapsClosed === data.summary.totalGaps
                ? 'bg-green-500/10 border-green-500'
                : 'bg-yellow-500/10 border-yellow-500'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-5 h-5" />
                <span className="font-semibold">Gap Closure</span>
              </div>
              <p className="text-2xl font-bold">
                {data.summary.gapsClosed}/{data.summary.totalGaps}
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Gaps closed
              </p>
            </div>

            {/* Forecast Rate */}
            <div className="p-4 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-5 h-5 text-purple-400" />
                <span className="font-semibold">Forecast Rate</span>
              </div>
              <p className="text-2xl font-bold">{data.forecasts.hourlyRate}/hr</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                {data.forecasts.total24h} in last 24h
              </p>
            </div>
          </div>

          {/* Gap Status Section */}
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-4">
            <div className="flex items-center gap-2 mb-4">
              <Database className="w-5 h-5 text-[hsl(var(--primary))]" />
              <h2 className="font-semibold text-lg">Gap Closure Status (CEO-DIR-2026-042/045)</h2>
            </div>
            <div className="space-y-2">
              {data.gaps.map(gap => (
                <GapCard key={gap.id} gap={gap} />
              ))}
            </div>
          </div>

          {/* Agent Heartbeats Grid */}
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-4">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-[hsl(var(--primary))]" />
              <h2 className="font-semibold text-lg">Agent Heartbeats</h2>
              <span className="ml-auto text-xs bg-[hsl(var(--secondary))] px-2 py-1 rounded">
                {data.agents.length} agents
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {data.agents.map(agent => (
                <AgentCard key={agent.id} agent={agent} />
              ))}
            </div>
          </div>

          {/* Monitoring & Learning Stats */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Monitoring Baseline */}
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <Database className="w-5 h-5 text-blue-400" />
                <h3 className="font-semibold">Monitoring Baseline</h3>
              </div>
              <div className="space-y-2">
                {Object.entries(data.monitoring).map(([table, count]) => (
                  <div key={table} className="flex justify-between items-center p-2 bg-[hsl(var(--secondary))] rounded">
                    <span className="font-mono text-sm">{table}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      count > 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {count} rows
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Learning Loop */}
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-4">
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-5 h-5 text-purple-400" />
                <h3 className="font-semibold">Learning Loop Health</h3>
              </div>
              <div className="space-y-3">
                <div className="p-3 bg-[hsl(var(--secondary))] rounded">
                  <div className="flex justify-between items-center">
                    <span>Outcome Ledger (Active)</span>
                    <span className="text-green-400 font-bold">
                      {data.learning.outcomeLedgerCount.toLocaleString()}
                    </span>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    Forecast ground truth - learning loop reconciliation
                  </p>
                </div>
                <div className="p-3 bg-[hsl(var(--secondary))] rounded">
                  <div className="flex justify-between items-center">
                    <span>Canonical Outcomes (Future)</span>
                    <span className="text-yellow-400 font-bold">
                      {data.learning.canonicalOutcomesCount}
                    </span>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    Execution ground truth - awaiting execution gate
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Price Freshness */}
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-4">
            <div className="flex items-center gap-2 mb-4">
              <Clock className="w-5 h-5 text-[hsl(var(--primary))]" />
              <h3 className="font-semibold">Price Data Freshness</h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
              {data.priceFreshness.map(p => (
                <div key={p.marketType} className={`p-3 rounded border ${
                  p.minutesStale < 5 ? 'bg-green-500/10 border-green-500/30' :
                  p.minutesStale < 60 ? 'bg-yellow-500/10 border-yellow-500/30' :
                  'bg-red-500/10 border-red-500/30'
                }`}>
                  <div className="font-medium">{p.marketType}</div>
                  <div className="text-2xl font-bold">
                    {p.minutesStale < 1 ? '<1' : Math.round(p.minutesStale)} min
                  </div>
                  <div className="text-xs text-[hsl(var(--muted-foreground))]">
                    {new Date(p.latest).toLocaleTimeString()}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Last Updated */}
          <div className="text-center text-xs text-[hsl(var(--muted-foreground))]">
            Last updated: {new Date(data.timestamp).toLocaleString()}
          </div>
        </>
      )}
    </div>
  )
}
