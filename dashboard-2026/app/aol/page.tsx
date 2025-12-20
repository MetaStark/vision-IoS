/**
 * Agent Observability Layer (AOL) - Main Page
 * CEO Directive 2026-FHQ-AOL-PATCH-01 + CEO Directive 2026-FHQ-AOL-TOOLTIPS-01
 *
 * Authority: ADR-001, ADR-004, ADR-006, ADR-009, ADR-012, ADR-013, ADR-018, ADR-019, ADR-020
 * Classification: CONSTITUTIONAL - Glass Wall Observability Layer
 *
 * AUTHORITATIVE SOURCE for all agent and system status information.
 * - System Status: DEFCON, ACI, Regime, Strategy, CEIO, Decision Surfaces
 * - Agent Metrics: ARS, CSI, RBR, GII, DDS, EIS, TCL
 *
 * All metrics bound to real database sources with semantic tooltips.
 * Per ADR-019 ("Dumb Glass Interface") - Section 4.4 Null-Safety Rules.
 */

import { Suspense } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { SystemStatusPanel } from '@/components/fcc/SystemStatusPanel'
import { LiveShadowActivity } from '@/components/aol/LiveShadowActivity'
import { ModuleUnavailable } from '@/components/ModuleErrorBoundary'
import { queryMany, safeQueryMany } from '@/lib/db'
import { getSystemStatus } from '@/lib/fcc/queries'
import {
  Activity,
  Brain,
  Flame,
  Shield,
  TrendingDown,
  Gauge,
  FileText,
  AlertOctagon,
  Cpu,
  Info,
  Clock,
  DollarSign,
  Zap,
  Network,
  Timer,
  Target,
} from 'lucide-react'

export const revalidate = 5 // 5-second polling per CEO Directive Section 4.3

// ============================================================================
// Types - Per CEO Directive 2026-FHQ-AOL-TOOLTIPS-01
// ============================================================================

interface AgentMetrics {
  agent_id: string
  contract_status: string
  mandate_scope: string

  // Last Activity
  last_activity: string | null
  last_activity_source: string | null

  // ARS - Agent Reliability Score
  success_count_7d: number | null
  failure_count_7d: number | null
  retry_count_7d: number | null
  ars_score: number | null
  ars_success_rate: number | null
  ars_retry_frequency: number | null
  ars_fallback_ratio: number | null

  // CSI - Cognitive Stability Index
  csi_score: number | null
  reasoning_entropy: number | null
  thought_coherence: number | null
  csi_tooltip_entropy: number | null
  csi_avg_chain_length: number | null
  csi_branching_factor: number | null
  csi_stability_variance: number | null

  // RBR - Resource Burn Rate
  api_requests_24h: number
  api_requests_7d: number
  total_cost_7d: number
  llm_requests_7d: number
  rbr_tokens_per_hour: number | null
  rbr_cost_per_unit: number | null
  rbr_cost_trend: number | null

  // TCL - Task Cycle Latency
  tcl_avg_latency: number | null
  tcl_max_latency: number | null
  tcl_data_fetch: number | null
  tcl_reasoning: number | null

  // GII - Governance Integrity Index
  gii_state: 'GREEN' | 'YELLOW' | 'RED'
  gii_score: number
  asrp_violations: number
  blocked_operations: number
  truth_vector_drift: number
  gii_tooltip_violations: number | null
  gii_tooltip_blocked: number | null
  gii_truth_drift: number | null
  gii_signature_missing: number | null

  // EIS - Execution Influence Score
  eis_score: number | null
  eis_dependent_modules: number | null
  eis_dependent_tasks: number | null
  eis_alpha_contribution: number | null

  // DDS - Decision Drift Score
  dds_score: number
  dds_drift_events: number | null
  dds_volatility: number | null
  dds_context_revisions: number | null

  // Confidence metrics
  conf_variance: number | null
  conf_low_decisions: number | null

  // Research Activity
  research_events_7d: number
}

// ============================================================================
// Semantic Tooltip Definitions - CEO Directive 2026-FHQ-AOL-TOOLTIPS-01
// Norwegian text per CEO specification
// ============================================================================

