/**
 * Comprehensive Data Dashboard Component
 * Bloomberg-style multi-asset, macro, and regime visualization
 * Displays all available data from fhq_data, fhq_macro, fhq_perception, fhq_graph
 */

'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { LineChart, type LineSeriesConfig } from '@/components/charts/LineChart'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Skeleton } from '@/components/ui/Skeleton'
import {
  TrendingUp, TrendingDown, Database, Clock, Activity,
  BarChart3, Globe, Cpu, AlertTriangle, CheckCircle, Layers, Cog, Eye, Brain,
  Target, LineChart as LineChartIcon, Zap, BookOpen, Radio
} from 'lucide-react'

// =============================================================================
// TYPES
// =============================================================================

interface OHLCVData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface AssetData {
  ticker: string
  name: string
  data: OHLCVData[]
  latestDate: string | null
  dataPoints: number
  latestPrice: number | null
  change24h: number | null
}

interface RegimeData {
  asset_id: string
  date: string
  regime_classification: string
  regime_confidence: number
  regime_stability_flag: boolean
  consecutive_confirms: number
}

interface MacroFeature {
  feature_id: string
  feature_name: string
  description: string
  cluster: string
  status: string
  frequency: string
}

interface MacroSeries {
  feature_id: string
  records: number
  from_date: string
  to_date: string
}

interface AlphaNode {
  node_id: string
  node_type: string
  label: string
  status: string
}

interface IosModule {
  ios_id: string
  title: string
  description: string
  status: string
  owner_role: string
  governance_state: string
  human_role: string
}

interface ScheduledTask {
  task_name: string
  task_type: string
  task_status: string
  owned_by_agent: string
  schedule_cron: string | null
  schedule_timezone: string | null
  schedule_description: string | null
  schedule_enabled: boolean
  last_scheduled_run: string | null
  run_count: number | null
  last_run_status: string | null
}

interface ScheduledTasksData {
  summary: {
    total_active: number
    scheduled_count: number
    unscheduled_vision_functions: number
    other_tasks: number
  }
  scheduled: ScheduledTask[]
  unscheduled: ScheduledTask[]
  other_tasks: ScheduledTask[]
}

type TimeRange = '7d' | '30d' | '90d' | '1y'

// =============================================================================
// CONSTANTS
// =============================================================================

const ALL_ASSETS = [
  { ticker: 'BTC-USD', dbId: 'BTCUSD', name: 'Bitcoin', color: '#f7931a', type: 'crypto' },
  { ticker: 'ETH-USD', dbId: 'ETHUSD', name: 'Ethereum', color: '#627eea', type: 'crypto' },
  { ticker: 'SOL-USD', dbId: 'SOLUSD', name: 'Solana', color: '#00ffa3', type: 'crypto' },
  { ticker: 'SPY', dbId: 'SPY', name: 'S&P 500 ETF', color: '#ef4444', type: 'equity' },
  { ticker: 'GLD', dbId: 'GLD', name: 'Gold ETF', color: '#fbbf24', type: 'commodity' },
  { ticker: 'EUR-USD', dbId: 'EURUSD', name: 'EUR/USD', color: '#3b82f6', type: 'forex' },
]

const TIME_RANGES: { value: TimeRange; label: string; days: number }[] = [
  { value: '7d', label: '7D', days: 7 },
  { value: '30d', label: '1M', days: 30 },
  { value: '90d', label: '3M', days: 90 },
  { value: '1y', label: '1Y', days: 365 },
]

const REGIME_COLORS: Record<string, string> = {
  'STRONG_BULL': '#22c55e',
  'BULL': '#86efac',
  'NEUTRAL': '#94a3b8',
  'BEAR': '#fca5a5',
  'STRONG_BEAR': '#ef4444',
  'BROKEN': '#7c3aed',
  'VOLATILE_NON_DIRECTIONAL': '#f59e0b',
}

