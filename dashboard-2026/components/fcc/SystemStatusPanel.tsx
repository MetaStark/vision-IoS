/**
 * FCC System Status Panel
 * AUTHORITATIVE System State Display - G4 Activation States
 *
 * Authority: CEO Directive 2026
 * Compliance: ADR-016, ADR-018, ADR-020
 *
 * This is the SINGLE SOURCE OF TRUTH for system status.
 * Displays: DEFCON, ACI, Regime Engine, Strategy, CEIO, Decision Surfaces
 */

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import {
  Shield,
  Brain,
  Eye,
  Zap,
  Database,
  Target,
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface DEFCONState {
  defcon_level: string
  triggered_at: string
  triggered_by: string
  trigger_reason: string
}

interface ACIState {
  execution_state: string
  dynamic_reasoning_loop: boolean
  sitc_enabled: boolean
  inforage_enabled: boolean
  ikea_enabled: boolean
  bound_state_hash: string
  activated_at: string
}

interface RegimeEngineState {
  perception_mode: string
  refresh_interval: string
  causal_modifiers_bound: boolean
  alpha_graph_version: string
  activated_at: string
}

interface StrategyState {
  strategy_state: string
  lars_evaluation_enabled: boolean
  dsl_optimization_bound: boolean
  quad_hash_binding: string
  regime_aware_allocation: boolean
  activated_at: string
}

interface CEIOState {
  fetch_enabled: boolean
  clean_enabled: boolean
  stage_enabled: boolean
  lake_tier_enabled: boolean
  pulse_tier_enabled: boolean
  sniper_tier_enabled: boolean
  aci_binding: boolean
  activated_at: string
}

interface DecisionSurfaceState {
  decision_ledger_enabled: boolean
  paper_execution_mode: boolean
  calibration_sequences: number
  trading_surfaces_frozen: boolean
  execution_authority: string
  activated_at: string
}

export interface SystemStatus {
  defcon: DEFCONState | null
  aci: ACIState | null
  regime: RegimeEngineState | null
  strategy: StrategyState | null
  ceio: CEIOState | null
  decision: DecisionSurfaceState | null
}

interface SystemStatusPanelProps {
  status: SystemStatus
}

export function SystemStatusPanel({ status }: SystemStatusPanelProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg" style={{ backgroundColor: 'hsl(var(--primary))' }}>
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <CardTitle>System Status (G4 Activation State)</CardTitle>
              <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                THE SOVEREIGN AUTONOMY RELEASE | Migration 126
              </p>
            </div>
          </div>
          <span
            className="px-3 py-1 text-xs font-semibold rounded-full"
            style={{
              backgroundColor: status.defcon?.defcon_level === 'GREEN'
                ? 'rgba(34, 197, 94, 0.2)'
                : 'rgba(245, 158, 11, 0.2)',
              color: status.defcon?.defcon_level === 'GREEN'
                ? 'rgb(134, 239, 172)'
                : 'rgb(253, 224, 71)',
              border: `1px solid ${status.defcon?.defcon_level === 'GREEN'
                ? 'rgba(34, 197, 94, 0.4)'
                : 'rgba(245, 158, 11, 0.4)'}`
            }}
          >
            DEFCON {status.defcon?.defcon_level || 'UNKNOWN'}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {/* DEFCON Banner */}
        {status.defcon && <DEFCONBanner defcon={status.defcon} />}

        {/* System State Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-4">
          {/* ACI State */}
          <StateCard
            icon={<Brain className="w-4 h-4" />}
            title="ACI (ADR-020)"
            subtitle="Autonomous Cognitive Intelligence"
            state={status.aci?.execution_state || 'INACTIVE'}
            isActive={status.aci?.execution_state === 'ACTIVE'}
            details={status.aci ? [
              { label: 'Dynamic Reasoning', value: status.aci.dynamic_reasoning_loop ? 'ON' : 'OFF' },
              { label: 'SitC Cycle', value: status.aci.sitc_enabled ? 'ENABLED' : 'DISABLED' },
              { label: 'InForage', value: status.aci.inforage_enabled ? 'ENABLED' : 'DISABLED' },
              { label: 'IKEA', value: status.aci.ikea_enabled ? 'ENABLED' : 'DISABLED' },
            ] : []}
            hash={status.aci?.bound_state_hash}
            activatedAt={status.aci?.activated_at}
          />

          {/* Regime Engine State */}
          <StateCard
            icon={<Eye className="w-4 h-4" />}
            title="Regime Engine (IoS-003)"
            subtitle="Market Perception System"
            state={status.regime?.perception_mode || 'PASSIVE'}
            isActive={status.regime?.perception_mode === 'ACTIVE_PERCEPTION'}
            details={status.regime ? [
              { label: 'Refresh', value: status.regime.refresh_interval },
              { label: 'Causal Modifiers', value: status.regime.causal_modifiers_bound ? 'BOUND' : 'UNBOUND' },
              { label: 'Alpha Graph', value: status.regime.alpha_graph_version?.substring(0, 20) || '—' },
            ] : []}
            activatedAt={status.regime?.activated_at}
          />

          {/* Strategy State */}
          <StateCard
            icon={<Target className="w-4 h-4" />}
            title="Strategy (IoS-004)"
            subtitle="LARS Evaluation & Allocation"
            state={status.strategy?.strategy_state || 'FROZEN'}
            isActive={status.strategy?.strategy_state === 'ACTIVE'}
            details={status.strategy ? [
              { label: 'LARS Eval', value: status.strategy.lars_evaluation_enabled ? 'ENABLED' : 'DISABLED' },
              { label: 'DSL Opt', value: status.strategy.dsl_optimization_bound ? 'BOUND' : 'UNBOUND' },
              { label: 'Regime-Aware', value: status.strategy.regime_aware_allocation ? 'YES' : 'NO' },
            ] : []}
            hash={status.strategy?.quad_hash_binding}
            activatedAt={status.strategy?.activated_at}
          />

          {/* CEIO State */}
          <StateCard
            icon={<Database className="w-4 h-4" />}
            title="CEIO Pipeline"
            subtitle="External Signal Integration"
            state={getCEIOState(status.ceio)}
            isActive={status.ceio?.fetch_enabled === true}
            details={status.ceio ? [
              { label: 'Lake Tier', value: status.ceio.lake_tier_enabled ? 'ENABLED' : 'DISABLED' },
              { label: 'Pulse Tier', value: status.ceio.pulse_tier_enabled ? 'ENABLED' : 'DISABLED' },
              { label: 'Sniper Tier', value: status.ceio.sniper_tier_enabled ? 'ENABLED' : 'PENDING' },
              { label: 'ACI Binding', value: status.ceio.aci_binding ? 'BOUND' : 'UNBOUND' },
            ] : []}
            activatedAt={status.ceio?.activated_at}
          />

          {/* Decision Surfaces State */}
          <StateCard
            icon={<Zap className="w-4 h-4" />}
            title="Decision Surfaces (IoS-012)"
            subtitle="Execution Authorization"
            state={status.decision?.execution_authority || 'UNKNOWN'}
            isActive={status.decision?.decision_ledger_enabled === true}
            details={status.decision ? [
              { label: 'Mode', value: status.decision.paper_execution_mode ? 'PAPER' : 'LIVE' },
              { label: 'Calibration', value: `${status.decision.calibration_sequences} sequences` },
              { label: 'Trading Frozen', value: status.decision.trading_surfaces_frozen ? 'YES' : 'NO' },
            ] : []}
            activatedAt={status.decision?.activated_at}
          />

          {/* System Summary */}
          <div
            className="p-4 rounded-lg"
            style={{ backgroundColor: 'hsl(var(--secondary))', border: '1px solid hsl(var(--border))' }}
          >
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-4 h-4" style={{ color: 'hsl(var(--primary))' }} />
              <span className="font-semibold text-sm">System Summary</span>
            </div>
            <div className="space-y-2 text-xs">
              <SummaryRow
                label="Cognitive Layer"
                value={status.aci?.execution_state === 'ACTIVE' ? 'ACTIVE' : 'INACTIVE'}
                isGood={status.aci?.execution_state === 'ACTIVE'}
              />
              <SummaryRow
                label="Perception Layer"
                value={status.regime?.perception_mode === 'ACTIVE_PERCEPTION' ? 'ACTIVE' : 'PASSIVE'}
                isGood={status.regime?.perception_mode === 'ACTIVE_PERCEPTION'}
              />
              <SummaryRow
                label="Strategy Layer"
                value={status.strategy?.strategy_state === 'ACTIVE' ? 'ACTIVE' : 'FROZEN'}
                isGood={status.strategy?.strategy_state === 'ACTIVE'}
              />
              <SummaryRow
                label="Data Pipeline"
                value={status.ceio?.fetch_enabled ? 'ENABLED' : 'DISABLED'}
                isGood={status.ceio?.fetch_enabled === true}
              />
              <SummaryRow
                label="Execution Auth"
                value={status.decision?.execution_authority || 'UNKNOWN'}
                isGood={status.decision?.execution_authority === 'ZERO_EXECUTION'}
              />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function DEFCONBanner({ defcon }: { defcon: DEFCONState }) {
  const isGreen = defcon.defcon_level === 'GREEN'
  const isYellow = defcon.defcon_level === 'YELLOW'

  return (
    <div
      className="p-4 rounded-lg"
      style={{
        backgroundColor: isGreen
          ? 'rgba(34, 197, 94, 0.1)'
          : isYellow
            ? 'rgba(245, 158, 11, 0.1)'
            : 'rgba(239, 68, 68, 0.1)',
        border: `1px solid ${isGreen
          ? 'rgba(34, 197, 94, 0.3)'
          : isYellow
            ? 'rgba(245, 158, 11, 0.3)'
            : 'rgba(239, 68, 68, 0.3)'}`
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className="w-3 h-3 rounded-full animate-pulse"
            style={{
              backgroundColor: isGreen
                ? 'rgb(34, 197, 94)'
                : isYellow
                  ? 'rgb(245, 158, 11)'
                  : 'rgb(239, 68, 68)'
            }}
          />
          <div>
            <span
              className="font-bold"
              style={{
                color: isGreen
                  ? 'rgb(134, 239, 172)'
                  : isYellow
                    ? 'rgb(253, 224, 71)'
                    : 'rgb(252, 165, 165)'
              }}
            >
              DEFCON {defcon.defcon_level}
              {isGreen && ' — Full Autonomy Enabled'}
              {isYellow && ' — Limited Autonomy'}
            </span>
            <p
              className="text-sm mt-1"
              style={{ color: 'hsl(var(--muted-foreground))' }}
            >
              {defcon.trigger_reason}
            </p>
          </div>
        </div>
        <div className="text-right text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          <p>Triggered by {defcon.triggered_by}</p>
          <p>{formatDistanceToNow(new Date(defcon.triggered_at), { addSuffix: true })}</p>
        </div>
      </div>
    </div>
  )
}

interface StateCardProps {
  icon: React.ReactNode
  title: string
  subtitle: string
  state: string
  isActive: boolean
  details: { label: string; value: string }[]
  hash?: string
  activatedAt?: string
}

function StateCard({ icon, title, subtitle, state, isActive, details, hash, activatedAt }: StateCardProps) {
  return (
    <div
      className="p-4 rounded-lg"
      style={{
        backgroundColor: 'hsl(var(--secondary))',
        border: `1px solid ${isActive ? 'rgba(34, 197, 94, 0.4)' : 'hsl(var(--border))'}`
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="p-1.5 rounded"
            style={{
              backgroundColor: isActive
                ? 'rgba(34, 197, 94, 0.2)'
                : 'hsl(var(--background))'
            }}
          >
            {icon}
          </div>
          <div>
            <span className="font-semibold text-sm">{title}</span>
            <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>{subtitle}</p>
          </div>
        </div>
        <StatusBadge variant={isActive ? 'pass' : 'warning'}>
          {state}
        </StatusBadge>
      </div>

      <div className="space-y-1.5">
        {details.map((d, i) => (
          <div key={i} className="flex justify-between text-xs">
            <span style={{ color: 'hsl(var(--muted-foreground))' }}>{d.label}</span>
            <span className="font-mono">{d.value}</span>
          </div>
        ))}
      </div>

      {hash && (
        <div className="mt-3 pt-2" style={{ borderTop: '1px solid hsl(var(--border))' }}>
          <p className="text-xs font-mono truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>
            {hash.substring(0, 40)}...
          </p>
        </div>
      )}

      {activatedAt && (
        <div className="flex items-center gap-1 mt-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          <Clock className="w-3 h-3" />
          <span>Activated {formatDistanceToNow(new Date(activatedAt), { addSuffix: true })}</span>
        </div>
      )}
    </div>
  )
}

function SummaryRow({ label, value, isGood }: { label: string; value: string; isGood: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span style={{ color: 'hsl(var(--muted-foreground))' }}>{label}</span>
      <div className="flex items-center gap-1.5">
        {isGood ? (
          <CheckCircle className="w-3 h-3" style={{ color: 'rgb(34, 197, 94)' }} />
        ) : (
          <AlertTriangle className="w-3 h-3" style={{ color: 'rgb(245, 158, 11)' }} />
        )}
        <span className="font-mono font-medium">{value}</span>
      </div>
    </div>
  )
}

function getCEIOState(ceio: CEIOState | null): string {
  if (!ceio) return 'INACTIVE'
  if (!ceio.fetch_enabled) return 'DISABLED'
  if (ceio.sniper_tier_enabled) return 'FULL_ENABLED'
  if (ceio.pulse_tier_enabled) return 'LAKE+PULSE'
  if (ceio.lake_tier_enabled) return 'LAKE_ONLY'
  return 'PARTIAL'
}