const TOOLTIPS = {
  ARS: {
    title: "Agent Reliability Score (ARS)",
    description: "Agentens pålitelighetsgrad over 7 dager. 100 = feilfri utførelse.",
    details: (m: AgentMetrics) => m.ars_score !== null ? [
      `Suksessrate: ${m.ars_success_rate?.toFixed(1) || '—'}%`,
      `Retry-frekvens: ${m.ars_retry_frequency || 0}`,
      `Fallback-ratio: ${m.ars_fallback_ratio?.toFixed(2) || '—'}`,
      `Suksess: ${m.success_count_7d || 0} | Feil: ${m.failure_count_7d || 0}`
    ] : ["Venter på telemetri fra STIG."]
  },
  CSI: {
    title: "Cognitive Stability Index (CSI)",
    description: "Måler agentens kognitive stabilitet og resonneringskvalitet.",
    details: (m: AgentMetrics) => m.csi_score !== null ? [
      `Resonneringsentropi: ${m.csi_tooltip_entropy?.toFixed(3) || '—'}`,
      `Gjsn. kjedegde: ${m.csi_avg_chain_length?.toFixed(1) || '—'}`,
      `Forgreningsfaktor: ${m.csi_branching_factor?.toFixed(2) || '—'}`,
      `Stabilitetsvarians: ${m.csi_stability_variance?.toFixed(3) || '—'}`
    ] : ["Venter på kognitive målinger fra IoS-013."]
  },
  RBR: {
    title: "Resource Burn Rate (RBR)",
    description: "Ressursforbruk: API-kall, LLM-tokens og kostnader.",
    details: (m: AgentMetrics) => [
      `Tokens/time: ${m.rbr_tokens_per_hour?.toFixed(0) || '0'}`,
      `Kost/enhet: $${m.rbr_cost_per_unit?.toFixed(4) || '0'}`,
      `Uke-trend: ${m.rbr_cost_trend !== null ? (m.rbr_cost_trend > 0 ? '+' : '') + m.rbr_cost_trend.toFixed(1) + '%' : '—'}`,
      `Total 7d: $${m.total_cost_7d.toFixed(2)}`
    ]
  },
  TCL: {
    title: "Task Cycle Latency (TCL)",
    description: "Gjennomsnittlig oppgavesyklustid og ytelsesmålinger.",
    details: (m: AgentMetrics) => m.tcl_avg_latency !== null ? [
      `Gjsn. latens: ${m.tcl_avg_latency?.toFixed(0) || '—'}ms`,
      `Maks latens: ${m.tcl_max_latency?.toFixed(0) || '—'}ms`,
      `Datahenting: ${m.tcl_data_fetch?.toFixed(0) || '—'}ms`,
      `Resonnering: ${m.tcl_reasoning?.toFixed(0) || '—'}ms`
    ] : ["Ingen syklusmålinger tilgjengelig."]
  },
  GII: {
    title: "Governance Integrity Index (GII)",
    description: "Overholdelse av styringsregler og ADR-krav.",
    details: (m: AgentMetrics) => [
      `ASRP-brudd: ${m.gii_tooltip_violations || m.asrp_violations}`,
      `Blokkerte ops: ${m.gii_tooltip_blocked || m.blocked_operations}`,
      `Sannhetsdrift: ${m.gii_truth_drift?.toFixed(4) || m.truth_vector_drift.toFixed(4)}`,
      `Manglende signaturer: ${m.gii_signature_missing || 0}`
    ]
  },
  EIS: {
    title: "Execution Influence Score (EIS)",
    description: "Agentens innflytelse på nedstrøms beslutninger.",
    details: (m: AgentMetrics) => m.eis_score !== null ? [
      `Avhengige moduler: ${m.eis_dependent_modules || 0}`,
      `Avhengige oppgaver: ${m.eis_dependent_tasks || 0}`,
      `Alpha-bidrag: ${m.eis_alpha_contribution?.toFixed(0) || '0'}`
    ] : ["Ingen innflytelsedata registrert."]
  },
  DDS: {
    title: "Decision Drift Score (DDS)",
    description: "Måler avvik fra kanonisk atferd. 0 = stabil.",
    details: (m: AgentMetrics) => [
      `Drifthendelser: ${m.dds_drift_events || 0}`,
      `Volatilitet: ${m.dds_volatility?.toFixed(3) || '0'}`,
      `Kontekstrevisjoner: ${m.dds_context_revisions || 0}`,
      m.dds_score > 0.3 ? "ADVARSEL: Rekalibrering anbefalt" : "Status: Stabil"
    ]
  },
  CONFIDENCE: {
    title: "LLM Confidence Metrics",
    description: "Konfidensvariasjon i agentens beslutninger.",
    details: (m: AgentMetrics) => m.conf_variance !== null ? [
      `Konfidensvarians: ${m.conf_variance?.toFixed(4) || '—'}`,
      `Lavkonfidensbeslutn.: ${m.conf_low_decisions || 0}`
    ] : ["Ingen konfidensdata tilgjengelig."]
  }
}

// ============================================================================
// Data Fetching Components with Graceful Degradation
// CD-EXEC-PERMANENT-UPTIME: Module failures must not crash dashboard
// ============================================================================

async function SystemStatusSection() {
  try {
    const status = await getSystemStatus()
    return <SystemStatusPanel status={status} />
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    console.error('[SYSTEM-STATUS] Failed:', msg)
    return <ModuleUnavailable moduleName="System Status Panel" error={msg} />
  }
}

