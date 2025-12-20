'use client'

import { useState, useEffect } from 'react'
import { Activity, Shield, AlertTriangle, TrendingUp, TrendingDown, Clock, CheckCircle, XCircle } from 'lucide-react'

interface ShadowTrade {
  trade_id: string
  asset_id: string
  direction: string
  entry_price: number
  shadow_size: number
  entry_time: string
  status: string
  pnl: number | null
}

interface DecisionPlan {
  decision_id: string
  decision_type: string
  defcon_level: number
  execution_state: string
  signature_agent: string
  created_at: string
}

interface SecurityAlert {
  alert_id: string
  alert_type: string
  alert_severity: string
  source_module: string
  created_at: string
}

interface LiveShadowData {
  success: boolean
  timestamp: string
  activation_mode: string
  ios012: {
    ios_id: string
    status: string
    governance_state: string
  }
  safeguards: {
    ed25519_validation: boolean
    execution_guard: boolean
    ios008_mandate: boolean
    defcon_circuit_breaker: boolean
    paper_mode: boolean
  }
  shadow_trades: {
    data: ShadowTrade[]
    summary: { open: number; closed: number; total_pnl: number }
  }
  decisions: {
    data: DecisionPlan[]
    total: number
  }
  governance_events: {
    data: SecurityAlert[]
    summary: { critical: number; high: number; total: number }
  }
}