const CLUSTER_COLORS: Record<string, string> = {
  'LIQUIDITY': '#3b82f6',
  'FACTOR': '#8b5cf6',
  'VOLATILITY': '#f59e0b',
  'CREDIT': '#ef4444',
  'ONCHAIN': '#22c55e',
  'OTHER': '#6b7280',
}

// IoS Module icons and colors
const IOS_CONFIG: Record<string, { icon: React.ElementType; color: string }> = {
  'IoS-001': { icon: Database, color: '#6366f1' },       // Registry/Foundation
  'IoS-002': { icon: LineChartIcon, color: '#8b5cf6' }, // Technical Indicators
  'IoS-003': { icon: Brain, color: '#ec4899' },          // HMM Regime
  'IoS-004': { icon: Target, color: '#14b8a6' },         // Portfolio Allocation
  'IoS-005': { icon: CheckCircle, color: '#22c55e' },    // Statistical Validation
  'IoS-006': { icon: Globe, color: '#3b82f6' },          // Macro Integration
  'IoS-007': { icon: Cpu, color: '#f59e0b' },            // Alpha Graph
  'IoS-008': { icon: Zap, color: '#ef4444' },            // Decision Engine
  'IoS-009': { icon: Eye, color: '#a855f7' },            // Perception Layer
  'IoS-010': { icon: BookOpen, color: '#06b6d4' },       // Prediction Ledger
  'IoS-011': { icon: BarChart3, color: '#64748b' },      // Technical Analysis
  'IoS-012': { icon: Radio, color: '#f97316' },          // Order Execution
  'IoS-013.HCP-LAB': { icon: Cog, color: '#84cc16' },    // Options Lab
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function HistoricalDataChart() {
  const [timeRange, setTimeRange] = useState<TimeRange>('30d')
  const [assetData, setAssetData] = useState<AssetData[]>([])
  const [regimeData, setRegimeData] = useState<RegimeData[]>([])
  const [macroFeatures, setMacroFeatures] = useState<MacroFeature[]>([])
  const [macroSeries, setMacroSeries] = useState<MacroSeries[]>([])
  const [alphaNodes, setAlphaNodes] = useState<AlphaNode[]>([])
  const [iosModules, setIosModules] = useState<IosModule[]>([])
  const [scheduledTasks, setScheduledTasks] = useState<ScheduledTasksData | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedAssets, setSelectedAssets] = useState<string[]>(['BTC-USD', 'ETH-USD', 'SPY'])

  // Fetch all data
  useEffect(() => {
    async function fetchAllData() {
      setLoading(true)

      const range = TIME_RANGES.find(r => r.value === timeRange)
      const endDate = new Date()
      const startDate = new Date()
      startDate.setDate(startDate.getDate() - (range?.days || 30))

      // Fetch price data for all assets
      const assetResults: AssetData[] = []
      for (const asset of ALL_ASSETS) {
        try {
          const response = await fetch(
            `/api/market/price-series?` +
              new URLSearchParams({
                ticker: asset.ticker,
                resolution: '1d',
                startDate: startDate.toISOString(),
                endDate: endDate.toISOString(),
              })
          )

          if (response.ok) {
            const data: OHLCVData[] = await response.json()
            const latestPrice = data.length > 0 ? data[data.length - 1].close : null
            const prevPrice = data.length > 1 ? data[data.length - 2].close : null
            const change24h = latestPrice && prevPrice
              ? ((latestPrice - prevPrice) / prevPrice) * 100
              : null

            assetResults.push({
              ticker: asset.ticker,
              name: asset.name,
              data,
              latestDate: data.length > 0 ? data[data.length - 1].date : null,
              dataPoints: data.length,
              latestPrice,
              change24h,
            })
          }
        } catch (err) {
          console.error(`Error fetching ${asset.ticker}:`, err)
        }
      }
      setAssetData(assetResults)

      // Fetch regime data
      try {
        const regimeResponse = await fetch('/api/sandbox/regimes')
        if (regimeResponse.ok) {
          const regimes = await regimeResponse.json()
          setRegimeData(regimes)
        }
      } catch (err) {
        console.error('Error fetching regimes:', err)
      }

      // Fetch macro features
      try {
        const macroResponse = await fetch('/api/sandbox/macro-features')
        if (macroResponse.ok) {
          const { features, series } = await macroResponse.json()
          setMacroFeatures(features || [])
          setMacroSeries(series || [])
        }
      } catch (err) {
        console.error('Error fetching macro features:', err)
      }

      // Fetch alpha nodes
      try {
        const nodesResponse = await fetch('/api/sandbox/alpha-nodes')
        if (nodesResponse.ok) {
          const nodes = await nodesResponse.json()
          setAlphaNodes(nodes)
        }
      } catch (err) {
        console.error('Error fetching alpha nodes:', err)
      }

      // Fetch IoS Registry
      try {
        const iosResponse = await fetch('/api/sandbox/ios-registry')
        if (iosResponse.ok) {
          const modules = await iosResponse.json()
          setIosModules(modules)
        }
      } catch (err) {
        console.error('Error fetching IoS registry:', err)
      }

      // Fetch Scheduled Tasks
      try {
        const scheduledResponse = await fetch('/api/sandbox/scheduled-tasks')
        if (scheduledResponse.ok) {
          const data = await scheduledResponse.json()
          setScheduledTasks(data)
        }
      } catch (err) {
        console.error('Error fetching scheduled tasks:', err)
      }

      setLoading(false)
    }

    fetchAllData()
  }, [timeRange])

  // Toggle asset selection
  const toggleAsset = (ticker: string) => {
    setSelectedAssets(prev =>
      prev.includes(ticker)
        ? prev.filter(t => t !== ticker)
        : [...prev, ticker]
    )
  }

  // Normalize data to percentage returns
  const normalizedData = normalizeToReturns(
    assetData.filter(a => selectedAssets.includes(a.ticker))
  )

  // Get series config for selected assets
  const seriesConfig: LineSeriesConfig[] = ALL_ASSETS
    .filter(a => selectedAssets.includes(a.ticker))
    .map(asset => ({
      dataKey: asset.dbId,
      name: asset.name,
      color: asset.color,
      strokeWidth: 2,
    }))

  return (
    <div className="space-y-6">
      {/* ===== MARKET OVERVIEW HEADER ===== */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {assetData.map(asset => {
          const config = ALL_ASSETS.find(a => a.ticker === asset.ticker)
          const isSelected = selectedAssets.includes(asset.ticker)

          return (
            <button
              key={asset.ticker}
              onClick={() => toggleAsset(asset.ticker)}
              className="p-3 rounded-lg border transition-all text-left"
              style={{
                backgroundColor: isSelected ? 'hsl(var(--primary) / 0.1)' : 'hsl(var(--card))',
                borderColor: isSelected ? config?.color : 'hsl(var(--border))',
                borderWidth: isSelected ? '2px' : '1px',
              }}
            >
              <div className="flex items-center gap-2 mb-1">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: config?.color }}
                />
                <span className="text-xs font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  {asset.ticker}
                </span>
              </div>
              <div className="text-lg font-bold">
                {asset.latestPrice
                  ? asset.ticker.includes('USD') && !asset.ticker.includes('EUR')
                    ? `$${formatCompact(asset.latestPrice)}`
                    : formatCompact(asset.latestPrice)
                  : 'N/A'
                }
              </div>
              {asset.change24h !== null && (
                <div
                  className="text-xs font-medium flex items-center gap-1"
                  style={{ color: asset.change24h >= 0 ? '#22c55e' : '#ef4444' }}
                >
                  {asset.change24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {asset.change24h >= 0 ? '+' : ''}{asset.change24h.toFixed(2)}%
                </div>
              )}
            </button>
          )
        })}
      </div>

      {/* ===== MAIN PRICE CHART ===== */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <BarChart3 className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
              <CardTitle>Price Performance (Normalized)</CardTitle>
            </div>
            <div className="flex gap-1">
              {TIME_RANGES.map(range => (
                <button
                  key={range.value}
                  onClick={() => setTimeRange(range.value)}
                  className="px-3 py-1 text-xs font-medium rounded transition-all"
                  style={{
                    backgroundColor: timeRange === range.value
                      ? 'hsl(var(--primary))'
                      : 'hsl(var(--secondary))',
                    color: timeRange === range.value
                      ? 'hsl(var(--primary-foreground))'
                      : 'hsl(var(--muted-foreground))',
                  }}
                >
                  {range.label}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton className="h-80" />
          ) : normalizedData.length > 0 ? (
            <LineChart
              data={normalizedData}
              series={seriesConfig}
              resolution="1d"
              source="fhq_data.price_series"
              height={320}
              yAxisFormatter={(value) => `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`}
            />
          ) : (
            <div className="flex items-center justify-center h-80" style={{ color: 'hsl(var(--muted-foreground))' }}>
              <p>Select assets to compare</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== REGIME STATUS PANEL ===== */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Activity className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
            <CardTitle>HMM Regime Classification</CardTitle>
          </div>
          <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Hidden Markov Model regime detection from fhq_perception.regime_daily
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {regimeData.length > 0 ? regimeData.map(regime => (
              <div
                key={regime.asset_id}
                className="p-4 rounded-lg border"
                style={{
                  backgroundColor: 'hsl(var(--secondary))',
                  borderColor: REGIME_COLORS[regime.regime_classification] || 'hsl(var(--border))',
                  borderWidth: '2px',
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold">{regime.asset_id}</span>
                  <StatusBadge
                    variant={regime.regime_classification.includes('BULL') ? 'pass' :
                            regime.regime_classification.includes('BEAR') ? 'fail' : 'info'}
                  >
                    {regime.regime_classification.replace(/_/g, ' ')}
                  </StatusBadge>
                </div>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span style={{ color: 'hsl(var(--muted-foreground))' }}>Confidence</span>
                    <span className="font-mono">{(regime.regime_confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: 'hsl(var(--muted-foreground))' }}>Confirms</span>
                    <span className="font-mono">{regime.consecutive_confirms}</span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: 'hsl(var(--muted-foreground))' }}>Stable</span>
                    {regime.regime_stability_flag
                      ? <CheckCircle className="w-4 h-4 text-green-400" />
                      : <AlertTriangle className="w-4 h-4 text-yellow-400" />
                    }
                  </div>
                </div>
              </div>
            )) : (
              <div className="col-span-4 text-center py-8" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Loading regime data...
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ===== IOS REGISTRY ===== */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Layers className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
            <CardTitle>Intelligence Operating System (IoS)</CardTitle>
          </div>
          <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            {iosModules.length} modules from fhq_meta.ios_registry — the modular architecture powering FjordHQ
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {iosModules.length > 0 ? iosModules.map(module => {
              const config = IOS_CONFIG[module.ios_id] || { icon: Layers, color: '#6b7280' }
              const IconComponent = config.icon

              // Determine governance state badge variant
              const getGovernanceVariant = (state: string) => {
                if (state === 'G4_ACTIVATED' || state === 'ACTIVATED') return 'pass'
                if (state === 'G3_AUDITED' || state === 'G3_PASSED') return 'fresh'
                if (state === 'G2_REVIEWED') return 'info'
                if (state === 'G1_VALIDATED') return 'info'
                if (state === 'G0_SUBMITTED') return 'stale'
                if (state === 'DEVELOPMENT') return 'warning'
                return 'stale'
              }

              // Determine status variant
              const getStatusVariant = (status: string) => {
                if (status === 'ACTIVE' || status === 'PRODUCTION') return 'pass'
                if (status === 'PENDING' || status === 'REVIEW') return 'info'
                if (status === 'DEPRECATED') return 'fail'
                return 'stale'
              }

              return (
                <div
                  key={module.ios_id}
                  className="p-4 rounded-lg border transition-all hover:shadow-md"
                  style={{
                    backgroundColor: 'hsl(var(--card))',
                    borderColor: config.color,
                    borderWidth: '2px',
                    borderLeftWidth: '4px',
                  }}
                >
                  {/* Header */}
                  <div className="flex items-start gap-3 mb-3">
                    <div
                      className="p-2 rounded-lg"
                      style={{ backgroundColor: `${config.color}20` }}
                    >
                      <IconComponent className="w-5 h-5" style={{ color: config.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm" style={{ color: config.color }}>
                          {module.ios_id}
                        </span>
                        <StatusBadge variant={getGovernanceVariant(module.governance_state)}>
                          {module.governance_state?.replace(/_/g, ' ') || 'UNKNOWN'}
                        </StatusBadge>
                      </div>
                      <h3 className="text-sm font-semibold mt-1 truncate" title={module.title}>
                        {module.title}
                      </h3>
                    </div>
                  </div>

                  {/* Human Role Explanation */}
                  <p className="text-xs leading-relaxed mb-3" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {module.human_role}
                  </p>

                  {/* Footer */}
                  <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: 'hsl(var(--border))' }}>
                    <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                      Owner: <span className="font-medium">{module.owner_role}</span>
                    </span>
                    <StatusBadge variant={getStatusVariant(module.status)}>
                      {module.status}
                    </StatusBadge>
                  </div>
                </div>
              )
            }) : (
              <div className="col-span-3 text-center py-8" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Loading IoS modules...
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ===== SCHEDULED TASKS ===== */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
            <CardTitle>Orchestrator Schedules</CardTitle>
          </div>
          <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Task automation status from fhq_governance.task_registry
          </p>
        </CardHeader>
        <CardContent>
          {scheduledTasks ? (
            <div className="space-y-6">
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                  <div className="text-2xl font-bold" style={{ color: '#22c55e' }}>
                    {scheduledTasks.summary.scheduled_count}
                  </div>
                  <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    Scheduled Tasks
                  </div>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                  <div className="text-2xl font-bold" style={{ color: '#f59e0b' }}>
                    {scheduledTasks.summary.unscheduled_vision_functions}
                  </div>
                  <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    Missing Schedules
                  </div>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                  <div className="text-2xl font-bold">
                    {scheduledTasks.summary.total_active}
                  </div>
                  <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    Total Active Tasks
                  </div>
                </div>
                <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                  <div className="text-2xl font-bold" style={{ color: '#6b7280' }}>
                    {scheduledTasks.summary.other_tasks}
                  </div>
                  <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    Other Tasks
                  </div>
                </div>
              </div>

              {/* Scheduled Tasks Table */}
              <div>
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                  <CheckCircle className="w-4 h-4" style={{ color: '#22c55e' }} />
                  Scheduled (Running Automatically)
                </h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                        <th className="text-left py-2 px-3">Task</th>
                        <th className="text-left py-2 px-3">Cron</th>
                        <th className="text-left py-2 px-3">Schedule</th>
                        <th className="text-left py-2 px-3">Owner</th>
                        <th className="text-right py-2 px-3">Runs</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scheduledTasks.scheduled.map(task => (
                        <tr key={task.task_name} style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                          <td className="py-2 px-3 font-mono text-xs">{task.task_name}</td>
                          <td className="py-2 px-3 font-mono text-xs" style={{ color: '#22c55e' }}>
                            {task.schedule_cron}
                          </td>
                          <td className="py-2 px-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                            {task.schedule_description}
                          </td>
                          <td className="py-2 px-3 text-xs">{task.owned_by_agent}</td>
                          <td className="py-2 px-3 text-right font-mono text-xs">
                            {task.run_count ?? 0}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Unscheduled Tasks */}
              {scheduledTasks.unscheduled.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" style={{ color: '#f59e0b' }} />
                    Vision Functions Without Schedules
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {scheduledTasks.unscheduled.map(task => (
                      <div
                        key={task.task_name}
                        className="p-2 rounded border text-xs"
                        style={{
                          backgroundColor: 'hsl(var(--card))',
                          borderColor: '#f59e0b',
                          borderWidth: '1px',
                        }}
                      >
                        <div className="font-mono truncate" title={task.task_name}>
                          {task.task_name}
                        </div>
                        <div style={{ color: 'hsl(var(--muted-foreground))' }}>
                          Owner: {task.owned_by_agent}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Loading scheduled tasks...
            </div>
          )}
        </CardContent>
      </Card>

      {/* ===== MACRO FEATURES GRID ===== */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Globe className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
            <CardTitle>Macro Feature Registry</CardTitle>
          </div>
          <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            {macroFeatures.length} features from fhq_macro.feature_registry
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Group by cluster */}
            {['LIQUIDITY', 'FACTOR', 'VOLATILITY', 'CREDIT', 'ONCHAIN', 'OTHER'].map(cluster => {
              const clusterFeatures = macroFeatures.filter(f => f.cluster === cluster)
              if (clusterFeatures.length === 0) return null

              return (
                <div key={cluster}>
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className="w-3 h-3 rounded"
                      style={{ backgroundColor: CLUSTER_COLORS[cluster] || '#6b7280' }}
                    />
                    <span className="text-sm font-semibold">{cluster}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{
                      backgroundColor: 'hsl(var(--secondary))',
                      color: 'hsl(var(--muted-foreground))'
                    }}>
                      {clusterFeatures.length}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 ml-5">
                    {clusterFeatures.map(feature => {
                      const series = macroSeries.find(s => s.feature_id === feature.feature_id)
                      const records = series ? Number(series.records) : 0

                      // Determine status badge variant based on actual status
                      const getStatusVariant = (status: string) => {
                        if (status === 'CANONICAL') return 'pass'
                        if (status === 'ACTIVE') return 'fresh'
                        if (status === 'REDUNDANT_BACKUP') return 'info'
                        if (status === 'CANDIDATE') return 'info'
                        if (status === 'DEFERRED') return 'stale'
                        if (status === 'PENDING_FIX') return 'warning'
                        if (status.includes('REJECTED')) return 'fail'
                        return 'stale'
                      }

                      return (
                        <div
                          key={feature.feature_id}
                          className="p-2 rounded border text-xs"
                          style={{
                            backgroundColor: 'hsl(var(--card))',
                            borderColor: 'hsl(var(--border))',
                            opacity: records === 0 ? 0.6 : 1,
                          }}
                        >
                          <div className="flex items-center justify-between gap-2 flex-nowrap">
                            <span className="font-medium truncate flex-1" title={feature.feature_name}>
                              {feature.feature_name}
                            </span>
                            <StatusBadge variant={getStatusVariant(feature.status)}>
                              {feature.status.replace(/_/g, ' ')}
                            </StatusBadge>
                          </div>
                          <div className="mt-1 text-xs whitespace-nowrap" style={{ color: 'hsl(var(--muted-foreground))' }}>
                            {records > 0 ? (
                              <span>{records.toLocaleString()} pts · {feature.frequency}</span>
                            ) : (
                              <span>
                                <span style={{ color: 'hsl(var(--destructive))' }}>No data</span>
                                {' · '}{feature.frequency}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* ===== ALPHA GRAPH NODES ===== */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
            <CardTitle>Alpha Graph Architecture</CardTitle>
          </div>
          <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Signal nodes from fhq_graph.nodes
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {['MACRO', 'REGIME', 'ASSET', 'FUTURE'].map(nodeType => {
              const typeNodes = alphaNodes.filter(n => n.node_type === nodeType)
              const typeColor = nodeType === 'MACRO' ? '#3b82f6' :
                               nodeType === 'REGIME' ? '#8b5cf6' :
                               nodeType === 'ASSET' ? '#22c55e' : '#6b7280'

              return (
                <div
                  key={nodeType}
                  className="p-3 rounded-lg border"
                  style={{
                    backgroundColor: 'hsl(var(--secondary))',
                    borderColor: typeColor,
                    borderWidth: '2px',
                  }}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: typeColor }} />
                    <span className="text-sm font-bold">{nodeType}</span>
                  </div>
                  <div className="space-y-1">
                    {typeNodes.map(node => (
                      <div
                        key={node.node_id}
                        className="text-xs flex items-center justify-between"
                      >
                        <span>{node.label}</span>
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{
                            backgroundColor: node.status === 'ACTIVE' ? '#22c55e' : '#6b7280'
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* ===== DATA COLLECTION SUMMARY ===== */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
            <CardTitle>Data Collection Summary</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                  <th className="text-left py-2 px-3">Asset</th>
                  <th className="text-left py-2 px-3">Type</th>
                  <th className="text-right py-2 px-3">Records</th>
                  <th className="text-right py-2 px-3">Latest</th>
                  <th className="text-right py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {assetData.map(asset => {
                  const config = ALL_ASSETS.find(a => a.ticker === asset.ticker)
                  return (
                    <tr
                      key={asset.ticker}
                      style={{ borderBottom: '1px solid hsl(var(--border))' }}
                    >
                      <td className="py-2 px-3">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: config?.color }}
                          />
                          <span className="font-medium">{asset.name}</span>
                        </div>
                      </td>
                      <td className="py-2 px-3 capitalize" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        {config?.type}
                      </td>
                      <td className="py-2 px-3 text-right font-mono">
                        {asset.dataPoints}
                      </td>
                      <td className="py-2 px-3 text-right font-mono text-xs">
                        {asset.latestDate
                          ? new Date(asset.latestDate).toLocaleDateString()
                          : 'N/A'
                        }
                      </td>
                      <td className="py-2 px-3 text-right">
                        <StatusBadge variant={asset.dataPoints > 0 ? 'pass' : 'fail'}>
                          {asset.dataPoints > 0 ? 'OK' : 'MISSING'}
                        </StatusBadge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

// =============================================================================
// UTILITIES
// =============================================================================

function normalizeToReturns(assetData: AssetData[]): Array<Record<string, any>> {
  if (assetData.length === 0) return []

  const referenceAsset = assetData.reduce((max, asset) =>
    asset.data.length > max.data.length ? asset : max
  , assetData[0])

  if (referenceAsset.data.length === 0) return []

  const dateMap = new Map<string, Record<string, any>>()

  referenceAsset.data.forEach(d => {
    const dateKey = d.date.split('T')[0].split(' ')[0]
    dateMap.set(dateKey, { date: d.date })
  })

  assetData.forEach(asset => {
    if (asset.data.length === 0) return

    const startPrice = asset.data[0].close
    const config = ALL_ASSETS.find(a => a.ticker === asset.ticker)
    const key = config?.dbId || asset.ticker.replace('-', '_')

    asset.data.forEach(d => {
      const dateKey = d.date.split('T')[0].split(' ')[0]
      const entry = dateMap.get(dateKey)
      if (entry) {
        const returnPct = ((d.close - startPrice) / startPrice) * 100
        entry[key] = returnPct
      }
    })
  })

  return Array.from(dateMap.values())
    .filter(entry => Object.keys(entry).length > 1)
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
}

function formatCompact(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return 'N/A'
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return 'N/A'
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(2)}K`
  if (num >= 1) return num.toFixed(2)
  return num.toFixed(4)
}
