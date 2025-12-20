/**
 * FCC Agent Activity Panel
 * Glass Wall Observability Layer - Agent Health & Activity View
 *
 * Authority: CEO Directive 2026
 * Compliance: ADR-001, ADR-016, ADR-018
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import type { AgentHeartbeat, AgentActivity, DEFCONState } from '@/lib/fcc/types'
import { Activity, Heart, AlertTriangle, Clock, Cpu, Zap } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface AgentActivityPanelProps {
  activity: AgentActivity
  defconState: DEFCONState | null
}

export function AgentActivityPanel({ activity, defconState }: AgentActivityPanelProps) {
  const { agents, system_health, defcon_level } = activity

  return (
    <div className="space-y-6">
      {/* DEFCON Status Banner */}
      <DEFCONBanner defconState={defconState} />

      {/* System Health Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SystemHealthCard health={system_health} />
        <ActiveAgentsCard agents={agents} />
        <DefconLevelCard level={defcon_level} />
      </div>

      {/* Agent Grid */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Agent Heartbeats (Last 24h)</CardTitle>
            <span className="text-xs text-slate-500">
              Source: fhq_governance.agent_heartbeats
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <AgentCard key={agent.agent_id} agent={agent} />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function DEFCONBanner({ defconState }: { defconState: DEFCONState | null }) {
  if (!defconState) return null

  const colors: Record<string, { bg: string; text: string; border: string }> = {
    GREEN: { bg: 'bg-green-900/50', text: 'text-green-300', border: 'border-green-700' },
    YELLOW: { bg: 'bg-yellow-900/50', text: 'text-yellow-300', border: 'border-yellow-700' },
    ORANGE: { bg: 'bg-orange-900/50', text: 'text-orange-300', border: 'border-orange-700' },
    RED: { bg: 'bg-red-900/50', text: 'text-red-300', border: 'border-red-700' },
    BLACK: { bg: 'bg-slate-950', text: 'text-white', border: 'border-slate-600' },
  }

  const style = colors[defconState.defcon_level] || colors.GREEN

  return (
    <div className={`${style.bg} ${style.border} border rounded-lg p-4`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${getDefconDotColor(defconState.defcon_level)} animate-pulse`} />
          <div>
            <span className={`font-bold ${style.text}`}>
              DEFCON {defconState.defcon_level}
            </span>
            <p className={`text-sm ${style.text} opacity-80`}>
              {defconState.trigger_reason}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className={`text-xs ${style.text} opacity-60`}>
            Triggered by {defconState.triggered_by}
          </p>
          <p className={`text-xs ${style.text} opacity-60`}>
            {formatDistanceToNow(new Date(defconState.triggered_at), { addSuffix: true })}
          </p>
        </div>
      </div>
    </div>
  )
}

function AgentCard({ agent }: { agent: AgentHeartbeat }) {
  const isAlive = agent.status === 'ALIVE'
  const isDegraded = agent.status === 'DEGRADED'
  const healthPercent = agent.health_score * 100

  return (
    <div
      className={`
        border rounded-lg p-4 transition-all
        ${isAlive ? 'border-green-700 bg-green-900/30' : ''}
        ${isDegraded ? 'border-yellow-700 bg-yellow-900/30' : ''}
        ${!isAlive && !isDegraded ? 'border-red-700 bg-red-900/30' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <AgentAvatar agentId={agent.agent_id} />
          <span className="font-bold text-slate-100">{agent.agent_id}</span>
        </div>
        <StatusPill status={agent.status} />
      </div>

      {/* Health Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-slate-400">Health Score</span>
          <span className="font-mono text-slate-200">{healthPercent.toFixed(0)}%</span>
        </div>
        <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${getHealthBarColor(healthPercent)}`}
            style={{ width: `${healthPercent}%` }}
          />
        </div>
      </div>

      {/* Current Task */}
      {agent.current_task && (
        <div className="mb-3">
          <p className="text-xs text-slate-400 mb-1">Current Task</p>
          <p className="text-sm text-slate-200 line-clamp-1">{agent.current_task}</p>
        </div>
      )}

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs border-t border-slate-700 pt-3">
        <div>
          <p className="text-slate-400">Events</p>
          <p className="font-mono font-medium text-slate-200">{agent.events_processed}</p>
        </div>
        <div>
          <p className="text-slate-400">Errors</p>
          <p className={`font-mono font-medium ${agent.errors_count > 0 ? 'text-red-400' : 'text-slate-200'}`}>
            {agent.errors_count}
          </p>
        </div>
        <div>
          <p className="text-slate-400">Warnings</p>
          <p className={`font-mono font-medium ${agent.warnings_count > 0 ? 'text-amber-400' : 'text-slate-200'}`}>
            {agent.warnings_count}
          </p>
        </div>
      </div>

      {/* Last Heartbeat */}
      <div className="mt-3 pt-2 border-t border-slate-700 flex items-center gap-1 text-xs text-slate-500">
        <Clock className="w-3 h-3" />
        {formatDistanceToNow(new Date(agent.last_heartbeat_at), { addSuffix: true })}
      </div>
    </div>
  )
}

function AgentAvatar({ agentId }: { agentId: string }) {
  const colors: Record<string, string> = {
    LARS: 'bg-blue-500',
    STIG: 'bg-green-500',
    FINN: 'bg-purple-500',
    VEGA: 'bg-amber-500',
    LINE: 'bg-pink-500',
    CEIO: 'bg-cyan-500',
    CRIO: 'bg-indigo-500',
  }

  return (
    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold ${colors[agentId] || 'bg-slate-500'}`}>
      {agentId.charAt(0)}
    </div>
  )
}

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ALIVE: 'bg-green-900/50 text-green-300 border border-green-700',
    DEGRADED: 'bg-yellow-900/50 text-yellow-300 border border-yellow-700',
    DEAD: 'bg-red-900/50 text-red-300 border border-red-700',
    UNKNOWN: 'bg-slate-800 text-slate-300 border border-slate-600',
  }

  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || styles.UNKNOWN}`}>
      {status}
    </span>
  )
}

function SystemHealthCard({ health }: { health: number }) {
  const percent = health * 100

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-3 mb-3">
        <div className="p-2 bg-green-900/50 rounded-lg">
          <Heart className="w-5 h-5 text-green-400" />
        </div>
        <div>
          <p className="text-2xl font-bold text-slate-100">{percent.toFixed(0)}%</p>
          <p className="text-xs text-slate-400">System Health</p>
        </div>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${getHealthBarColor(percent)}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}

function ActiveAgentsCard({ agents }: { agents: AgentHeartbeat[] }) {
  const alive = agents.filter(a => a.status === 'ALIVE').length

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-blue-900/50 rounded-lg">
          <Cpu className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <p className="text-2xl font-bold text-slate-100">{alive}/{agents.length}</p>
          <p className="text-xs text-slate-400">Agents Active</p>
        </div>
      </div>
    </div>
  )
}

function DefconLevelCard({ level }: { level: number }) {
  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-amber-900/50 rounded-lg">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
        </div>
        <div>
          <p className="text-2xl font-bold text-slate-100">DEFCON {level}</p>
          <p className="text-xs text-slate-400">Alert Level</p>
        </div>
      </div>
    </div>
  )
}

function getHealthBarColor(percent: number): string {
  if (percent >= 80) return 'bg-green-500'
  if (percent >= 60) return 'bg-yellow-500'
  if (percent >= 40) return 'bg-orange-500'
  return 'bg-red-500'
}

function getDefconDotColor(level: string): string {
  const colors: Record<string, string> = {
    GREEN: 'bg-green-500',
    YELLOW: 'bg-yellow-500',
    ORANGE: 'bg-orange-500',
    RED: 'bg-red-500',
    BLACK: 'bg-slate-900',
  }
  return colors[level] || 'bg-slate-500'
}