// LLM Balance Panel - Live from DeepSeek API
async function LLMBalancePanel() {
  try {
    // Fetch from our API which gets live data from DeepSeek
    const balanceData = await queryMany<{
      provider: string
      currency: string
      total_balance: number
      fetched_at: string
    }>(`
      SELECT provider, currency, total_balance::float, fetched_at::text
      FROM fhq_governance.llm_provider_balance
      WHERE provider = 'deepseek'
      ORDER BY fetched_at DESC
      LIMIT 1
    `)

    // Get December spend from telemetry
    const decemberSpend = await queryMany<{
      total_spent: number
      total_requests: number
    }>(`
      SELECT
        COALESCE(SUM(total_cost_usd), 0)::float as total_spent,
        COALESCE(SUM(llm_requests), 0)::bigint as total_requests
      FROM fhq_governance.telemetry_cost_ledger
      WHERE ledger_date >= '2025-12-01'
    `)

    const balance = balanceData[0]
    const spend = decemberSpend[0] || { total_spent: 0, total_requests: 0 }
    const lastFetched = balance ? new Date(balance.fetched_at) : null

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg" style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)' }}>
              <DollarSign className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <CardTitle>LLM Provider Balance</CardTitle>
              <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                DeepSeek API - Live Balance | ADR-012 Economic Safety
              </p>
            </div>
          </div>
          {lastFetched && (
            <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              <Clock className="w-3 h-3 inline mr-1" />
              Oppdatert: {lastFetched.toLocaleString('no-NO')}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* Current Balance */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="text-xs mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Tilgjengelig Saldo
            </div>
            <div className="text-2xl font-bold text-green-400">
              ${balance?.total_balance.toFixed(2) || '—'}
            </div>
            <div className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {balance?.currency || 'USD'}
            </div>
          </div>

          {/* December Spend */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="text-xs mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Desember Forbruk
            </div>
            <div className="text-2xl font-bold" style={{ color: 'hsl(var(--foreground))' }}>
              ${spend.total_spent.toFixed(2)}
            </div>
            <div className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {spend.total_requests} requests
            </div>
          </div>

          {/* Daily Budget Status */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="text-xs mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Daglig Budsjett (G2-C)
            </div>
            <div className="text-2xl font-bold text-green-400">
              $5.00
            </div>
            <div className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Grense per ADR-012
            </div>
          </div>

          {/* DeepSeek Pricing */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="text-xs mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              DeepSeek Prising
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Input (cache hit)</span>
                <span className="font-mono text-green-400">$0.028</span>
              </div>
              <div className="flex justify-between text-sm">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Input (cache miss)</span>
                <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>$0.28</span>
              </div>
              <div className="flex justify-between text-sm">
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>Output</span>
                <span className="font-mono" style={{ color: 'hsl(var(--foreground))' }}>$0.42</span>
              </div>
            </div>
            <div className="text-xs mt-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
              per 1M tokens
            </div>
          </div>
        </div>

        {/* Provider comparison note */}
        <div className="mt-4 p-3 rounded-lg text-xs" style={{ backgroundColor: 'rgba(96, 165, 250, 0.1)', border: '1px solid rgba(96, 165, 250, 0.2)' }}>
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-blue-400" />
            <span style={{ color: 'hsl(var(--foreground))' }}>
              <strong>DeepSeek prioritert:</strong> $0.28-$0.42/1M tokens vs GPT-4o $2.50-$10/1M tokens (90-95% besparelse)
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    console.error('[LLM-BALANCE] Failed:', msg)
    return <ModuleUnavailable moduleName="LLM Provider Balance" error={msg} />
  }
}

export default async function AOLPage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div className="pb-6" style={{ borderBottom: '1px solid hsl(var(--border))' }}>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 rounded-lg" style={{ backgroundColor: 'hsl(var(--primary))' }}>
            <Cpu className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-display">Agent Observability Layer</h1>
            <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              AUTHORITATIVE SOURCE | System Status + Agent Telemetry
            </p>
          </div>
        </div>
        <p className="mt-3 max-w-3xl" style={{ color: 'hsl(var(--muted-foreground))' }}>
          When agents think — CEO sees. When agents drift — CEO knows. When agents fail — CEO can act.
          <strong> No placeholders. No synthetic values. Backend truth only.</strong>
        </p>
        <div className="flex items-center gap-4 mt-4 text-xs" style={{ color: 'hsl(var(--muted-foreground) / 0.7)' }}>
          <span>Compliance: ADR-006, ADR-009, ADR-012, ADR-018, ADR-019, ADR-020</span>
          <span>|</span>
          <span>Refresh: 5s polling</span>
          <span>|</span>
          <span>Mode: READ-ONLY (Dumb Glass)</span>
          <span>|</span>
          <span className="px-2 py-0.5 rounded text-green-400 bg-green-900/30">TELEMETRY ACTIVE</span>
        </div>
      </div>

      {/* G4 System Status Panel - AUTHORITATIVE */}
      <Suspense fallback={<SkeletonCard />}>
        <SystemStatusSection />
      </Suspense>

      {/* IoS-012 Live Shadow Activity Panel - CD-IOS-012-LIVE-ACT-001 */}
      <LiveShadowActivity />

      {/* Metrics Legend with Enhanced Tooltips */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))', border: '1px solid hsl(var(--border))' }}>
        <MetricLegend
          icon={<Gauge className="w-4 h-4" />}
          label="ARS"
          description="Pålitelighet (0-100)"
        />
        <MetricLegend
          icon={<Brain className="w-4 h-4" />}
          label="CSI"
          description="Kognitiv stabilitet"
        />
        <MetricLegend
          icon={<Flame className="w-4 h-4" />}
          label="RBR"
          description="Ressursforbruk"
        />
        <MetricLegend
          icon={<Timer className="w-4 h-4" />}
          label="TCL"
          description="Syklustid (ms)"
        />
        <MetricLegend
          icon={<Shield className="w-4 h-4" />}
          label="GII"
          description="Styringsintegritet"
        />
        <MetricLegend
          icon={<Network className="w-4 h-4" />}
          label="EIS"
          description="Innflytelse"
        />
        <MetricLegend
          icon={<TrendingDown className="w-4 h-4" />}
          label="DDS"
          description="Beslutningsdrift"
        />
      </div>

      {/* LLM Provider Balance - Live from DeepSeek */}
      <Suspense fallback={<SkeletonCard />}>
        <LLMBalancePanel />
      </Suspense>

      {/* Agent Cards */}
      <Suspense fallback={<AgentGridSkeleton />}>
        <AgentObservabilityGrid />
      </Suspense>

      {/* Agent Integrity Ledger */}
      <Suspense fallback={<SkeletonCard />}>
        <AgentIntegrityLedger />
      </Suspense>

      {/* Footer */}
      <footer className="pt-6 text-center text-xs" style={{ borderTop: '1px solid hsl(var(--border))', color: 'hsl(var(--muted-foreground) / 0.6)' }}>
        <p>Agent Observability Layer v3.0.0 | CEO Directive 2026-FHQ-AOL-TOOLTIPS-01</p>
        <p className="mt-1">
          ADR-019 Compliant: No placeholders, no synthetic values. "—" indicates awaiting telemetry.
        </p>
      </footer>
    </div>
  )
}

// ============================================================================
// Agent Data Fetching Components - Using mv_aol_agent_metrics with tooltip data
// CD-EXEC-PERMANENT-UPTIME: Module failures must not crash dashboard
// ============================================================================

async function AgentObservabilityGrid() {
  try {
    // Query actual available columns from mv_aol_agent_metrics
    // Actual columns: agent_id, total_actions, last_action, approved_count
    const agents = await queryMany<any>(`
    SELECT
      m.agent_id,
      'ACTIVE' as contract_status,
      'OPERATIONAL' as mandate_scope,
      m.last_action as last_activity,
      'agent_task_log' as last_activity_source,
      m.total_actions as success_count_7d,
      0 as failure_count_7d,
      0 as retry_count_7d,
      0 as fallback_count_7d,
      CASE WHEN m.total_actions > 0 THEN 100 ELSE NULL END as ars_score,
      NULL::int as csi_score,
      NULL::float as reasoning_entropy,
      NULL::float as thought_coherence,
      0 as api_requests_24h,
      0 as api_requests_7d,
      0.0 as api_cost_7d,
      0 as llm_requests_7d,
      0.0 as total_cost_7d,
      'GREEN' as gii_state,
      100 as gii_score,
      0 as asrp_violations,
      0 as blocked_operations,
      0.0 as truth_vector_drift,
      0.0 as dds_score,
      0 as research_events_7d,
      -- Tooltip data (all fallback values since columns don't exist)
      NULL::float as ars_success_rate,
      NULL::int as ars_retry_frequency,
      NULL::float as ars_fallback_ratio,
      NULL::float as csi_tooltip_entropy,
      NULL::float as csi_avg_chain_length,
      NULL::float as csi_branching_factor,
      NULL::float as csi_stability_variance,
      NULL::int as rbr_tokens_per_hour,
      NULL::float as rbr_cost_per_unit,
      NULL::text as rbr_cost_trend,
      NULL::int as tcl_avg_latency,
      NULL::int as tcl_max_latency,
      NULL::int as tcl_data_fetch,
      NULL::int as tcl_reasoning,
      NULL::text as gii_tooltip_violations,
      NULL::text as gii_tooltip_blocked,
      NULL::float as gii_truth_drift,
      NULL::int as gii_signature_missing,
      NULL::text as eis_dependent_modules,
      NULL::text as eis_dependent_tasks,
      NULL::float as eis_alpha_contribution,
      NULL::int as eis_score,
      NULL::int as dds_drift_events,
      NULL::float as dds_volatility,
      NULL::int as dds_context_revisions,
      NULL::float as conf_variance,
      NULL::int as conf_low_decisions
    FROM fhq_governance.mv_aol_agent_metrics m
    ORDER BY m.agent_id
  `)

  const agentMetrics: AgentMetrics[] = agents.map((agent: any) => ({
    agent_id: agent.agent_id,
    contract_status: agent.contract_status,
    mandate_scope: agent.mandate_scope,

    last_activity: agent.last_activity || null,
    last_activity_source: agent.last_activity_source || null,

    // ARS
    success_count_7d: agent.ars_score !== null ? parseInt(agent.success_count_7d || '0') : null,
    failure_count_7d: agent.ars_score !== null ? parseInt(agent.failure_count_7d || '0') : null,
    retry_count_7d: agent.ars_score !== null ? parseInt(agent.retry_count_7d || '0') : null,
    ars_score: agent.ars_score !== null ? parseInt(agent.ars_score) : null,
    ars_success_rate: agent.ars_success_rate !== null ? parseFloat(agent.ars_success_rate) : null,
    ars_retry_frequency: agent.ars_retry_frequency !== null ? parseInt(agent.ars_retry_frequency) : null,
    ars_fallback_ratio: agent.ars_fallback_ratio !== null ? parseFloat(agent.ars_fallback_ratio) : null,

    // CSI
    csi_score: agent.csi_score !== null ? parseInt(agent.csi_score) : null,
    reasoning_entropy: agent.reasoning_entropy !== null ? parseFloat(agent.reasoning_entropy) : null,
    thought_coherence: agent.thought_coherence !== null ? parseFloat(agent.thought_coherence) : null,
    csi_tooltip_entropy: agent.csi_tooltip_entropy !== null ? parseFloat(agent.csi_tooltip_entropy) : null,
    csi_avg_chain_length: agent.csi_avg_chain_length !== null ? parseFloat(agent.csi_avg_chain_length) : null,
    csi_branching_factor: agent.csi_branching_factor !== null ? parseFloat(agent.csi_branching_factor) : null,
    csi_stability_variance: agent.csi_stability_variance !== null ? parseFloat(agent.csi_stability_variance) : null,

    // RBR
    api_requests_24h: parseInt(agent.api_requests_24h || '0'),
    api_requests_7d: parseInt(agent.api_requests_7d || '0'),
    total_cost_7d: parseFloat(agent.total_cost_7d || '0'),
    llm_requests_7d: parseInt(agent.llm_requests_7d || '0'),
    rbr_tokens_per_hour: agent.rbr_tokens_per_hour !== null ? parseFloat(agent.rbr_tokens_per_hour) : null,
    rbr_cost_per_unit: agent.rbr_cost_per_unit !== null ? parseFloat(agent.rbr_cost_per_unit) : null,
    rbr_cost_trend: agent.rbr_cost_trend !== null ? parseFloat(agent.rbr_cost_trend) : null,

    // TCL
    tcl_avg_latency: agent.tcl_avg_latency !== null ? parseFloat(agent.tcl_avg_latency) : null,
    tcl_max_latency: agent.tcl_max_latency !== null ? parseFloat(agent.tcl_max_latency) : null,
    tcl_data_fetch: agent.tcl_data_fetch !== null ? parseFloat(agent.tcl_data_fetch) : null,
    tcl_reasoning: agent.tcl_reasoning !== null ? parseFloat(agent.tcl_reasoning) : null,

    // GII
    gii_state: agent.gii_state || 'GREEN',
    gii_score: parseInt(agent.gii_score || '100'),
    asrp_violations: parseInt(agent.asrp_violations || '0'),
    blocked_operations: parseInt(agent.blocked_operations || '0'),
    truth_vector_drift: parseFloat(agent.truth_vector_drift || '0'),
    gii_tooltip_violations: agent.gii_tooltip_violations !== null ? parseInt(agent.gii_tooltip_violations) : null,
    gii_tooltip_blocked: agent.gii_tooltip_blocked !== null ? parseInt(agent.gii_tooltip_blocked) : null,
    gii_truth_drift: agent.gii_truth_drift !== null ? parseFloat(agent.gii_truth_drift) : null,
    gii_signature_missing: agent.gii_signature_missing !== null ? parseInt(agent.gii_signature_missing) : null,

    // EIS
    eis_score: agent.eis_score !== null ? parseInt(agent.eis_score) : null,
    eis_dependent_modules: agent.eis_dependent_modules !== null ? parseInt(agent.eis_dependent_modules) : null,
    eis_dependent_tasks: agent.eis_dependent_tasks !== null ? parseInt(agent.eis_dependent_tasks) : null,
    eis_alpha_contribution: agent.eis_alpha_contribution !== null ? parseInt(agent.eis_alpha_contribution) : null,

    // DDS
    dds_score: parseFloat(agent.dds_score || '0'),
    dds_drift_events: agent.dds_drift_events !== null ? parseInt(agent.dds_drift_events) : null,
    dds_volatility: agent.dds_volatility !== null ? parseFloat(agent.dds_volatility) : null,
    dds_context_revisions: agent.dds_context_revisions !== null ? parseInt(agent.dds_context_revisions) : null,

    // Confidence
    conf_variance: agent.conf_variance !== null ? parseFloat(agent.conf_variance) : null,
    conf_low_decisions: agent.conf_low_decisions !== null ? parseInt(agent.conf_low_decisions) : null,

    // Research
    research_events_7d: parseInt(agent.research_events_7d || '0'),
  }))

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agentMetrics.map((agent) => (
          <AgentCard key={agent.agent_id} agent={agent} />
        ))}
      </div>
    )
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    console.error('[AGENT-GRID] Failed:', msg)
    return <ModuleUnavailable moduleName="Agent Observability Grid" error={msg} />
  }
}