export function LiveShadowActivity() {
  const [data, setData] = useState<LiveShadowData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/aol/live-shadow')
        const json = await res.json()
        if (json.success) {
          setData(json)
          setError(null)
        } else {
          setError(json.error || 'Failed to fetch')
        }
      } catch (err) {
        setError('Failed to connect')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="p-6 rounded-lg border border-slate-700 bg-slate-800/50">
        <div className="animate-pulse">Loading Live Shadow Activity...</div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-6 rounded-lg border border-red-500/30 bg-red-900/20">
        <div className="flex items-center gap-2 text-red-400">
          <XCircle className="w-5 h-5" />
          <span>Live Shadow Error: {error}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-4 rounded-lg border border-emerald-500/30 bg-emerald-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-600 rounded-lg">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-emerald-100">
                IoS-012 Live Shadow Mode
              </h3>
              <p className="text-sm text-emerald-400">
                {data.ios012.governance_state} | CD-IOS-012-LIVE-ACT-001
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-3 py-1 text-sm font-semibold bg-emerald-600 text-white rounded-full">
              PAPER MODE ACTIVE
            </span>
          </div>
        </div>
      </div>

      {/* Safeguards Status */}
      <div className="grid grid-cols-5 gap-3">
        <SafeguardBadge
          name="Ed25519"
          active={data.safeguards.ed25519_validation}
        />
        <SafeguardBadge
          name="ExecutionGuard"
          active={data.safeguards.execution_guard}
        />
        <SafeguardBadge
          name="IoS-008 Mandate"
          active={data.safeguards.ios008_mandate}
        />
        <SafeguardBadge
          name="DEFCON Breaker"
          active={data.safeguards.defcon_circuit_breaker}
        />
        <SafeguardBadge
          name="Paper Mode"
          active={data.safeguards.paper_mode}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-2 gap-6">
        {/* Shadow Trades */}
        <div className="p-4 rounded-lg border border-slate-700 bg-slate-800/50">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-semibold text-slate-200 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Shadow Trades
            </h4>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-emerald-400">Open: {data.shadow_trades.summary.open}</span>
              <span className="text-slate-400">Closed: {data.shadow_trades.summary.closed}</span>
            </div>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {data.shadow_trades.data.slice(0, 8).map((trade) => (
              <div
                key={trade.trade_id}
                className="flex items-center justify-between p-2 rounded bg-slate-700/50 text-sm"
              >
                <div className="flex items-center gap-2">
                  {trade.direction === 'LONG' ? (
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  )}
                  <span className="font-mono text-slate-200">{trade.asset_id}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-slate-400">${trade.entry_price.toLocaleString()}</span>
                  <span className={trade.status === 'OPEN' ? 'text-emerald-400' : 'text-slate-500'}>
                    {trade.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Governance Events */}
        <div className="p-4 rounded-lg border border-slate-700 bg-slate-800/50">
          <div className="flex items-center justify-between mb-4">
            <h4 className="font-semibold text-slate-200 flex items-center gap-2">
              <Shield className="w-4 h-4" />
              Governance Events
            </h4>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-red-400">Critical: {data.governance_events.summary.critical}</span>
              <span className="text-amber-400">High: {data.governance_events.summary.high}</span>
            </div>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {data.governance_events.data.slice(0, 8).map((alert) => (
              <div
                key={alert.alert_id}
                className={`flex items-center justify-between p-2 rounded text-sm ${
                  alert.alert_severity === 'CRITICAL'
                    ? 'bg-red-900/30 border border-red-500/30'
                    : alert.alert_severity === 'HIGH'
                    ? 'bg-amber-900/30 border border-amber-500/30'
                    : 'bg-slate-700/50'
                }`}
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle
                    className={`w-4 h-4 ${
                      alert.alert_severity === 'CRITICAL'
                        ? 'text-red-400'
                        : alert.alert_severity === 'HIGH'
                        ? 'text-amber-400'
                        : 'text-slate-400'
                    }`}
                  />
                  <span className="text-slate-200 truncate max-w-48">
                    {alert.alert_type.replace(/_/g, ' ')}
                  </span>
                </div>
                <span className="text-xs text-slate-500">
                  {new Date(alert.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Decision Plans */}
      <div className="p-4 rounded-lg border border-slate-700 bg-slate-800/50">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-semibold text-slate-200 flex items-center gap-2">
            <Clock className="w-4 h-4" />
            Recent Decision Plans
          </h4>
          <span className="text-sm text-slate-400">Total: {data.decisions.total}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="pb-2 pr-4">Decision ID</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4">DEFCON</th>
                <th className="pb-2 pr-4">Signer</th>
                <th className="pb-2 pr-4">State</th>
                <th className="pb-2">Time</th>
              </tr>
            </thead>
            <tbody>
              {data.decisions.data.slice(0, 5).map((decision) => (
                <tr key={decision.decision_id} className="border-b border-slate-700/50">
                  <td className="py-2 pr-4 font-mono text-xs text-slate-300">
                    {decision.decision_id.slice(0, 8)}...
                  </td>
                  <td className="py-2 pr-4 text-slate-200">
                    {decision.decision_type.replace(/_/g, ' ')}
                  </td>
                  <td className="py-2 pr-4">
                    <DefconBadge level={decision.defcon_level} />
                  </td>
                  <td className="py-2 pr-4 text-slate-300">{decision.signature_agent}</td>
                  <td className="py-2 pr-4">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      decision.execution_state === 'PENDING'
                        ? 'bg-amber-900/50 text-amber-300'
                        : 'bg-slate-700 text-slate-300'
                    }`}>
                      {decision.execution_state}
                    </span>
                  </td>
                  <td className="py-2 text-slate-500 text-xs">
                    {new Date(decision.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Footer */}
      <div className="text-xs text-slate-500 text-center">
        Last updated: {new Date(data.timestamp).toLocaleString()} | Real capital execution BLOCKED
      </div>
    </div>
  )
}

function SafeguardBadge({ name, active }: { name: string; active: boolean }) {
  return (
    <div
      className={`p-2 rounded text-center text-xs ${
        active
          ? 'bg-emerald-900/30 border border-emerald-500/30 text-emerald-300'
          : 'bg-red-900/30 border border-red-500/30 text-red-300'
      }`}
    >
      <div className="flex items-center justify-center gap-1 mb-1">
        {active ? (
          <CheckCircle className="w-3 h-3" />
        ) : (
          <XCircle className="w-3 h-3" />
        )}
      </div>
      <span>{name}</span>
    </div>
  )
}

function DefconBadge({ level }: { level: number }) {
  const colors: Record<number, string> = {
    1: 'bg-red-600 text-white',
    2: 'bg-orange-500 text-white',
    3: 'bg-amber-500 text-black',
    4: 'bg-yellow-400 text-black',
    5: 'bg-emerald-500 text-white'
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${colors[level] || 'bg-slate-600'}`}>
      {level}
    </span>
  )
}
