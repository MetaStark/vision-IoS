'use client'

/**
 * CCO Dashboard - WAVE 17A
 * ========================
 * Central Context Orchestrator Live Status
 *
 * Shows:
 * - CCO operational state (INIT/OPERATIONAL/DEGRADED/UNAVAILABLE)
 * - Global permit status (UNKNOWN/PERMITTED/SUPPRESSED)
 * - Context freshness and provenance
 * - Signal readiness
 * - State transitions
 */

import { useEffect, useState } from 'react'
import {
  RefreshCw,
  Activity,
  ShieldCheck,
  ShieldAlert,
  ShieldOff,
  Clock,
  Hash,
  Target,
  ArrowRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Zap,
  Eye,
  Server,
  Sparkles,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Layers,
  DollarSign,
  ChevronDown,
  ChevronUp,
  Crosshair,
  Shield,
  Wallet
} from 'lucide-react'

interface CCOState {
  status: string
  globalPermit: string
  contextHash: string | null
  inputHash: string | null
  sourceTables: string[] | null
  validUntil: string | null
  permitReason: string | null
  permitAttribution: string | null
  contextTimestamp: string | null
  updatedAt: string | null
  contextAgeSeconds: number
  defconLevel: number | null
  defconBlocksExecution: boolean | null
  currentRegime: string | null
  currentRegimeConfidence: number | null
  currentVolPercentile: number | null
  currentVolState: string | null
  currentLiquidityState: string | null
  currentMarketHours: boolean | null
  contextDetails: any
}

interface SignalSummary {
  DORMANT: number
  ARMED: number
  EXECUTED: number
  EXPIRED: number
  total: number
}

interface Transition {
  needle_id: string
  from_state: string
  to_state: string
  transition_trigger: string
  context_snapshot: any
  cco_status: string
  transition_valid: boolean
  transitioned_at: string
}

interface ExitCriteria {
  totalPaperTrades: number
  paperSharpe: number
  paperMaxDrawdown: number
  paperWinRate: number
  paperDurationDays: number
  passesMinTrades: boolean
  passesSharpe: boolean
  passesDrawdown: boolean
  passesWinRate: boolean
  passesDuration: boolean
  allCriteriaPassed: boolean
  g5EligibleSince: string | null
  vegaAttestation: string
  vegaAttestationAt: string | null
  ceoTwoManRule: boolean
  liveActivationAuthorized: boolean
  lastUpdated: string
}

interface DaemonHealth {
  status: string
  contextAgeSeconds: number
  triggeredDegraded: boolean
  triggeredUnavailable: boolean
  triggeredDefcon: boolean
  defconLevelSet: number | null
  recoveredToOperational: boolean
  signalsBlockedCount: number
  signalsAllowedCount: number
  checkTimestamp: string
}

interface GoldenNeedleSummary {
  totalNeedles: number
  currentNeedles: number
  avgEqs: number
  avgFactors: number
  oldestNeedle: string | null
  newestNeedle: string | null
  tierCounts?: {
    gold: number
    silver: number
    bronze: number
    below: number
  }
}

interface NeedleCategory {
  category: string
  count: number
  avgEqs: number
}

interface GoldenNeedle {
  needleId: string
  title: string
  category: string
  eqsScore: number
  tier?: 'GOLD' | 'SILVER' | 'BRONZE' | 'BELOW'
  confluenceFactors: number
  sitcConfidence: string
  regimeTechnical: string
  regimeSovereign: string
  priceWitnessSymbol: string
  priceWitnessValue: number
  defconLevel: number
  expectedTimeframeDays: number | null
  createdAt: string
}

interface TradesSummary {
  totalTrades: number
  closedTrades: number
  openTrades: number
  wins: number
  losses: number
  totalPnl: number
  avgPnlPct: number
  avgHoldingPeriods: number
  winRate: number
}

interface PaperTrade {
  tradeId: string
  needleId: string
  symbol: string
  direction: string
  entryPrice: number
  exitPrice: number | null
  positionSize: number
  entryRegime: string
  entryContext: any
  exitTrigger: string | null
  pnlAbsolute: number | null
  pnlPercent: number | null
  holdingPeriods: number | null
  tradeOutcome: string | null
  entryTimestamp: string
  exitTimestamp: string | null
  // Golden Needle details
  needleTitle: string | null
  needleCategory: string | null
  needleEqs: number | null
  needleConfluence: number | null
  needleSitcConfidence: string | null
  expectedTimeframeDays: number | null
  // Calculated targets
  targetPrice: number
  stopLossPrice: number
  targetPct: number
  stopLossPct: number
}

interface CCOData {
  ccoState: CCOState | null
  signalSummary: SignalSummary
  transitions: Transition[]
  exitCriteria: ExitCriteria | null
  daemonHealth: DaemonHealth | null
  goldenNeedles: {
    summary: GoldenNeedleSummary | null
    byCategory: NeedleCategory[]
    recent: GoldenNeedle[]
  }
  paperTrades: {
    summary: TradesSummary | null
    recent: PaperTrade[]
  }
  timestamp: string
}

// WAVE 17B - Promotion Funnel Interfaces
interface PromotionFunnelData {
  intake: {
    totalNeedles: number
    needles24h: number
    needlesPerHour: number
    avgEqs: number
    minEqs: number
    maxEqs: number
    gateAPassRate: number
  }
  validationQueue: {
    awaitingValidation: number
    admissibleCandidates: number
    rejectedAdmissibility: number
    rejectionReasons: {
      sitcNotHigh: number
      eqsBelow085: number
      noVegaEvidence: number
      noCanonical: number
    }
    rejectionBreakdown: Array<{ reason: string; count: number }>
  }
  signalArsenal: {
    DORMANT: { count: number; latestEntry?: string; oldestEntry?: string }
    PRIMED: { count: number; latestEntry?: string; oldestEntry?: string }
    ARMED: { count: number; latestEntry?: string; oldestEntry?: string }
    EXECUTING: { count: number; latestEntry?: string; oldestEntry?: string }
    POSITION: { count: number; latestEntry?: string; oldestEntry?: string }
    COOLING: { count: number; latestEntry?: string; oldestEntry?: string }
    EXPIRED: { count: number; latestEntry?: string; oldestEntry?: string }
    total: number
  }
  governanceLedger: Array<{
    promotionId: string
    needleId: string
    currentStatus: string
    gateAPassed: boolean
    gateARejection: string | null
    gateBPassed: boolean | null
    gateBRejection: string | null
    gateCPassed: boolean | null
    signalId: string | null
    evidenceHash: string | null
    signedBy: string | null
    createdAt: string
  }>
  timestamp: string
}

// WAVE 17C - Pipeline Status Interface
interface PipelineStatusData {
  pipeline: {
    state: string
    shadowModeEnabled: boolean
    shadowModeUntil: string | null
    shadowReviewCount: number
    shadowReviewRequired: number
    rampUpPercentage: number
    rampUpStage: number
    maxPromotionsPerHour: number
    rateLimitEnabled: boolean
    currentHourPromotions: number
    pausedAt: string | null
    pausedReason: string | null
  }
  shadow: {
    total: number
    wouldPass: number
    wouldReject: number
    reviewed: number
    avgMs: number
    maxMs: number
    passRate: number
  }
  drift: {
    avgEqs: number
    needleCount: number
    signalCount: number
    conversionRate: number
    eqsThreshold: number
    conversionThreshold: number
    eqsBreach: boolean
    conversionBreach: boolean
    driftDetected: boolean
  } | null
  sla: {
    totalPromotions: number
    evidenceBreaches: number
    gateABreaches: number
    totalBreaches: number
    avgEvidenceMs: number
    avgGateAMs: number
    avgTotalMs: number
    maxTotalMs: number
    complianceRate: number
  }
  timestamp: string
}