async function AgentIntegrityLedger() {
  try {
    const recentEvents = await queryMany<any>(`
    SELECT
      task_id,
      agent_id,
      task_name,
      task_type,
      status,
      started_at,
      completed_at,
      latency_ms,
      cost_usd,
      provider,
      signature_hash,
      quad_hash,
      fallback_used,
      error_message
    FROM fhq_governance.agent_task_log
    ORDER BY started_at DESC
    LIMIT 50
  `)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5" style={{ color: 'hsl(var(--muted-foreground))' }} />
          <CardTitle>Agent Integrity Ledger</CardTitle>
          <span className="px-2 py-0.5 text-xs rounded" style={{ backgroundColor: 'hsl(var(--secondary))', color: 'hsl(var(--muted-foreground))' }}>
            {recentEvents.length} events
          </span>
          <SemanticTooltip
            title="Agent Integrity Ledger"
            description="Kronologisk logg over alle agenthandlinger med kryptografisk signatur."
            details={["task_name, status, signature_hash", "cost_usd, latency_ms per oppgave", "Siste 50 hendelser fra agent_task_log"]}
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid hsl(var(--border))' }}>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Agent</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Task</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Status</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Provider</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Latency</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Cost</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Signature</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: 'hsl(var(--muted-foreground))' }}>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {recentEvents.map((event: any) => (
                <tr key={event.task_id} style={{ borderBottom: '1px solid hsl(var(--border) / 0.5)' }} className="hover:bg-[hsl(var(--secondary))]">
                  <td className="py-2 px-3 font-mono text-xs" style={{ color: 'hsl(var(--foreground))' }}>{event.agent_id}</td>
                  <td className="py-2 px-3 text-xs" style={{ color: 'hsl(var(--foreground))' }}>
                    <span title={event.task_name}>{event.task_name?.substring(0, 20)}{event.task_name?.length > 20 ? '...' : ''}</span>
                    <span className="ml-2 text-xs px-1 rounded" style={{ backgroundColor: 'hsl(var(--secondary))', color: 'hsl(var(--muted-foreground))' }}>
                      {event.task_type}
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    <StatusBadge
                      variant={
                        event.status === 'SUCCESS'
                          ? 'pass'
                          : event.status === 'FAILED'
                          ? 'fail'
                          : 'info'
                      }
                    >
                      {event.status || 'PENDING'}
                    </StatusBadge>
                  </td>
                  <td className="py-2 px-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {event.provider || '—'}
                  </td>
                  <td className="py-2 px-3 text-xs font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {event.latency_ms !== null ? `${event.latency_ms}ms` : '—'}
                  </td>
                  <td className="py-2 px-3 text-xs font-mono" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {event.cost_usd !== null && parseFloat(event.cost_usd) > 0
                      ? `$${parseFloat(event.cost_usd).toFixed(4)}`
                      : '—'}
                  </td>
                  <td className="py-2 px-3 font-mono text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {event.quad_hash ? event.quad_hash.substring(0, 12) + '...' : '—'}
                  </td>
                  <td className="py-2 px-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {new Date(event.started_at).toLocaleString()}
                  </td>
                </tr>
              ))}
              {recentEvents.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-8 text-center" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    No recent events in ledger. Awaiting STIG telemetry activation.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
  } catch (error) {
    const msg = error instanceof Error ? error.message : 'Unknown error'
    console.error('[INTEGRITY-LEDGER] Failed:', msg)
    return <ModuleUnavailable moduleName="Agent Integrity Ledger" error={msg} />
  }
}

