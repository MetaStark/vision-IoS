/**
 * ACI Triangle Panel Component
 * CEO Directive CEO-ACI-TRIANGLE-2025-12-21
 *
 * Displays shadow evaluation telemetry for:
 * - EC-020 SitC: Reasoning chain integrity
 * - EC-021 InForage: API budget discipline
 * - EC-022 IKEA: Hallucination firewall
 *
 * Mode: SHADOW/AUDIT-ONLY (crypto assets only)
 */

'use client'

import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils/cn'
import {
  Brain,
  DollarSign,
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Activity
} from 'lucide-react'

interface ACITriangleTelemetry {
  sitc: {
    totalEvaluated: number
    brokenChains: number
    brokenChainRate: number
    avgScore: number
    reasonDistribution: Record<string, number>
    lastEvaluatedAt: string | null
  }
  inforage: {
    totalCostUsd: number
    avgCostPerNeedle: number
    budgetCapUsd: number
    budgetPressurePct: number
    avgBudgetPressure: number
    totalApiCalls: number
    lastEvaluatedAt: string | null
    currentBalance?: number
    initialBalance?: number
    monthlySpent?: number
  }
  ikea: {
    totalEvaluated: number
    fabricationCount: number
    staleDataCount: number
    unverifiableCount: number
    flaggedTotal: number
    fabricationRate: number
    avgScore: number
    lastEvaluatedAt: string | null
  }
  summary: {
    mode: 'SHADOW'
    assetFilter: 'CRYPTO_ONLY'
    totalNeedlesEvaluated: number
    totalNeedlesInDatabase: number
    needlesWithChainHash: number
    chainHashCoverage: number
    lastFullScanAt: string | null
  }
  timestamp: string
}

interface ACITrianglePanelProps {
  className?: string
  refreshKey?: number
}