function StatusBadge({ status, type }: { status: string; type: 'cco' | 'permit' | 'health' }) {
  let bgClass = 'bg-gray-500/20 text-gray-400'
  let icon = null

  if (type === 'cco') {
    switch (status) {
      case 'OPERATIONAL':
        bgClass = 'bg-green-500/20 text-green-400'
        icon = <ShieldCheck className="w-4 h-4" />
        break
      case 'INIT':
        bgClass = 'bg-blue-500/20 text-blue-400'
        icon = <Clock className="w-4 h-4" />
        break
      case 'DEGRADED':
        bgClass = 'bg-yellow-500/20 text-yellow-400'
        icon = <ShieldAlert className="w-4 h-4" />
        break
      case 'UNAVAILABLE':
        bgClass = 'bg-red-500/20 text-red-400'
        icon = <ShieldOff className="w-4 h-4" />
        break
    }
  } else if (type === 'permit') {
    switch (status) {
      case 'PERMITTED':
        bgClass = 'bg-green-500/20 text-green-400'
        icon = <CheckCircle2 className="w-4 h-4" />
        break
      case 'SUPPRESSED':
        bgClass = 'bg-yellow-500/20 text-yellow-400'
        icon = <AlertTriangle className="w-4 h-4" />
        break
      case 'UNKNOWN':
        bgClass = 'bg-gray-500/20 text-gray-400'
        icon = <Eye className="w-4 h-4" />
        break
    }
  } else if (type === 'health') {
    // Handle both 'HEALTHY' and 'OPERATIONAL' as good states
    if (status === 'HEALTHY' || status === 'OPERATIONAL') {
      bgClass = 'bg-green-500/20 text-green-400'
      icon = <CheckCircle2 className="w-4 h-4" />
    } else if (status === 'DEGRADED') {
      bgClass = 'bg-yellow-500/20 text-yellow-400'
      icon = <AlertTriangle className="w-4 h-4" />
    } else if (status === 'UNAVAILABLE' || status === 'ERROR') {
      bgClass = 'bg-red-500/20 text-red-400'
      icon = <XCircle className="w-4 h-4" />
    } else {
      // Unknown status - show neutral
      bgClass = 'bg-gray-500/20 text-gray-400'
      icon = <Eye className="w-4 h-4" />
    }
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-semibold ${bgClass}`}>
      {icon}
      {status}
    </span>
  )
}

function formatAge(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('nb-NO', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return dateStr
  }
}

// Tooltip component for parameter explanations
function Tooltip({ children, text }: { children: React.ReactNode; text: string }) {
  const [show, setShow] = useState(false)
  return (
    <span
      className="relative cursor-help"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs text-white bg-gray-900 rounded-lg shadow-lg w-48 text-center">
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </span>
      )}
    </span>
  )
}

// Live position data interface
interface LivePosition {
  symbol: string
  qty: number
  avgEntryPrice: number
  currentPrice: number
  marketValue: number
  unrealizedPl: number
  unrealizedPlPct: number
  side: string
  changeToday: number
}

export default function CCOPage() {
  const [data, setData] = useState<CCOData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedTradeId, setExpandedTradeId] = useState<string | null>(null)
  const [livePositions, setLivePositions] = useState<LivePosition[]>([])
  const [needlesPage, setNeedlesPage] = useState(0)
  const [needlesPerPage] = useState(10)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  // WAVE 17B - Promotion Funnel State
  const [promotionData, setPromotionData] = useState<PromotionFunnelData | null>(null)
  // WAVE 17C - Pipeline Status State
  const [pipelineData, setPipelineData] = useState<PipelineStatusData | null>(null)

  // Fetch live positions from Alpaca
  async function fetchLivePositions() {
    try {
      const res = await fetch('/api/alpaca/positions')
      if (res.ok) {
        const json = await res.json()
        setLivePositions(json.positions || [])
      }
    } catch (e) {
      console.error('Failed to fetch live positions:', e)
    }
  }

  // Get live position for a symbol
  function getLivePosition(symbol: string): LivePosition | null {
    return livePositions.find(p => p.symbol === symbol) || null
  }

  // Generate human-readable trade summary (simplified and clear)
  function generateTradeSummary(trade: PaperTrade): string {
    const symbol = trade.symbol
    const direction = trade.direction === 'LONG' ? 'bought' : 'shorted'
    const category = (trade.needleCategory || '').toLowerCase()

    // Simple, clear explanations based on strategy type
    if (category.includes('breakout') || category.includes('volatility') || category.includes('regime')) {
      return `We ${direction} ${symbol} because the price was coiling tightly (low volatility) and our system detected a breakout is likely. This pattern often leads to strong directional moves.`
    } else if (category.includes('reversion') || category.includes('mean')) {
      return `We ${direction} ${symbol} because the price moved too far from its average. Our system expects it to snap back toward fair value.`
    } else if (category.includes('catalyst')) {
      return `We ${direction} ${symbol} based on a catalyst event. Multiple factors aligned suggesting momentum will continue in this direction.`
    } else if (category.includes('momentum') || category.includes('trend')) {
      return `We ${direction} ${symbol} to ride an existing trend. The momentum is strong and our system expects it to continue.`
    } else {
      return `We ${direction} ${symbol} based on a high-confidence signal. Multiple technical factors aligned at the same time, suggesting a good risk/reward opportunity.`
    }
  }

  async function fetchData() {
    setLoading(true)
    try {
      const res = await fetch('/api/cco/status')
      if (!res.ok) throw new Error('Failed to fetch CCO status')
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  // WAVE 17B - Fetch Promotion Funnel Data
  async function fetchPromotionData() {
    try {
      const res = await fetch('/api/cco/promotion')
      if (res.ok) {
        const json = await res.json()
        setPromotionData(json)
      }
    } catch (e) {
      console.error('Failed to fetch promotion data:', e)
    }
  }

  // WAVE 17C - Fetch Pipeline Status Data
  async function fetchPipelineData() {
    try {
      const res = await fetch('/api/cco/pipeline')
      if (res.ok) {
        const json = await res.json()
        setPipelineData(json)
      }
    } catch (e) {
      console.error('Failed to fetch pipeline data:', e)
    }
  }

  useEffect(() => {
    fetchData()
    fetchLivePositions()
    fetchPromotionData()
    fetchPipelineData()
    // Auto-refresh every 10 seconds (matches daemon interval)
    const interval = setInterval(() => {
      fetchData()
      fetchLivePositions()
      fetchPromotionData()
      fetchPipelineData()
    }, 10000)
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
            Central Context Orchestrator
          </h1>
          <p className="text-[hsl(var(--muted-foreground))]">
            WAVE 17B - Promotion Control Room
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
          {/* Market Conditions Panel - TOP PRIORITY DISPLAY */}
          {data.ccoState?.contextDetails && (
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Eye className="w-5 h-5 text-[hsl(var(--primary))]" />
                <h3 className="font-semibold text-[hsl(var(--foreground))]">Market Conditions</h3>
                <span className="ml-auto text-xs text-[hsl(var(--muted-foreground))]">
                  {data.ccoState.contextDetails.symbol || 'BTC-USD'}
                </span>
              </div>

              {/* Why Trading is Suppressed/Permitted */}
              <div className={`p-4 rounded-lg mb-4 ${
                data.ccoState.globalPermit === 'PERMITTED'
                  ? 'bg-green-500/10 border border-green-500/30'
                  : 'bg-yellow-500/10 border border-yellow-500/30'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  {data.ccoState.globalPermit === 'PERMITTED' ? (
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-yellow-400" />
                  )}
                  <span className={`font-semibold ${
                    data.ccoState.globalPermit === 'PERMITTED' ? 'text-green-400' : 'text-yellow-400'
                  }`}>
                    {data.ccoState.globalPermit === 'PERMITTED' ? 'Trading Permitted' : 'Trading Paused'}
                  </span>
                </div>
                <p className="text-sm text-[hsl(var(--foreground))]">
                  {data.ccoState.permitReason || (
                    data.ccoState.globalPermit === 'SUPPRESSED'
                      ? 'Market conditions are outside the normal operating range. The system waits for volatility to return to neutral levels (30-70 percentile) before executing trades.'
                      : 'Market conditions are within normal operating parameters. Trading signals can be executed.'
                  )}
                </p>
              </div>

              {/* Market Indicators Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                {/* Regime */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Market Regime</p>
                  <div className="flex items-center gap-2">
                    {data.ccoState.contextDetails.regime === 'BULL' ? (
                      <TrendingUp className="w-5 h-5 text-green-400" />
                    ) : data.ccoState.contextDetails.regime === 'BEAR' ? (
                      <TrendingDown className="w-5 h-5 text-red-400" />
                    ) : (
                      <Activity className="w-5 h-5 text-yellow-400" />
                    )}
                    <span className={`text-lg font-bold ${
                      data.ccoState.contextDetails.regime === 'BULL' ? 'text-green-400' :
                      data.ccoState.contextDetails.regime === 'BEAR' ? 'text-red-400' :
                      'text-yellow-400'
                    }`}>
                      {data.ccoState.contextDetails.regime || 'NEUTRAL'}
                    </span>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {((data.ccoState.contextDetails.regime_confidence || 0) * 100).toFixed(0)}% confidence
                  </p>
                </div>

                {/* Volatility Percentile */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Volatility Level</p>
                  <div className="flex items-center gap-2">
                    <span className={`text-lg font-bold ${
                      (data.ccoState.contextDetails.vol_percentile || 0) < 30 ? 'text-blue-400' :
                      (data.ccoState.contextDetails.vol_percentile || 0) > 70 ? 'text-red-400' :
                      'text-green-400'
                    }`}>
                      {(data.ccoState.contextDetails.vol_percentile || 0).toFixed(1)}%
                    </span>
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {(data.ccoState.contextDetails.vol_percentile || 0) < 30 ? 'Unusually calm' :
                     (data.ccoState.contextDetails.vol_percentile || 0) > 70 ? 'High volatility' :
                     'Normal range'}
                  </p>
                </div>

                {/* Vol State */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Vol Trend</p>
                  <span className={`text-lg font-bold ${
                    data.ccoState.contextDetails.vol_state === 'STABLE' ? 'text-green-400' :
                    data.ccoState.contextDetails.vol_state === 'EXPANDING' ? 'text-yellow-400' :
                    data.ccoState.contextDetails.vol_state === 'CONTRACTING' ? 'text-blue-400' :
                    'text-gray-400'
                  }`}>
                    {data.ccoState.contextDetails.vol_state || 'UNKNOWN'}
                  </span>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {data.ccoState.contextDetails.vol_state === 'STABLE' ? 'Steady conditions' :
                     data.ccoState.contextDetails.vol_state === 'EXPANDING' ? 'Increasing risk' :
                     data.ccoState.contextDetails.vol_state === 'CONTRACTING' ? 'Calming down' :
                     'Monitoring'}
                  </p>
                </div>

                {/* Liquidity */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Liquidity</p>
                  <span className={`text-lg font-bold ${
                    data.ccoState.contextDetails.liquidity_state === 'NORMAL' ? 'text-green-400' :
                    data.ccoState.contextDetails.liquidity_state === 'THIN' ? 'text-yellow-400' :
                    data.ccoState.contextDetails.liquidity_state === 'CRISIS' ? 'text-red-400' :
                    'text-gray-400'
                  }`}>
                    {data.ccoState.contextDetails.liquidity_state || 'UNKNOWN'}
                  </span>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {data.ccoState.contextDetails.liquidity_state === 'NORMAL' ? 'Healthy trading' :
                     data.ccoState.contextDetails.liquidity_state === 'THIN' ? 'Reduced depth' :
                     data.ccoState.contextDetails.liquidity_state === 'CRISIS' ? 'Low liquidity' :
                     'Assessing'}
                  </p>
                </div>
              </div>

              {/* Volatility Gauge */}
              <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg mb-4">
                <p className="text-xs text-[hsl(var(--muted-foreground))] mb-2">Volatility Percentile (Trading Zone: 30-70%)</p>
                <div className="relative h-8 bg-[hsl(var(--card))] rounded-full overflow-hidden">
                  {/* Zones */}
                  <div className="absolute inset-0 flex">
                    <div className="w-[30%] bg-blue-500/20 border-r border-blue-500/50" />
                    <div className="w-[40%] bg-green-500/20" />
                    <div className="w-[30%] bg-red-500/20 border-l border-red-500/50" />
                  </div>
                  {/* Labels */}
                  <div className="absolute inset-0 flex items-center justify-between px-2 text-xs">
                    <span className="text-blue-400">Calm</span>
                    <span className="text-green-400 font-semibold">NEUTRAL ZONE</span>
                    <span className="text-red-400">Volatile</span>
                  </div>
                  {/* Marker */}
                  <div
                    className="absolute top-0 bottom-0 w-1 bg-white shadow-lg"
                    style={{ left: `${Math.min(100, Math.max(0, data.ccoState.contextDetails.vol_percentile || 0))}%` }}
                  >
                    <div className="absolute -top-6 left-1/2 -translate-x-1/2 px-1 py-0.5 bg-white text-black text-xs font-bold rounded">
                      {(data.ccoState.contextDetails.vol_percentile || 0).toFixed(0)}%
                    </div>
                  </div>
                </div>
                <div className="flex justify-between mt-1 text-xs text-[hsl(var(--muted-foreground))]">
                  <span>0%</span>
                  <span>30%</span>
                  <span>70%</span>
                  <span>100%</span>
                </div>
              </div>

              {/* Market Hours & Last Update */}
              <div className="flex items-center justify-between text-xs text-[hsl(var(--muted-foreground))]">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${
                    data.ccoState.contextDetails.market_hours ? 'bg-green-400' : 'bg-gray-400'
                  }`} />
                  <span>{data.ccoState.contextDetails.market_hours ? 'Markets Open' : 'Markets Closed'}</span>
                </div>
                <span>
                  Updated: {data.ccoState.contextDetails.computed_at
                    ? new Date(data.ccoState.contextDetails.computed_at).toLocaleTimeString('nb-NO')
                    : '-'}
                </span>
              </div>
            </div>
          )}

          {/* WAVE 17B - 4-Panel Control Room */}
          {promotionData && (
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Layers className="w-5 h-5 text-purple-400" />
                <h3 className="font-semibold text-[hsl(var(--foreground))]">Promotion Control Room</h3>
                <span className="ml-auto px-2 py-1 text-xs bg-purple-500/20 text-purple-400 rounded-lg font-mono">
                  WAVE 17B
                </span>
              </div>

              {/* 4-Panel Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Panel A: Intake (Needles) */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg border border-blue-500/30">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles className="w-4 h-4 text-blue-400" />
                    <h4 className="text-sm font-semibold text-blue-400">Panel A: Intake</h4>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-[hsl(var(--foreground))]">{promotionData.intake.totalNeedles}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Total Needles</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-blue-400">{promotionData.intake.needles24h}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Last 24h</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-cyan-400">{promotionData.intake.needlesPerHour.toFixed(1)}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Per Hour</p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-[hsl(var(--muted-foreground))]">EQS Range: {promotionData.intake.minEqs.toFixed(2)} - {promotionData.intake.maxEqs.toFixed(2)}</span>
                    <span className="text-yellow-400">Avg: {promotionData.intake.avgEqs.toFixed(3)}</span>
                  </div>
                  <div className="mt-2 h-2 bg-[hsl(var(--card))] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all"
                      style={{ width: `${Math.min(100, promotionData.intake.gateAPassRate)}%` }}
                    />
                  </div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    Gate A Pass Rate: <span className={promotionData.intake.gateAPassRate > 0 ? 'text-green-400' : 'text-red-400'}>{promotionData.intake.gateAPassRate.toFixed(1)}%</span>
                  </p>
                </div>

                {/* Panel B: Validation Queue */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg border border-yellow-500/30">
                  <div className="flex items-center gap-2 mb-3">
                    <Shield className="w-4 h-4 text-yellow-400" />
                    <h4 className="text-sm font-semibold text-yellow-400">Panel B: Validation Queue</h4>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-yellow-400">{promotionData.validationQueue.awaitingValidation}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Awaiting</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-green-400">{promotionData.validationQueue.admissibleCandidates}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Admissible</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-red-400">{promotionData.validationQueue.rejectedAdmissibility}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Rejected</p>
                    </div>
                  </div>
                  <div className="space-y-1 text-xs">
                    <p className="text-[hsl(var(--muted-foreground))]">Rejection Breakdown:</p>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="flex justify-between">
                        <span className="text-orange-400">No VEGA Evidence:</span>
                        <span className="text-orange-400 font-mono">{promotionData.validationQueue.rejectionReasons.noVegaEvidence}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-amber-400">EQS &lt; 0.85:</span>
                        <span className="text-amber-400 font-mono">{promotionData.validationQueue.rejectionReasons.eqsBelow085}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-yellow-400">SITC Not HIGH:</span>
                        <span className="text-yellow-400 font-mono">{promotionData.validationQueue.rejectionReasons.sitcNotHigh}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-red-400">No Canonical:</span>
                        <span className="text-red-400 font-mono">{promotionData.validationQueue.rejectionReasons.noCanonical}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Panel C: Signal Arsenal */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg border border-green-500/30">
                  <div className="flex items-center gap-2 mb-3">
                    <Crosshair className="w-4 h-4 text-green-400" />
                    <h4 className="text-sm font-semibold text-green-400">Panel C: Signal Arsenal</h4>
                    <span className="ml-auto text-xs text-[hsl(var(--muted-foreground))]">
                      Total: {promotionData.signalArsenal.total}
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 mb-3">
                    <div className="p-2 bg-blue-500/10 border border-blue-500/30 rounded text-center">
                      <p className="text-lg font-bold text-blue-400">{promotionData.signalArsenal.DORMANT?.count || 0}</p>
                      <p className="text-xs text-blue-400">DORMANT</p>
                    </div>
                    <div className="p-2 bg-yellow-500/10 border border-yellow-500/30 rounded text-center">
                      <p className="text-lg font-bold text-yellow-400">{promotionData.signalArsenal.PRIMED?.count || 0}</p>
                      <p className="text-xs text-yellow-400">PRIMED</p>
                    </div>
                    <div className="p-2 bg-green-500/10 border border-green-500/30 rounded text-center">
                      <p className="text-lg font-bold text-green-400">{promotionData.signalArsenal.ARMED?.count || 0}</p>
                      <p className="text-xs text-green-400">ARMED</p>
                    </div>
                    <div className="p-2 bg-purple-500/10 border border-purple-500/30 rounded text-center">
                      <p className="text-lg font-bold text-purple-400">{(promotionData.signalArsenal.EXECUTING?.count || 0) + (promotionData.signalArsenal.POSITION?.count || 0)}</p>
                      <p className="text-xs text-purple-400">ACTIVE</p>
                    </div>
                  </div>
                  <div className="flex justify-between text-xs text-[hsl(var(--muted-foreground))]">
                    <span>Cooling: {promotionData.signalArsenal.COOLING?.count || 0}</span>
                    <span>Expired: {promotionData.signalArsenal.EXPIRED?.count || 0}</span>
                  </div>
                </div>

                {/* Panel D: Governance Ledger */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg border border-purple-500/30">
                  <div className="flex items-center gap-2 mb-3">
                    <BarChart3 className="w-4 h-4 text-purple-400" />
                    <h4 className="text-sm font-semibold text-purple-400">Panel D: Governance Ledger</h4>
                  </div>
                  {promotionData.governanceLedger.length > 0 ? (
                    <div className="space-y-2 max-h-32 overflow-y-auto">
                      {promotionData.governanceLedger.slice(0, 5).map((entry, idx) => (
                        <div key={entry.promotionId || idx} className="flex items-center justify-between text-xs p-2 bg-[hsl(var(--card))] rounded">
                          <div>
                            <span className={`font-mono ${
                              entry.currentStatus === 'DORMANT_SIGNAL' ? 'text-green-400' :
                              entry.currentStatus?.includes('REJECT') ? 'text-red-400' :
                              'text-yellow-400'
                            }`}>
                              {entry.currentStatus}
                            </span>
                            <span className="text-[hsl(var(--muted-foreground))] ml-2">
                              {entry.needleId?.slice(0, 8)}...
                            </span>
                          </div>
                          <span className="text-[hsl(var(--muted-foreground))]">
                            {formatTime(entry.createdAt)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-24 text-[hsl(var(--muted-foreground))]">
                      <p className="text-sm">No promotion events yet</p>
                      <p className="text-xs mt-1">Needles awaiting Gate A evaluation</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Funnel Summary Bar */}
              <div className="mt-4 p-3 bg-[hsl(var(--card))] rounded-lg">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-4">
                    <span className="text-[hsl(var(--muted-foreground))]">Funnel Flow:</span>
                    <span className="text-blue-400">{promotionData.intake.totalNeedles} Needles</span>
                    <ArrowRight className="w-3 h-3 text-[hsl(var(--muted-foreground))]" />
                    <span className="text-yellow-400">{promotionData.validationQueue.admissibleCandidates} Candidates</span>
                    <ArrowRight className="w-3 h-3 text-[hsl(var(--muted-foreground))]" />
                    <span className="text-green-400">{promotionData.signalArsenal.DORMANT?.count || 0} Signals</span>
                  </div>
                  <span className="text-purple-400 font-mono">
                    Conv: {promotionData.intake.totalNeedles > 0
                      ? ((promotionData.signalArsenal.total / promotionData.intake.totalNeedles) * 100).toFixed(1)
                      : '0.0'}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* WAVE 17C - Pipeline Status Panel */}
          {pipelineData && (
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-5 h-5 text-cyan-400" />
                <h3 className="font-semibold text-[hsl(var(--foreground))]">Autonomous Pipeline</h3>
                <span className={`ml-2 px-2 py-1 text-xs rounded-lg font-mono ${
                  pipelineData.pipeline.state === 'SHADOW' ? 'bg-blue-500/20 text-blue-400' :
                  pipelineData.pipeline.state === 'ACTIVE' ? 'bg-green-500/20 text-green-400' :
                  pipelineData.pipeline.state === 'PAUSED' ? 'bg-yellow-500/20 text-yellow-400' :
                  pipelineData.pipeline.state === 'HALTED' ? 'bg-red-500/20 text-red-400' :
                  'bg-purple-500/20 text-purple-400'
                }`}>
                  {pipelineData.pipeline.state}
                </span>
                <span className="ml-auto px-2 py-1 text-xs bg-cyan-500/20 text-cyan-400 rounded-lg font-mono">
                  WAVE 17C
                </span>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                {/* Shadow Mode Status */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg border border-blue-500/30">
                  <div className="flex items-center gap-2 mb-3">
                    <Eye className="w-4 h-4 text-blue-400" />
                    <h4 className="text-sm font-semibold text-blue-400">Shadow Mode</h4>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Decisions</span>
                      <span className="text-[hsl(var(--foreground))] font-mono">{pipelineData.shadow.total}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Would Pass</span>
                      <span className="text-green-400 font-mono">{pipelineData.shadow.wouldPass}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Would Reject</span>
                      <span className="text-red-400 font-mono">{pipelineData.shadow.wouldReject}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Pass Rate</span>
                      <span className={`font-mono ${pipelineData.shadow.passRate >= 80 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {pipelineData.shadow.passRate.toFixed(1)}%
                      </span>
                    </div>
                    <div className="mt-2 h-2 bg-[hsl(var(--card))] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-green-400 rounded-full"
                        style={{ width: `${Math.min(100, (pipelineData.shadow.total / pipelineData.pipeline.shadowReviewRequired) * 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">
                      Review Progress: {pipelineData.shadow.total} / {pipelineData.pipeline.shadowReviewRequired}
                    </p>
                  </div>
                </div>

                {/* SLA Compliance */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg border border-green-500/30">
                  <div className="flex items-center gap-2 mb-3">
                    <Clock className="w-4 h-4 text-green-400" />
                    <h4 className="text-sm font-semibold text-green-400">SLA Compliance</h4>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Compliance</span>
                      <span className={`font-mono ${pipelineData.sla.complianceRate >= 99 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {pipelineData.sla.complianceRate.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Avg Total</span>
                      <span className={`font-mono ${pipelineData.sla.avgTotalMs < 1000 ? 'text-green-400' : 'text-yellow-400'}`}>
                        {pipelineData.sla.avgTotalMs.toFixed(0)}ms
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Max Total</span>
                      <span className={`font-mono ${pipelineData.sla.maxTotalMs < 30000 ? 'text-green-400' : 'text-red-400'}`}>
                        {pipelineData.sla.maxTotalMs}ms
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Breaches (24h)</span>
                      <span className={`font-mono ${pipelineData.sla.totalBreaches === 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {pipelineData.sla.totalBreaches}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-1 mt-2 text-xs">
                      <div className="p-1 bg-[hsl(var(--card))] rounded text-center">
                        <span className="text-[hsl(var(--muted-foreground))]">Evidence</span>
                        <p className="font-mono text-green-400">{pipelineData.sla.avgEvidenceMs.toFixed(0)}ms</p>
                      </div>
                      <div className="p-1 bg-[hsl(var(--card))] rounded text-center">
                        <span className="text-[hsl(var(--muted-foreground))]">Gate A</span>
                        <p className="font-mono text-green-400">{pipelineData.sla.avgGateAMs.toFixed(0)}ms</p>
                      </div>
                      <div className="p-1 bg-[hsl(var(--card))] rounded text-center">
                        <span className="text-[hsl(var(--muted-foreground))]">SLA</span>
                        <p className="font-mono text-blue-400">&lt;30s</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Rate Limiting & Drift */}
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg border border-yellow-500/30">
                  <div className="flex items-center gap-2 mb-3">
                    <BarChart3 className="w-4 h-4 text-yellow-400" />
                    <h4 className="text-sm font-semibold text-yellow-400">Safeguards</h4>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Rate Limit</span>
                      <span className="text-[hsl(var(--foreground))] font-mono">
                        {pipelineData.pipeline.currentHourPromotions}/{pipelineData.pipeline.maxPromotionsPerHour}/hr
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Ramp-Up</span>
                      <span className="text-purple-400 font-mono">{pipelineData.pipeline.rampUpPercentage}%</span>
                    </div>
                    {pipelineData.drift && (
                      <>
                        <div className="flex justify-between text-sm">
                          <span className="text-[hsl(var(--muted-foreground))]">7d Avg EQS</span>
                          <span className={`font-mono ${pipelineData.drift.eqsBreach ? 'text-red-400' : 'text-green-400'}`}>
                            {pipelineData.drift.avgEqs.toFixed(3)}
                          </span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-[hsl(var(--muted-foreground))]">Conversion</span>
                          <span className={`font-mono ${pipelineData.drift.conversionBreach ? 'text-red-400' : 'text-green-400'}`}>
                            {(pipelineData.drift.conversionRate * 100).toFixed(1)}%
                          </span>
                        </div>
                      </>
                    )}
                    <div className="flex justify-between text-sm">
                      <span className="text-[hsl(var(--muted-foreground))]">Drift Detected</span>
                      <span className={`font-mono ${pipelineData.drift?.driftDetected ? 'text-red-400' : 'text-green-400'}`}>
                        {pipelineData.drift?.driftDetected ? 'YES' : 'NO'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Pipeline Status Bar */}
              <div className="mt-4 p-3 bg-[hsl(var(--card))] rounded-lg">
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-4">
                    <span className={`flex items-center gap-1 ${pipelineData.pipeline.rateLimitEnabled ? 'text-green-400' : 'text-gray-400'}`}>
                      <div className={`w-2 h-2 rounded-full ${pipelineData.pipeline.rateLimitEnabled ? 'bg-green-400' : 'bg-gray-400'}`} />
                      Rate Limit
                    </span>
                    <span className={`flex items-center gap-1 ${pipelineData.pipeline.shadowModeEnabled ? 'text-blue-400' : 'text-gray-400'}`}>
                      <div className={`w-2 h-2 rounded-full ${pipelineData.pipeline.shadowModeEnabled ? 'bg-blue-400' : 'bg-gray-400'}`} />
                      Shadow
                    </span>
                    <span className="flex items-center gap-1 text-green-400">
                      <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                      Pipeline Active
                    </span>
                  </div>
                  <span className="text-[hsl(var(--muted-foreground))]">
                    {pipelineData.pipeline.shadowModeUntil && (
                      <>Shadow until: {new Date(pipelineData.pipeline.shadowModeUntil).toLocaleString('nb-NO')}</>
                    )}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Main Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* CCO Status */}
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-[hsl(var(--muted-foreground))]">
                  CCO STATUS
                </h3>
                <Activity className="w-5 h-5 text-[hsl(var(--primary))]" />
              </div>
              <StatusBadge status={data.ccoState?.status || 'UNKNOWN'} type="cco" />
              <p className="mt-3 text-xs text-[hsl(var(--muted-foreground))]">
                Last update: {formatTime(data.ccoState?.contextTimestamp)}
              </p>
            </div>

            {/* Global Permit */}
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-[hsl(var(--muted-foreground))]">
                  GLOBAL PERMIT
                </h3>
                <Target className="w-5 h-5 text-[hsl(var(--primary))]" />
              </div>
              <StatusBadge status={data.ccoState?.globalPermit || 'UNKNOWN'} type="permit" />
              {data.ccoState?.permitReason && (
                <p className="mt-3 text-xs text-[hsl(var(--muted-foreground))]">
                  {data.ccoState.permitReason}
                </p>
              )}
              {data.ccoState?.permitAttribution && (
                <p className="mt-1 text-xs font-mono text-yellow-400">
                  [{data.ccoState.permitAttribution}]
                </p>
              )}
            </div>

            {/* Context Age */}
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-medium text-[hsl(var(--muted-foreground))]">
                  CONTEXT AGE
                </h3>
                <Clock className="w-5 h-5 text-[hsl(var(--primary))]" />
              </div>
              <p className={`text-3xl font-bold ${
                (data.ccoState?.contextAgeSeconds || 0) > 15
                  ? 'text-yellow-400'
                  : 'text-green-400'
              }`}>
                {formatAge(data.ccoState?.contextAgeSeconds || 0)}
              </p>
              <p className="mt-3 text-xs text-[hsl(var(--muted-foreground))]">
                Threshold: 15s (DEGRADED)
              </p>
            </div>
          </div>

          {/* Signal Summary */}
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-5 h-5 text-[hsl(var(--primary))]" />
              <h3 className="font-semibold text-[hsl(var(--foreground))]">Signal Readiness</h3>
              <span className="ml-auto text-sm text-[hsl(var(--muted-foreground))]">
                {data.signalSummary.total} total signals
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-2xl font-bold text-blue-400">{data.signalSummary.DORMANT}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">DORMANT</p>
              </div>
              <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-2xl font-bold text-green-400">{data.signalSummary.ARMED}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">ARMED</p>
              </div>
              <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-2xl font-bold text-purple-400">{data.signalSummary.EXECUTED}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">EXECUTED</p>
              </div>
              <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-400">{data.signalSummary.EXPIRED}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">EXPIRED</p>
              </div>
            </div>
          </div>

          {/* Context Details & Daemon Health */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Context Provenance (ADR-013) */}
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Hash className="w-5 h-5 text-[hsl(var(--primary))]" />
                <h3 className="font-semibold text-[hsl(var(--foreground))]">Context Provenance</h3>
                <span className="ml-auto text-xs px-2 py-1 bg-[hsl(var(--secondary))] rounded">
                  ADR-013
                </span>
              </div>
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Context Hash</p>
                  <p className="font-mono text-xs text-[hsl(var(--foreground))] break-all">
                    {data.ccoState?.contextHash || '-'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Input Hash</p>
                  <p className="font-mono text-xs text-[hsl(var(--foreground))] break-all">
                    {data.ccoState?.inputHash || '-'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Source Tables</p>
                  <p className="font-mono text-xs text-[hsl(var(--foreground))]">
                    {data.ccoState?.sourceTables?.join(', ') || '-'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Valid Until</p>
                  <p className="text-sm text-[hsl(var(--foreground))]">
                    {formatTime(data.ccoState?.validUntil)}
                  </p>
                </div>
              </div>
            </div>

            {/* Daemon Health */}
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Server className="w-5 h-5 text-[hsl(var(--primary))]" />
                <h3 className="font-semibold text-[hsl(var(--foreground))]">Daemon Health</h3>
                {data.daemonHealth && (
                  <StatusBadge status={data.daemonHealth.status} type="health" />
                )}
              </div>
              {data.daemonHealth ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Signals Allowed</p>
                      <p className="text-lg font-bold text-green-400">
                        {data.daemonHealth.signalsAllowedCount}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Signals Blocked</p>
                      <p className={`text-lg font-bold ${
                        data.daemonHealth.signalsBlockedCount > 0 ? 'text-yellow-400' : 'text-gray-400'
                      }`}>
                        {data.daemonHealth.signalsBlockedCount}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className={`p-2 rounded ${data.daemonHealth.triggeredDegraded ? 'bg-yellow-500/20 text-yellow-400' : 'bg-[hsl(var(--secondary))] text-[hsl(var(--muted-foreground))]'}`}>
                      Degraded: {data.daemonHealth.triggeredDegraded ? 'Yes' : 'No'}
                    </div>
                    <div className={`p-2 rounded ${data.daemonHealth.triggeredUnavailable ? 'bg-red-500/20 text-red-400' : 'bg-[hsl(var(--secondary))] text-[hsl(var(--muted-foreground))]'}`}>
                      Unavailable: {data.daemonHealth.triggeredUnavailable ? 'Yes' : 'No'}
                    </div>
                    <div className={`p-2 rounded ${data.daemonHealth.triggeredDefcon ? 'bg-red-500/20 text-red-400' : 'bg-[hsl(var(--secondary))] text-[hsl(var(--muted-foreground))]'}`}>
                      DEFCON: {data.daemonHealth.triggeredDefcon ? `L${data.daemonHealth.defconLevelSet}` : 'No'}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">Last Check</p>
                    <p className="text-sm text-[hsl(var(--foreground))]">
                      {formatTime(data.daemonHealth.checkTimestamp)}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-[hsl(var(--muted-foreground))]">No daemon health data</p>
              )}
            </div>
          </div>

          {/* Exit Criteria Status - G5 Live Authorization */}
          {data.exitCriteria && (
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <CheckCircle2 className="w-5 h-5 text-[hsl(var(--primary))]" />
                <h3 className="font-semibold text-[hsl(var(--foreground))]">G5 Exit Criteria</h3>
                <span className={`ml-auto px-3 py-1 rounded-lg text-sm font-semibold ${
                  data.exitCriteria.allCriteriaPassed
                    ? 'bg-green-500/20 text-green-400'
                    : 'bg-yellow-500/20 text-yellow-400'
                }`}>
                  {data.exitCriteria.allCriteriaPassed ? 'ALL PASSED' : 'PENDING'}
                </span>
              </div>
              {/* Paper Trading Metrics */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                  <p className="text-xl font-bold text-[hsl(var(--foreground))]">{data.exitCriteria.totalPaperTrades}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Trades</p>
                </div>
                <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                  <p className={`text-xl font-bold ${data.exitCriteria.paperSharpe >= 1.5 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {data.exitCriteria.paperSharpe.toFixed(2)}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Sharpe</p>
                </div>
                <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                  <p className={`text-xl font-bold ${data.exitCriteria.paperMaxDrawdown <= 10 ? 'text-green-400' : 'text-red-400'}`}>
                    {data.exitCriteria.paperMaxDrawdown.toFixed(1)}%
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Max DD</p>
                </div>
                <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                  <p className={`text-xl font-bold ${data.exitCriteria.paperWinRate >= 55 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {data.exitCriteria.paperWinRate.toFixed(0)}%
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Win Rate</p>
                </div>
              </div>
              {/* Criteria Checks */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-4">
                {[
                  { label: 'Min Trades', pass: data.exitCriteria.passesMinTrades },
                  { label: 'Sharpe', pass: data.exitCriteria.passesSharpe },
                  { label: 'Drawdown', pass: data.exitCriteria.passesDrawdown },
                  { label: 'Win Rate', pass: data.exitCriteria.passesWinRate },
                  { label: 'Duration', pass: data.exitCriteria.passesDuration },
                ].map((c) => (
                  <div key={c.label} className={`p-2 rounded text-xs text-center ${
                    c.pass ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
                  }`}>
                    {c.pass ? <CheckCircle2 className="w-3 h-3 inline mr-1" /> : <XCircle className="w-3 h-3 inline mr-1" />}
                    {c.label}
                  </div>
                ))}
              </div>
              {/* Authorization Status */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">VEGA Attestation</p>
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-medium ${
                    data.exitCriteria.vegaAttestation === 'G5_PASS'
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-gray-500/20 text-gray-400'
                  }`}>
                    {data.exitCriteria.vegaAttestation === 'G5_PASS' && <CheckCircle2 className="w-3 h-3" />}
                    {data.exitCriteria.vegaAttestation || 'PENDING'}
                  </span>
                </div>
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">CEO Two-Man Rule</p>
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-medium ${
                    data.exitCriteria.ceoTwoManRule
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-yellow-500/20 text-yellow-400'
                  }`}>
                    {data.exitCriteria.ceoTwoManRule ? 'APPROVED' : 'AWAITING'}
                  </span>
                </div>
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Live Authorization</p>
                  <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-medium ${
                    data.exitCriteria.liveActivationAuthorized
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-red-500/20 text-red-400'
                  }`}>
                    {data.exitCriteria.liveActivationAuthorized ? 'AUTHORIZED' : 'BLOCKED'}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Live Broker Positions (Alpaca SOT) */}
          {livePositions.length > 0 && (
            <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
              <div className="flex items-center gap-2 mb-4">
                <Wallet className="w-5 h-5 text-emerald-400" />
                <h3 className="font-semibold text-[hsl(var(--foreground))]">Live Broker Positions</h3>
                <span className="ml-auto px-2 py-1 text-xs bg-emerald-500/20 text-emerald-400 rounded-lg font-mono">
                  ALPACA SOT
                </span>
              </div>

              {/* Positions Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {livePositions.map((pos) => (
                  <div
                    key={pos.symbol}
                    className={`p-4 rounded-lg border ${
                      pos.unrealizedPl >= 0
                        ? 'bg-green-500/10 border-green-500/30'
                        : 'bg-red-500/10 border-red-500/30'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-[hsl(var(--foreground))]">{pos.symbol}</span>
                        <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                          pos.side === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                        }`}>
                          {pos.side.toUpperCase()}
                        </span>
                      </div>
                      <span className={`text-lg font-bold ${
                        pos.unrealizedPl >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {pos.unrealizedPl >= 0 ? '+' : ''}{pos.unrealizedPlPct.toFixed(2)}%
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">Quantity</p>
                        <p className="font-mono text-[hsl(var(--foreground))]">{pos.qty.toLocaleString()}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">Avg Entry</p>
                        <p className="font-mono text-[hsl(var(--foreground))]">${pos.avgEntryPrice.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">Current Price</p>
                        <p className="font-mono text-[hsl(var(--foreground))]">${pos.currentPrice.toFixed(2)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">Market Value</p>
                        <p className="font-mono text-[hsl(var(--foreground))]">${pos.marketValue.toLocaleString()}</p>
                      </div>
                    </div>

                    <div className="mt-3 pt-3 border-t border-[hsl(var(--border))] flex items-center justify-between">
                      <div>
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">Unrealized P/L</p>
                        <p className={`font-mono font-semibold ${
                          pos.unrealizedPl >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {pos.unrealizedPl >= 0 ? '+' : ''}${pos.unrealizedPl.toFixed(2)}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="text-xs text-[hsl(var(--muted-foreground))]">Today</p>
                        <p className={`font-mono ${
                          pos.changeToday >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {pos.changeToday >= 0 ? '+' : ''}{pos.changeToday.toFixed(2)}%
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Total Portfolio Summary */}
              <div className="mt-4 p-3 bg-[hsl(var(--secondary))] rounded-lg">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-[hsl(var(--muted-foreground))]">Total Positions: {livePositions.length}</span>
                  <span className="text-[hsl(var(--muted-foreground))]">
                    Total Value: ${livePositions.reduce((sum, p) => sum + p.marketValue, 0).toLocaleString()}
                  </span>
                  <span className={`font-semibold ${
                    livePositions.reduce((sum, p) => sum + p.unrealizedPl, 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    Total P/L: {livePositions.reduce((sum, p) => sum + p.unrealizedPl, 0) >= 0 ? '+' : ''}
                    ${livePositions.reduce((sum, p) => sum + p.unrealizedPl, 0).toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Paper Trades Section */}
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <DollarSign className="w-5 h-5 text-green-400" />
              <h3 className="font-semibold text-[hsl(var(--foreground))]">Paper Trades</h3>
              <span className="ml-auto px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded-lg">
                G5 Paper Mode
              </span>
            </div>

            {/* Trade Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-xl font-bold text-[hsl(var(--foreground))]">{data.paperTrades?.summary?.totalTrades || 0}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Total</p>
              </div>
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-xl font-bold text-blue-400">{data.paperTrades?.summary?.openTrades || 0}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Open</p>
              </div>
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-xl font-bold text-green-400">{data.paperTrades?.summary?.wins || 0}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Wins</p>
              </div>
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-xl font-bold text-red-400">{data.paperTrades?.summary?.losses || 0}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Losses</p>
              </div>
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className={`text-xl font-bold ${
                  (data.paperTrades?.summary?.winRate || 0) >= 55 ? 'text-green-400' : 'text-yellow-400'
                }`}>
                  {(data.paperTrades?.summary?.winRate || 0).toFixed(0)}%
                </p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Win Rate</p>
              </div>
            </div>

            {/* PnL Summary */}
            {(data.paperTrades?.summary?.totalTrades || 0) > 0 && (
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Total P&L</p>
                  <p className={`text-2xl font-bold ${
                    (data.paperTrades?.summary?.totalPnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    ${(data.paperTrades?.summary?.totalPnl || 0).toLocaleString()}
                  </p>
                </div>
                <div className="p-4 bg-[hsl(var(--secondary))] rounded-lg">
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">Avg P&L %</p>
                  <p className={`text-2xl font-bold ${
                    (data.paperTrades?.summary?.avgPnlPct || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {(data.paperTrades?.summary?.avgPnlPct || 0).toFixed(2)}%
                  </p>
                </div>
              </div>
            )}

            {/* Recent Trades */}
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mb-2">Recent Trades</p>
              {data.paperTrades?.recent?.length > 0 ? (
                <div className="space-y-2">
                  {data.paperTrades.recent.map((trade) => (
                    <div
                      key={trade.tradeId}
                      className="bg-[hsl(var(--secondary))] rounded-lg overflow-hidden"
                    >
                      {/* Clickable Trade Header */}
                      <div
                        onClick={() => setExpandedTradeId(expandedTradeId === trade.tradeId ? null : trade.tradeId)}
                        className="p-3 flex items-center gap-4 cursor-pointer hover:bg-[hsl(var(--secondary))]/80 transition-colors"
                      >
                        <div className={`p-2 rounded ${
                          trade.direction === 'LONG' ? 'bg-green-500/20' : 'bg-red-500/20'
                        }`}>
                          {trade.direction === 'LONG' ? (
                            <TrendingUp className="w-4 h-4 text-green-400" />
                          ) : (
                            <TrendingDown className="w-4 h-4 text-red-400" />
                          )}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-[hsl(var(--foreground))]">
                            {trade.symbol} <span className="text-[hsl(var(--muted-foreground))]">{trade.direction}</span>
                          </p>
                          <p className="text-xs text-[hsl(var(--muted-foreground))]">
                            Entry: ${trade.entryPrice.toLocaleString()} | Regime: {trade.entryRegime}
                          </p>
                        </div>
                        {trade.exitTimestamp ? (
                          <div className="text-right">
                            <p className={`text-sm font-bold ${
                              (trade.pnlPercent || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                            }`}>
                              {(trade.pnlPercent || 0) >= 0 ? '+' : ''}{(trade.pnlPercent || 0).toFixed(2)}%
                            </p>
                            <p className="text-xs text-[hsl(var(--muted-foreground))]">
                              {trade.holdingPeriods} periods | {trade.exitTrigger}
                            </p>
                          </div>
                        ) : (
                          <span className="px-2 py-1 text-xs bg-blue-500/20 text-blue-400 rounded">
                            OPEN
                          </span>
                        )}
                        {expandedTradeId === trade.tradeId ? (
                          <ChevronUp className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
                        )}
                      </div>

                      {/* Expanded Trade Details */}
                      {expandedTradeId === trade.tradeId && (
                        <div className="border-t border-[hsl(var(--border))] p-4 space-y-4">
                          {/* Live P/L for open trades */}
                          {!trade.exitTimestamp && (() => {
                            const livePos = getLivePosition(trade.symbol)
                            if (livePos) {
                              return (
                                <div className={`p-4 rounded-lg border ${
                                  livePos.unrealizedPl >= 0
                                    ? 'bg-green-500/10 border-green-500/30'
                                    : 'bg-red-500/10 border-red-500/30'
                                }`}>
                                  <div className="flex items-center justify-between">
                                    <div>
                                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Live Price</p>
                                      <p className="text-2xl font-bold text-[hsl(var(--foreground))]">
                                        ${livePos.currentPrice.toFixed(2)}
                                      </p>
                                    </div>
                                    <div className="text-right">
                                      <p className="text-xs text-[hsl(var(--muted-foreground))]">Unrealized P&L</p>
                                      <p className={`text-2xl font-bold ${
                                        livePos.unrealizedPl >= 0 ? 'text-green-400' : 'text-red-400'
                                      }`}>
                                        {livePos.unrealizedPl >= 0 ? '+' : ''}${livePos.unrealizedPl.toFixed(2)}
                                      </p>
                                      <p className={`text-sm ${
                                        livePos.unrealizedPlPct >= 0 ? 'text-green-400' : 'text-red-400'
                                      }`}>
                                        ({livePos.unrealizedPlPct >= 0 ? '+' : ''}{livePos.unrealizedPlPct.toFixed(2)}%)
                                      </p>
                                    </div>
                                  </div>
                                  <div className="mt-2 text-xs text-[hsl(var(--muted-foreground))]">
                                    {livePos.qty} shares @ ${livePos.avgEntryPrice.toFixed(2)} avg |
                                    Today: {livePos.changeToday >= 0 ? '+' : ''}{livePos.changeToday.toFixed(2)}%
                                  </div>
                                </div>
                              )
                            }
                            return null
                          })()}

                          {/* Human Summary */}
                          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                            <p className="text-xs font-semibold text-blue-400 mb-1 flex items-center gap-1">
                              <Sparkles className="w-3 h-3" /> Why This Trade?
                            </p>
                            <p className="text-sm text-[hsl(var(--foreground))]">
                              {generateTradeSummary(trade)}
                            </p>
                          </div>

                          {/* Golden Needle Info with Tooltips */}
                          {trade.needleTitle && (
                            <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                              <p className="text-xs font-semibold text-yellow-400 mb-2 flex items-center gap-1">
                                <Target className="w-3 h-3" /> Signal Source
                              </p>
                              <p className="text-sm font-medium text-[hsl(var(--foreground))] mb-2">
                                {trade.needleTitle}
                              </p>
                              <div className="flex flex-wrap gap-2">
                                <Tooltip text="Edge Quality Score (0-1). Higher means stronger historical edge. 1.0 is the maximum.">
                                  <span className="px-2 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded cursor-help">
                                    EQS {(trade.needleEqs || 0).toFixed(2)}
                                  </span>
                                </Tooltip>
                                <Tooltip text="Strategy type. REGIME_EDGE means trading based on market regime transitions (bull/bear/neutral).">
                                  <span className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded cursor-help">
                                    {trade.needleCategory}
                                  </span>
                                </Tooltip>
                                <Tooltip text="Confluence factors count. More factors aligning = higher confidence. 7/7 means all indicators agree.">
                                  <span className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded cursor-help">
                                    {trade.needleConfluence}/7 factors
                                  </span>
                                </Tooltip>
                                <Tooltip text="Signal confidence level based on backtested win rate and risk/reward ratio.">
                                  <span className={`px-2 py-0.5 text-xs rounded cursor-help ${
                                    trade.needleSitcConfidence === 'HIGH' ? 'bg-green-500/20 text-green-400' :
                                    trade.needleSitcConfidence === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                                    'bg-gray-500/20 text-gray-400'
                                  }`}>
                                    {trade.needleSitcConfidence} confidence
                                  </span>
                                </Tooltip>
                              </div>
                            </div>
                          )}

                          {/* Price Levels */}
                          <div className="grid grid-cols-3 gap-3">
                            <div className="p-3 bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg text-center">
                              <p className="text-xs text-[hsl(var(--muted-foreground))] mb-1">Entry Price</p>
                              <p className="text-lg font-bold text-[hsl(var(--foreground))]">
                                ${trade.entryPrice.toLocaleString()}
                              </p>
                            </div>
                            <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg text-center">
                              <p className="text-xs text-green-400 mb-1 flex items-center justify-center gap-1">
                                <Crosshair className="w-3 h-3" /> Target (+{trade.targetPct}%)
                              </p>
                              <p className="text-lg font-bold text-green-400">
                                ${trade.targetPrice.toLocaleString()}
                              </p>
                            </div>
                            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-center">
                              <p className="text-xs text-red-400 mb-1 flex items-center justify-center gap-1">
                                <Shield className="w-3 h-3" /> Stop Loss (-{trade.stopLossPct}%)
                              </p>
                              <p className="text-lg font-bold text-red-400">
                                ${trade.stopLossPrice.toLocaleString()}
                              </p>
                            </div>
                          </div>

                          {/* Trade Details Grid */}
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                            <div className="p-2 bg-[hsl(var(--card))] rounded">
                              <p className="text-xs text-[hsl(var(--muted-foreground))]">Position Size</p>
                              <p className="text-sm font-semibold text-[hsl(var(--foreground))]">
                                ${trade.positionSize.toLocaleString()}
                              </p>
                            </div>
                            <div className="p-2 bg-[hsl(var(--card))] rounded">
                              <p className="text-xs text-[hsl(var(--muted-foreground))]">Entry Time</p>
                              <p className="text-sm font-semibold text-[hsl(var(--foreground))]">
                                {formatTime(trade.entryTimestamp)}
                              </p>
                            </div>
                            <div className="p-2 bg-[hsl(var(--card))] rounded">
                              <p className="text-xs text-[hsl(var(--muted-foreground))]">Expected Hold</p>
                              <p className="text-sm font-semibold text-[hsl(var(--foreground))]">
                                {trade.expectedTimeframeDays || 5} days
                              </p>
                            </div>
                            <div className="p-2 bg-[hsl(var(--card))] rounded">
                              <p className="text-xs text-[hsl(var(--muted-foreground))]">Regime at Entry</p>
                              <p className={`text-sm font-semibold ${
                                trade.entryRegime === 'BULL' ? 'text-green-400' :
                                trade.entryRegime === 'BEAR' ? 'text-red-400' :
                                'text-[hsl(var(--foreground))]'
                              }`}>
                                {trade.entryRegime}
                              </p>
                            </div>
                          </div>

                          {/* Trade ID */}
                          <div className="pt-2 border-t border-[hsl(var(--border))]">
                            <p className="text-xs text-[hsl(var(--muted-foreground))] font-mono">
                              Trade ID: {trade.tradeId} | Needle: {trade.needleId?.slice(0, 8)}...
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center bg-[hsl(var(--secondary))] rounded-lg">
                  <BarChart3 className="w-8 h-8 mx-auto mb-2 text-[hsl(var(--muted-foreground))]" />
                  <p className="text-sm text-[hsl(var(--muted-foreground))]">
                    No paper trades yet
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    Trades will appear when signals are ARMED and CCO permits execution
                  </p>
                </div>
              )}
            </div>

            {/* Strategy Explanation */}
            <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <p className="text-xs font-semibold text-blue-400 mb-2">Trading Strategy</p>
              <div className="text-xs text-[hsl(var(--muted-foreground))] space-y-1">
                <p><strong>Market-Driven:</strong> Signals transition DORMANT → ARMED when CCO context permits (regime alignment, vol within bounds, liquidity ok)</p>
                <p><strong>Time-Driven:</strong> Positions have expected_timeframe_days from Golden Needle hypothesis (usually 3-7 days)</p>
                <p><strong>Exit Triggers:</strong> Signal reversal, stop-loss hit, context revoked, or time expiry</p>
              </div>
            </div>
          </div>

          {/* Golden Needles Section */}
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="w-5 h-5 text-yellow-400" />
              <h3 className="font-semibold text-[hsl(var(--foreground))]">Golden Needles</h3>
              <span className="ml-auto text-sm font-bold text-yellow-400">
                {data.goldenNeedles?.summary?.totalNeedles || 0} total
              </span>
            </div>

            {/* Tier Distribution */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-center">
                <p className="text-2xl font-bold text-yellow-400">{data.goldenNeedles?.summary?.tierCounts?.gold || 0}</p>
                <p className="text-xs text-yellow-400 font-semibold">GOLD</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">EQS &ge; 0.80</p>
              </div>
              <div className="p-3 bg-gray-400/10 border border-gray-400/30 rounded-lg text-center">
                <p className="text-2xl font-bold text-gray-300">{data.goldenNeedles?.summary?.tierCounts?.silver || 0}</p>
                <p className="text-xs text-gray-300 font-semibold">SILVER</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">0.65-0.79</p>
              </div>
              <div className="p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg text-center">
                <p className="text-2xl font-bold text-orange-400">{data.goldenNeedles?.summary?.tierCounts?.bronze || 0}</p>
                <p className="text-xs text-orange-400 font-semibold">BRONZE</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">0.50-0.64</p>
              </div>
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-2xl font-bold text-[hsl(var(--muted-foreground))]">{data.goldenNeedles?.summary?.tierCounts?.below || 0}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))] font-semibold">BELOW</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">&lt; 0.50</p>
              </div>
            </div>

            {/* Summary Stats */}
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-xl font-bold text-green-400">{(data.goldenNeedles?.summary?.avgEqs || 0).toFixed(2)}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Avg EQS</p>
              </div>
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-xl font-bold text-blue-400">{(data.goldenNeedles?.summary?.avgFactors || 0).toFixed(1)}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Avg Factors</p>
              </div>
              <div className="p-3 bg-[hsl(var(--secondary))] rounded-lg text-center">
                <p className="text-xl font-bold text-purple-400">{data.goldenNeedles?.byCategory?.length || 0}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))]">Categories</p>
              </div>
            </div>

            {/* Category Filter */}
            <div className="mb-4">
              <p className="text-xs text-[hsl(var(--muted-foreground))] mb-2">Filter by Category</p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => { setSelectedCategory(null); setNeedlesPage(0); }}
                  className={`px-2 py-1 text-xs rounded-lg transition-colors ${
                    selectedCategory === null
                      ? 'bg-yellow-500/30 text-yellow-400 font-semibold'
                      : 'bg-[hsl(var(--secondary))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--secondary))]/80'
                  }`}
                >
                  All ({data.goldenNeedles?.summary?.totalNeedles || 0})
                </button>
                {data.goldenNeedles?.byCategory?.map((cat) => (
                  <button
                    key={cat.category}
                    onClick={() => { setSelectedCategory(cat.category); setNeedlesPage(0); }}
                    className={`px-2 py-1 text-xs rounded-lg transition-colors ${
                      selectedCategory === cat.category
                        ? 'bg-blue-500/30 text-blue-400 font-semibold'
                        : 'bg-[hsl(var(--secondary))] text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--secondary))]/80'
                    }`}
                  >
                    {cat.category} ({cat.count})
                  </button>
                ))}
              </div>
            </div>

            {/* Needles List with Pagination */}
            <div>
              {(() => {
                const allNeedles = data.goldenNeedles?.recent || []
                const filteredNeedles = selectedCategory
                  ? allNeedles.filter(n => n.category === selectedCategory)
                  : allNeedles
                const totalPages = Math.ceil(filteredNeedles.length / needlesPerPage)
                const paginatedNeedles = filteredNeedles.slice(
                  needlesPage * needlesPerPage,
                  (needlesPage + 1) * needlesPerPage
                )

                return (
                  <>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">
                        Showing {paginatedNeedles.length} of {filteredNeedles.length} needles
                      </p>
                      {totalPages > 1 && (
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setNeedlesPage(p => Math.max(0, p - 1))}
                            disabled={needlesPage === 0}
                            className="px-2 py-1 text-xs bg-[hsl(var(--secondary))] rounded disabled:opacity-50"
                          >
                            ← Prev
                          </button>
                          <span className="text-xs text-[hsl(var(--muted-foreground))]">
                            {needlesPage + 1} / {totalPages}
                          </span>
                          <button
                            onClick={() => setNeedlesPage(p => Math.min(totalPages - 1, p + 1))}
                            disabled={needlesPage >= totalPages - 1}
                            className="px-2 py-1 text-xs bg-[hsl(var(--secondary))] rounded disabled:opacity-50"
                          >
                            Next →
                          </button>
                        </div>
                      )}
                    </div>

                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {paginatedNeedles.map((needle) => (
                        <div
                          key={needle.needleId}
                          className="p-3 bg-[hsl(var(--secondary))] rounded-lg hover:bg-[hsl(var(--secondary))]/80 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                {/* Tier Badge */}
                                <span className={`px-2 py-0.5 text-xs font-bold rounded ${
                                  needle.tier === 'GOLD' ? 'bg-yellow-500/30 text-yellow-400 border border-yellow-500/50' :
                                  needle.tier === 'SILVER' ? 'bg-gray-400/30 text-gray-300 border border-gray-400/50' :
                                  needle.tier === 'BRONZE' ? 'bg-orange-500/30 text-orange-400 border border-orange-500/50' :
                                  'bg-gray-500/20 text-gray-500'
                                }`}>
                                  {needle.tier || 'GOLD'}
                                </span>
                                <p className="text-sm font-medium text-[hsl(var(--foreground))] truncate">
                                  {needle.title}
                                </p>
                              </div>
                              <div className="flex flex-wrap gap-2 mt-1">
                                <Tooltip text={`Edge Quality Score: ${(needle.eqsScore * 100).toFixed(0)}% confidence in historical edge`}>
                                  <span className="px-1.5 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded cursor-help">
                                    EQS {needle.eqsScore.toFixed(2)}
                                  </span>
                                </Tooltip>
                                <Tooltip text={`Strategy type: ${needle.category.replace(/_/g, ' ').toLowerCase()}`}>
                                  <span className="px-1.5 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded cursor-help">
                                    {needle.category}
                                  </span>
                                </Tooltip>
                                <Tooltip text={`${needle.confluenceFactors} out of 7 technical factors align for this signal`}>
                                  <span className="px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded cursor-help">
                                    {needle.confluenceFactors}/7 factors
                                  </span>
                                </Tooltip>
                                <span className={`px-1.5 py-0.5 text-xs rounded ${
                                  needle.sitcConfidence === 'HIGH' ? 'bg-green-500/20 text-green-400' :
                                  needle.sitcConfidence === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                                  'bg-gray-500/20 text-gray-400'
                                }`}>
                                  {needle.sitcConfidence}
                                </span>
                              </div>
                            </div>
                            <div className="text-right shrink-0">
                              <p className="text-xs font-semibold text-[hsl(var(--foreground))]">
                                {needle.priceWitnessSymbol}
                              </p>
                              <p className="text-sm font-mono text-green-400">
                                ${needle.priceWitnessValue.toLocaleString()}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                      {paginatedNeedles.length === 0 && (
                        <p className="text-sm text-[hsl(var(--muted-foreground))] text-center py-4">
                          No golden needles {selectedCategory ? `in ${selectedCategory}` : 'yet'}
                        </p>
                      )}
                    </div>
                  </>
                )
              })()}
            </div>
          </div>

          {/* Recent Transitions */}
          <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-6">
            <div className="flex items-center gap-2 mb-4">
              <ArrowRight className="w-5 h-5 text-[hsl(var(--primary))]" />
              <h3 className="font-semibold text-[hsl(var(--foreground))]">Recent State Transitions</h3>
            </div>
            {data.transitions.length === 0 ? (
              <p className="text-sm text-[hsl(var(--muted-foreground))]">No transitions recorded</p>
            ) : (
              <div className="space-y-2">
                {data.transitions.map((t, idx) => (
                  <div
                    key={idx}
                    className="flex items-center gap-4 p-3 bg-[hsl(var(--secondary))] rounded-lg"
                  >
                    <span className="text-xs font-mono text-[hsl(var(--muted-foreground))]">
                      {formatTime(t.transitioned_at)}
                    </span>
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      t.transition_valid ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {t.transition_valid ? 'VALID' : 'INVALID'}
                    </span>
                    <span className="text-sm text-[hsl(var(--foreground))]">
                      {t.from_state}
                    </span>
                    <ArrowRight className="w-4 h-4 text-[hsl(var(--muted-foreground))]" />
                    <span className="text-sm font-semibold text-[hsl(var(--foreground))]">
                      {t.to_state}
                    </span>
                    <span className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded">
                      {t.transition_trigger}
                    </span>
                    <span className="ml-auto text-xs text-[hsl(var(--muted-foreground))]">
                      CCO: {t.cco_status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="text-center text-xs text-[hsl(var(--muted-foreground))]">
            Last updated: {new Date(data.timestamp).toLocaleString('nb-NO')} | Auto-refresh: 10s
          </div>
        </>
      )}
    </div>
  )
}