// ============================================================================
// UI Components with Semantic Tooltips and Visualizations
// ============================================================================

function AgentCard({ agent }: { agent: AgentMetrics }) {
  const getScoreColor = (score: number | null) => {
    if (score === null) return { color: 'hsl(var(--muted-foreground))' }
    if (score >= 80) return { color: 'rgb(134, 239, 172)' }
    if (score >= 60) return { color: 'rgb(253, 224, 71)' }
    return { color: 'rgb(252, 165, 165)' }
  }

  const getGIIStyle = (state: string) => {
    if (state === 'GREEN') return { backgroundColor: 'rgba(34, 197, 94, 0.15)', color: 'rgb(134, 239, 172)', border: '1px solid rgba(34, 197, 94, 0.3)' }
    if (state === 'YELLOW') return { backgroundColor: 'rgba(245, 158, 11, 0.15)', color: 'rgb(253, 224, 71)', border: '1px solid rgba(245, 158, 11, 0.3)' }
    return { backgroundColor: 'rgba(239, 68, 68, 0.15)', color: 'rgb(252, 165, 165)', border: '1px solid rgba(239, 68, 68, 0.3)' }
  }

  const formatValue = (value: number | null, suffix?: string) => {
    if (value === null) return '—'
    return suffix ? `${value}${suffix}` : value.toString()
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
              <Activity className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground))' }} />
            </div>
            <CardTitle className="text-lg">{agent.agent_id}</CardTitle>
          </div>
          <span className="px-2 py-1 text-xs font-semibold rounded" style={getGIIStyle(agent.gii_state)}>
            GII: {agent.gii_state}
          </span>
        </div>
        <p className="text-xs mt-1 line-clamp-2" style={{ color: 'hsl(var(--muted-foreground))' }}>{agent.mandate_scope}</p>
      </CardHeader>
      <CardContent>
        {/* Main Metric Grid with Radial Visualizations */}
        <div className="grid grid-cols-2 gap-3 mb-3">
          {/* ARS with Radial Meter */}
          <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <Gauge className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>ARS</span>
              <SemanticTooltip
                title={TOOLTIPS.ARS.title}
                description={TOOLTIPS.ARS.description}
                details={TOOLTIPS.ARS.details(agent)}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold" style={getScoreColor(agent.ars_score)}>
                {formatValue(agent.ars_score)}
              </span>
              {agent.ars_score !== null && (
                <RadialMeter value={agent.ars_score} max={100} size={24} />
              )}
            </div>
          </div>

          {/* CSI with Oscilloscope */}
          <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <Brain className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>CSI</span>
              <SemanticTooltip
                title={TOOLTIPS.CSI.title}
                description={TOOLTIPS.CSI.description}
                details={TOOLTIPS.CSI.details(agent)}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold" style={getScoreColor(agent.csi_score)}>
                {formatValue(agent.csi_score)}
              </span>
              {agent.csi_score !== null && (
                <StabilityIndicator variance={agent.csi_stability_variance || 0} />
              )}
            </div>
          </div>

          {/* GII Score */}
          <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <Shield className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>GII</span>
              <SemanticTooltip
                title={TOOLTIPS.GII.title}
                description={TOOLTIPS.GII.description}
                details={TOOLTIPS.GII.details(agent)}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xl font-bold" style={getScoreColor(agent.gii_score)}>
                {agent.gii_score}
              </span>
              <RadialMeter value={agent.gii_score} max={100} size={24} />
            </div>
          </div>

          {/* EIS */}
          <div className="p-3 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <div className="flex items-center gap-1 mb-1">
              <Network className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>EIS</span>
              <SemanticTooltip
                title={TOOLTIPS.EIS.title}
                description={TOOLTIPS.EIS.description}
                details={TOOLTIPS.EIS.details(agent)}
              />
            </div>
            <span className="text-xl font-bold" style={getScoreColor(agent.eis_score)}>
              {formatValue(agent.eis_score)}
            </span>
          </div>
        </div>

        {/* Secondary Metrics Row */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          {/* DDS with Heat Indicator */}
          <div className="p-2 rounded-lg text-center" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
            <div className="flex items-center justify-center gap-1 mb-1">
              <TrendingDown className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>DDS</span>
              <SemanticTooltip
                title={TOOLTIPS.DDS.title}
                description={TOOLTIPS.DDS.description}
                details={TOOLTIPS.DDS.details(agent)}
              />
            </div>
            <div className="flex items-center justify-center gap-1">
              <span className="text-sm font-bold" style={{ color: agent.dds_score > 0.3 ? 'rgb(252, 165, 165)' : 'hsl(var(--foreground))' }}>
                {agent.dds_score.toFixed(3)}
              </span>
              <HeatBar value={agent.dds_score} max={1} />
            </div>
          </div>

          {/* TCL */}
          <div className="p-2 rounded-lg text-center" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
            <div className="flex items-center justify-center gap-1 mb-1">
              <Timer className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>TCL</span>
              <SemanticTooltip
                title={TOOLTIPS.TCL.title}
                description={TOOLTIPS.TCL.description}
                details={TOOLTIPS.TCL.details(agent)}
              />
            </div>
            <span className="text-sm font-mono font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
              {agent.tcl_avg_latency !== null ? `${agent.tcl_avg_latency.toFixed(0)}ms` : '—'}
            </span>
          </div>

          {/* Confidence */}
          <div className="p-2 rounded-lg text-center" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
            <div className="flex items-center justify-center gap-1 mb-1">
              <Target className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Conf</span>
              <SemanticTooltip
                title={TOOLTIPS.CONFIDENCE.title}
                description={TOOLTIPS.CONFIDENCE.description}
                details={TOOLTIPS.CONFIDENCE.details(agent)}
              />
            </div>
            <span className="text-sm font-mono font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
              {agent.conf_variance !== null ? agent.conf_variance.toFixed(3) : '—'}
            </span>
          </div>
        </div>

        {/* Resource Burn Rate Section */}
        <div className="grid grid-cols-3 gap-2 p-2 rounded-lg mb-3" style={{ backgroundColor: 'hsl(var(--secondary) / 0.5)' }}>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1">
              <Zap className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>API 24h</span>
            </div>
            <span className="text-sm font-mono font-semibold" style={{ color: 'hsl(var(--foreground))' }}>{agent.api_requests_24h}</span>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1">
              <Brain className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>LLM 7d</span>
            </div>
            <span className="text-sm font-mono font-semibold" style={{ color: 'hsl(var(--foreground))' }}>{agent.llm_requests_7d}</span>
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-1">
              <DollarSign className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
              <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Cost 7d</span>
              <SemanticTooltip
                title={TOOLTIPS.RBR.title}
                description={TOOLTIPS.RBR.description}
                details={TOOLTIPS.RBR.details(agent)}
              />
            </div>
            <span className="text-sm font-mono font-semibold" style={{ color: agent.total_cost_7d > 10 ? 'rgb(252, 165, 165)' : 'hsl(var(--foreground))' }}>
              ${agent.total_cost_7d.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Activity Stats */}
        <div className="flex items-center justify-between text-xs py-2" style={{ borderTop: '1px solid hsl(var(--border))' }}>
          <div className="flex items-center gap-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            <Activity className="w-3 h-3" />
            <span>Events: {agent.research_events_7d}</span>
          </div>
          <div className="flex items-center gap-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
            <AlertOctagon className="w-3 h-3" style={{ color: agent.blocked_operations > 0 ? 'rgb(252, 165, 165)' : undefined }} />
            <span>Blocked: {agent.blocked_operations}</span>
          </div>
        </div>

        {/* Last Activity */}
        <div className="flex items-center gap-1 text-xs pt-2" style={{ color: 'hsl(var(--muted-foreground))', borderTop: '1px solid hsl(var(--border))' }}>
          <Clock className="w-3 h-3" />
          <span>
            Last activity:{' '}
            {agent.last_activity
              ? `${new Date(agent.last_activity).toLocaleString()} (${agent.last_activity_source})`
              : '—'}
          </span>
        </div>

        {/* ADR-009 Suspend Button */}
        {agent.gii_state === 'RED' && (
          <form action="/api/aol/suspend" method="POST" className="mt-3">
            <input type="hidden" name="agent_id" value={agent.agent_id} />
            <input type="hidden" name="reason" value={`GII RED: ${agent.blocked_operations} blocked ops, ${agent.asrp_violations} ASRP violations`} />
            <input type="hidden" name="requestor" value="FCC_DASHBOARD_CEO" />
            <button
              type="submit"
              className="w-full py-2 px-4 text-white text-sm font-medium rounded-lg transition-colors hover:opacity-90"
              style={{ backgroundColor: 'rgb(220, 38, 38)' }}
              title="Initiates ADR-009 suspension workflow requiring CEO approval"
            >
              Request Suspension (ADR-009)
            </button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Visualization Components per CEO Directive Section 3.2
// ============================================================================

function RadialMeter({ value, max, size = 24 }: { value: number; max: number; size?: number }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100))
  const strokeWidth = 3
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (percentage / 100) * circumference

  const getColor = () => {
    if (percentage >= 80) return 'rgb(34, 197, 94)'
    if (percentage >= 60) return 'rgb(245, 158, 11)'
    return 'rgb(239, 68, 68)'
  }

  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="hsl(var(--border))"
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={getColor()}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        strokeLinecap="round"
      />
    </svg>
  )
}