export function ACITrianglePanel({ className, refreshKey = 0 }: ACITrianglePanelProps) {
  const [data, setData] = useState<ACITriangleTelemetry | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const res = await fetch('/api/aci-triangle')
        if (!res.ok) throw new Error('Failed to fetch ACI telemetry')
        const json = await res.json()
        setData(json)
      } catch (err) {
        console.error('[ACI Triangle] Fetch error:', err)
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
    // Refresh every 60 seconds
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [refreshKey])

  const getHealthStatus = (rate: number, threshold: number, inverse = false) => {
    const isHealthy = inverse ? rate < threshold : rate >= threshold
    return {
      color: isHealthy ? 'text-green-400' : 'text-red-400',
      bgColor: isHealthy ? 'bg-green-900/20' : 'bg-red-900/20',
      borderColor: isHealthy ? 'border-green-800' : 'border-red-800',
      icon: isHealthy ? CheckCircle : XCircle
    }
  }

  const getBudgetStatus = (balance: number, budgetCap: number) => {
    // Green if balance > 50% of budget, Yellow if 20-50%, Red if < 20%
    const ratio = balance / budgetCap
    if (ratio > 0.5) return { color: 'text-green-400', label: 'HEALTHY', bgColor: 'bg-green-900/20' }
    if (ratio > 0.2) return { color: 'text-yellow-400', label: 'CAUTION', bgColor: 'bg-yellow-900/20' }
    return { color: 'text-red-400', label: 'CRITICAL', bgColor: 'bg-red-900/20' }
  }

  if (isLoading) {
    return (
      <div className={cn('bg-gray-900 border border-gray-800 rounded-lg p-6', className)}>
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-800 rounded w-1/3" />
          <div className="grid grid-cols-3 gap-4">
            <div className="h-32 bg-gray-800 rounded" />
            <div className="h-32 bg-gray-800 rounded" />
            <div className="h-32 bg-gray-800 rounded" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className={cn('bg-gray-900 border border-red-900/50 rounded-lg p-6', className)}>
        <div className="text-red-400">
          <div className="font-semibold mb-2">ACI Triangle Offline</div>
          <div className="text-sm text-gray-500">
            {error || 'Run: python aci_triangle_shadow.py --evaluate'}
          </div>
        </div>
      </div>
    )
  }

  const sitcHealth = getHealthStatus(data.sitc.brokenChainRate, 50, true)
  const ikeaHealth = getHealthStatus(data.ikea.fabricationRate, 10, true)
  const budgetStatus = getBudgetStatus(data.inforage.currentBalance ?? 0, data.inforage.budgetCapUsd)

  return (
    <div
      className={cn(
        'bg-gray-900 border border-gray-800 rounded-lg',
        'shadow-lg shadow-gray-950/50',
        className
      )}
    >
      {/* Header */}
      <div className="border-b border-gray-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-900/30 rounded-lg">
              <Activity className="h-5 w-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white">ACI Constraint Triangle</h3>
              <p className="text-xs text-gray-500">Shadow Mode | Crypto Only</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-xs text-white font-medium">
                {data.summary.totalNeedlesInDatabase} needles
              </div>
              <div className="text-[10px] text-gray-500">
                {data.summary.needlesWithChainHash}/{data.summary.totalNeedlesInDatabase} chain hash
              </div>
            </div>
            <span className="px-2 py-0.5 text-xs bg-purple-900/30 text-purple-400 rounded">
              SHADOW
            </span>
          </div>
        </div>
      </div>

      {/* Three EC Cards */}
      <div className="grid grid-cols-3 gap-4 p-6">
        {/* EC-020 SitC */}
        <div className={cn(
          'rounded-lg border p-4 transition-all',
          sitcHealth.bgColor,
          sitcHealth.borderColor
        )}>
          <div className="flex items-center gap-2 mb-3">
            <Brain className={cn('h-4 w-4', sitcHealth.color)} />
            <span className="text-xs font-medium text-gray-400">EC-020 SitC</span>
          </div>
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-2xl font-bold text-white">
                {(100 - data.sitc.brokenChainRate).toFixed(0)}%
              </span>
              <span className="text-xs text-gray-500">chain integrity</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full', sitcHealth.color.replace('text-', 'bg-'))}
                style={{ width: `${100 - data.sitc.brokenChainRate}%` }}
              />
            </div>
            <div className="text-xs text-gray-500">
              {data.sitc.brokenChains} broken of {data.sitc.totalEvaluated}
            </div>
            {Object.entries(data.sitc.reasonDistribution).length > 0 && (
              <div className="mt-2 pt-2 border-t border-gray-800">
                {Object.entries(data.sitc.reasonDistribution).slice(0, 2).map(([reason, count]) => (
                  <div key={reason} className="flex items-center justify-between text-xs">
                    <span className="text-gray-500 truncate">{reason}</span>
                    <span className="text-gray-400">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* EC-021 InForage */}
        <div className={cn(
          'rounded-lg border p-4 transition-all',
          budgetStatus.bgColor,
          budgetStatus.color === 'text-green-400' ? 'border-green-800' :
          budgetStatus.color === 'text-yellow-400' ? 'border-yellow-800' : 'border-red-800'
        )}>
          <div className="flex items-center gap-2 mb-3">
            <DollarSign className={cn('h-4 w-4', budgetStatus.color)} />
            <span className="text-xs font-medium text-gray-400">EC-021 InForage</span>
          </div>
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-2xl font-bold text-white">
                ${(data.inforage.monthlySpent ?? data.inforage.totalCostUsd ?? 0).toFixed(2)}
              </span>
              <span className={cn('text-xs', budgetStatus.color)}>SPENT</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full bg-green-400"
                style={{ width: `${Math.min(100, ((data.inforage.monthlySpent ?? 0) / data.inforage.budgetCapUsd) * 100)}%` }}
              />
            </div>
            <div className="text-xs text-gray-500">
              Monthly expenses (from DeepSeek)
            </div>
            <div className="mt-2 pt-2 border-t border-gray-800 space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Balance</span>
                <span className="text-gray-400">${(data.inforage.currentBalance ?? 0).toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Source</span>
                <span className="text-green-400">DEEPSEEK API</span>
              </div>
            </div>
          </div>
        </div>

        {/* EC-022 IKEA */}
        <div className={cn(
          'rounded-lg border p-4 transition-all',
          ikeaHealth.bgColor,
          ikeaHealth.borderColor
        )}>
          <div className="flex items-center gap-2 mb-3">
            <Shield className={cn('h-4 w-4', ikeaHealth.color)} />
            <span className="text-xs font-medium text-gray-400">EC-022 IKEA</span>
          </div>
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <span className="text-2xl font-bold text-white">
                {(data.ikea.avgScore * 100).toFixed(0)}%
              </span>
              <span className="text-xs text-gray-500">confidence</span>
            </div>
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={cn('h-full rounded-full', ikeaHealth.color.replace('text-', 'bg-'))}
                style={{ width: `${data.ikea.avgScore * 100}%` }}
              />
            </div>
            <div className="text-xs text-gray-500">
              {data.ikea.flaggedTotal} flagged of {data.ikea.totalEvaluated}
            </div>
            <div className="mt-2 pt-2 border-t border-gray-800 space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Fabrications</span>
                <span className={data.ikea.fabricationCount > 0 ? 'text-red-400' : 'text-gray-400'}>
                  {data.ikea.fabricationCount}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Stale data</span>
                <span className={data.ikea.staleDataCount > 0 ? 'text-yellow-400' : 'text-gray-400'}>
                  {data.ikea.staleDataCount}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="text-xs text-gray-600">
          Sample: {data.summary.totalNeedlesEvaluated} evaluated | Coverage: {data.summary.chainHashCoverage.toFixed(0)}%
        </div>
        <div className="text-xs text-gray-600">
          Last scan: {data.summary.lastFullScanAt
            ? new Date(data.summary.lastFullScanAt).toLocaleTimeString()
            : 'Never'}
        </div>
      </div>
    </div>
  )
}