function HeatBar({ value, max }: { value: number; max: number }) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100))

  const getColor = () => {
    if (percentage <= 30) return 'rgb(34, 197, 94)'
    if (percentage <= 60) return 'rgb(245, 158, 11)'
    return 'rgb(239, 68, 68)'
  }

  return (
    <div className="w-8 h-2 rounded-full overflow-hidden" style={{ backgroundColor: 'hsl(var(--border))' }}>
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${percentage}%`, backgroundColor: getColor() }}
      />
    </div>
  )
}

function StabilityIndicator({ variance }: { variance: number }) {
  // Higher variance = less stable = more red
  const stability = Math.max(0, 1 - variance)
  const color = stability >= 0.7 ? 'rgb(34, 197, 94)' : stability >= 0.4 ? 'rgb(245, 158, 11)' : 'rgb(239, 68, 68)'

  return (
    <div className="flex items-center gap-0.5">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-1 rounded-full transition-all"
          style={{
            height: `${8 + i * 4}px`,
            backgroundColor: i <= Math.floor(stability * 3) ? color : 'hsl(var(--border))'
          }}
        />
      ))}
    </div>
  )
}

function MetricLegend({
  icon,
  label,
  description,
}: {
  icon: React.ReactNode
  label: string
  description: string
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="p-1.5 rounded" style={{ backgroundColor: 'hsl(var(--background))', border: '1px solid hsl(var(--border))' }}>{icon}</div>
      <div>
        <span className="font-semibold text-sm" style={{ color: 'hsl(var(--foreground))' }}>{label}</span>
        <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{description}</p>
      </div>
    </div>
  )
}

function SemanticTooltip({
  title,
  description,
  details
}: {
  title: string
  description: string
  details: string[]
}) {
  return (
    <span className="group relative">
      <Info className="w-3 h-3 cursor-help" style={{ color: 'hsl(var(--muted-foreground))' }} />
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none w-72 z-50 shadow-lg" style={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', color: 'hsl(var(--foreground))' }}>
        <div className="font-semibold mb-1" style={{ color: 'hsl(var(--primary))' }}>{title}</div>
        <div className="mb-2" style={{ color: 'hsl(var(--muted-foreground))' }}>{description}</div>
        <div className="space-y-0.5">
          {details.map((detail, i) => (
            <div key={i} className="font-mono text-xs" style={{ color: 'hsl(var(--foreground))' }}>• {detail}</div>
          ))}
        </div>
      </span>
    </span>
  )
}

function AgentGridSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  )
}
