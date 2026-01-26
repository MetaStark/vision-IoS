/**
 * Canonical Test Card - CEO-DIR-2026-CALENDAR-VISUAL-ENHANCEMENT
 *
 * Modern, human-readable test cards with:
 * - Unique pleasant color per test
 * - 2-sentence max explanations
 * - Clear start/end timestamps with local timezone
 * - Subtle animations for engagement
 */

'use client'

import { useState, useEffect } from 'react'
import {
  FlaskConical,
  Clock,
  Target,
  CheckCircle,
  XCircle,
  ChevronDown,
  Calendar,
  Shield,
  Lightbulb,
  BarChart3,
  Activity,
  Database,
  AlertTriangle,
  Sparkles,
  Play,
  Flag,
} from 'lucide-react'

interface CanonicalTest {
  name: string
  code: string
  owner: string
  status: string
  category: string
  startDate: string
  endDate: string
  daysElapsed: number
  daysRemaining: number
  requiredDays: number
  progressPct: number
  businessIntent?: string
  beneficiarySystem?: string
  hypothesisCode?: string
  baselineDefinition?: any
  targetMetrics?: any
  successCriteria?: any
  failureCriteria?: any
  midTestCheckpoint?: string
  escalationState?: string
  ceoActionRequired?: boolean
  recommendedActions?: string[]
  verdict?: string
  monitoringAgent?: string
  testProgress?: {
    hypothesesInWindow: number
    falsifiedInWindow: number
    activeInWindow: number
    draftInWindow: number
    deathRateInWindow: number | null
    lastHypothesisInWindow: string | null
    verifiedAt: string
    trajectory: 'ON_TARGET' | 'TOO_BRUTAL' | 'TOO_MILD' | 'INSUFFICIENT_DATA' | 'UNKNOWN'
  } | null
}

interface CanonicalTestCardProps {
  test: CanonicalTest
  onActionClick?: (action: string) => void
}

// CEO-DIR-2026-CALENDAR-VISUAL: Unique pleasant colors for each test type
const TEST_COLORS: Record<string, { primary: string; bg: string; border: string; glow: string }> = {
  'EC-022': { primary: '#a78bfa', bg: 'from-violet-500/20 to-purple-500/10', border: 'border-violet-500/40', glow: 'shadow-violet-500/20' },  // Violet - Reward Logic
  'Tier-1': { primary: '#60a5fa', bg: 'from-blue-500/20 to-cyan-500/10', border: 'border-blue-500/40', glow: 'shadow-blue-500/20' },          // Blue - Brutality Calibration
  'Golden': { primary: '#fbbf24', bg: 'from-amber-500/20 to-yellow-500/10', border: 'border-amber-500/40', glow: 'shadow-amber-500/20' },     // Gold - Golden Needles
  'FINN-T': { primary: '#34d399', bg: 'from-emerald-500/20 to-teal-500/10', border: 'border-emerald-500/40', glow: 'shadow-emerald-500/20' }, // Emerald - World Model
  'G1.5':   { primary: '#f472b6', bg: 'from-pink-500/20 to-rose-500/10', border: 'border-pink-500/40', glow: 'shadow-pink-500/20' },          // Pink - Calibration Freeze
}

// 2-sentence human explanations for each test
const TEST_SUMMARIES: Record<string, string> = {
  'EC-022': 'Tester at kontekst-integrering forbedrer prediksjoner før vi aktiverer belønning. Uten bevis risikerer vi å belønne tilfeldigheter.',
  'Tier-1': 'Kalibrerer hvor streng falsifisering skal være. Målet er 60-90% dødsrate: balansen mellom å drepe dårlige ideer og å la gode overleve.',
  'Golden': 'Skaper mangfold i idékildene ved å jakte på gullkorn i markedsdata. Kontrasterer FINN-genererte hypoteser for bedre kalibrering.',
  'FINN-T': 'Genererer hypoteser basert på økonomiske drivere (renter, kreditt, likviditet). Hver idé må forklare hvorfor, ikke bare at.',
  'G1.5': 'Beviser at pre-tier scoring faktisk predikerer overlevelse. Høyere fødselsscore skal gi lengre levetid for hypoteser.',
}

function getTestColorKey(testName: string): string {
  if (testName.includes('Reward') || testName.includes('EC-022')) return 'EC-022'
  if (testName.includes('Tier-1') || testName.includes('Brutality')) return 'Tier-1'
  if (testName.includes('Golden') || testName.includes('Shadow')) return 'Golden'
  if (testName.includes('FINN-T') || testName.includes('World-Model')) return 'FINN-T'
  if (testName.includes('G1.5') || testName.includes('Calibration Freeze')) return 'G1.5'
  return 'Tier-1' // default
}

function AnimatedProgressBar({ elapsed, total, color, startDate, endDate }: {
  elapsed: number
  total: number
  color: string
  startDate?: string
  endDate?: string
}) {
  const pct = Math.min(100, Math.max(0, Math.round((elapsed / total) * 100)))

  return (
    <div className="space-y-2">
      {/* Modern progress track */}
      <div className="relative h-4 bg-gray-800/80 rounded-xl overflow-hidden backdrop-blur-sm">
        {/* Background pattern */}
        <div className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `repeating-linear-gradient(90deg, ${color}20 0px, ${color}20 2px, transparent 2px, transparent 8px)`,
          }}
        />

        {/* Progress fill with glow */}
        <div
          className="absolute inset-y-0 left-0 rounded-xl transition-all duration-700 ease-out"
          style={{
            width: `${pct}%`,
            background: `linear-gradient(90deg, ${color}60, ${color}, ${color}60)`,
            backgroundSize: '200% 100%',
            animation: 'shimmer 3s ease-in-out infinite',
            boxShadow: `0 0 20px ${color}40, inset 0 1px 0 rgba(255,255,255,0.2)`,
          }}
        />

        {/* Day markers */}
        {total <= 30 && Array.from({ length: total - 1 }, (_, i) => (
          <div
            key={i}
            className="absolute top-0 bottom-0 w-px bg-gray-600/30"
            style={{ left: `${((i + 1) / total) * 100}%` }}
          />
        ))}

        {/* Current position indicator */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-5 h-5 rounded-full border-2 border-white shadow-xl transition-all duration-700 z-10"
          style={{
            left: `calc(${pct}% - 10px)`,
            backgroundColor: color,
            boxShadow: `0 0 16px ${color}, 0 0 32px ${color}60`,
          }}
        >
          <div className="absolute inset-1 rounded-full bg-white/30" />
        </div>

        {/* Percentage label */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-[10px] font-bold text-white/90 drop-shadow-lg">
            {pct}%
          </span>
        </div>
      </div>

      {/* Timeline markers */}
      <div className="flex justify-between text-[10px] text-gray-500">
        <span className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color + '60' }} />
          Start
        </span>
        <span className="text-gray-400 font-medium">Dag {elapsed} av {total}</span>
        <span className="flex items-center gap-1">
          Slutt
          <div className="w-2 h-2 rounded-full bg-gray-600" />
        </span>
      </div>
    </div>
  )
}

function DeathRateGauge({
  value,
  minTarget = 60,
  maxTarget = 90,
  trajectory,
  accentColor
}: {
  value: number | null
  minTarget?: number
  maxTarget?: number
  trajectory: string
  accentColor: string
}) {
  const displayValue = value ?? 0
  const isOnTarget = value !== null && value >= minTarget && value <= maxTarget
  const isTooHigh = value !== null && value > maxTarget
  const hasData = value !== null

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-400">Death Rate</span>
        <span
          className="px-2 py-1 rounded text-xs font-semibold"
          style={{
            backgroundColor: trajectory === 'ON_TARGET' ? '#22c55e20' :
                            trajectory === 'TOO_BRUTAL' ? '#ef444420' : '#eab30820',
            color: trajectory === 'ON_TARGET' ? '#22c55e' :
                   trajectory === 'TOO_BRUTAL' ? '#ef4444' : '#eab308'
          }}
        >
          {trajectory === 'ON_TARGET' ? '✓ På mål' :
           trajectory === 'TOO_BRUTAL' ? '⚠ For streng' :
           trajectory === 'INSUFFICIENT_DATA' ? '◌ Venter data' : '⚠ For mild'}
        </span>
      </div>

      <div className="relative h-8 bg-gray-800 rounded-lg overflow-hidden">
        <div
          className="absolute h-full bg-green-500/20 border-l border-r border-green-500/50"
          style={{ left: `${minTarget}%`, width: `${maxTarget - minTarget}%` }}
        />
        <div className="absolute inset-0 flex items-center justify-between px-2 text-xs text-gray-500">
          <span>0%</span>
          <span className="text-green-400/70">{minTarget}-{maxTarget}%</span>
          <span>100%</span>
        </div>
        {hasData && (
          <div
            className="absolute top-0 bottom-0 w-1 transition-all duration-500"
            style={{
              left: `${Math.min(100, displayValue)}%`,
              backgroundColor: isOnTarget ? '#22c55e' : isTooHigh ? '#ef4444' : '#eab308'
            }}
          >
            <div
              className="absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full animate-pulse"
              style={{ backgroundColor: isOnTarget ? '#22c55e' : isTooHigh ? '#ef4444' : '#eab308' }}
            />
          </div>
        )}
      </div>

      <div className="text-center">
        <span className={`text-3xl font-bold ${!hasData ? 'text-gray-500' : ''}`}
              style={{ color: hasData ? (isOnTarget ? '#22c55e' : isTooHigh ? '#ef4444' : '#eab308') : undefined }}>
          {hasData ? `${displayValue.toFixed(1)}%` : '—'}
        </span>
      </div>
    </div>
  )
}

function Section({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
  accentColor
}: {
  title: string
  icon: any
  children: React.ReactNode
  defaultOpen?: boolean
  accentColor: string
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className="border-t border-gray-700/50 pt-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left text-sm text-gray-400 hover:text-white transition-colors"
      >
        <Icon className="h-4 w-4" style={{ color: accentColor }} />
        <span className="font-medium">{title}</span>
        <ChevronDown className={`h-4 w-4 ml-auto transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && <div className="mt-3 space-y-3">{children}</div>}
    </div>
  )
}

export function CanonicalTestCard({ test, onActionClick }: CanonicalTestCardProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const colorKey = getTestColorKey(test.name)
  const colors = TEST_COLORS[colorKey]
  const summary = TEST_SUMMARIES[colorKey]

  // Format timestamp with Oslo timezone
  const formatTimestamp = (dateStr: string) => {
    if (!dateStr) return 'Ikke satt'
    const date = new Date(dateStr)
    return date.toLocaleString('nb-NO', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Europe/Oslo'
    }) + ' CET'
  }

  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl border transition-all duration-500
        ${colors.border} ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}
        hover:shadow-xl ${colors.glow}
      `}
      style={{
        background: `linear-gradient(135deg, rgba(17,24,39,0.95), rgba(17,24,39,0.8))`,
      }}
    >
      {/* Animated gradient border effect */}
      <div
        className="absolute inset-0 opacity-30 pointer-events-none"
        style={{
          background: `linear-gradient(135deg, ${colors.primary}10, transparent 50%, ${colors.primary}05)`,
        }}
      />

      {/* CEO Action Required Banner */}
      {test.ceoActionRequired && (
        <div className="relative bg-red-500/10 border-b border-red-500/30 px-6 py-3">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle className="h-5 w-5 animate-pulse" />
            <span className="font-semibold">CEO-handling påkrevd</span>
          </div>
        </div>
      )}

      {/* Header with color accent */}
      <div className="relative px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: `${colors.primary}20` }}
              >
                <FlaskConical className="h-5 w-5" style={{ color: colors.primary }} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">{test.name}</h3>
                <p className="text-sm text-gray-400">
                  {test.owner} · {test.monitoringAgent || 'STIG'}
                </p>
              </div>
            </div>
          </div>
          <span
            className="px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide animate-pulse"
            style={{
              backgroundColor: `${colors.primary}20`,
              color: colors.primary,
            }}
          >
            {test.verdict || test.status}
          </span>
        </div>

        {/* 2-sentence summary */}
        <div className="mt-4 p-4 rounded-xl bg-gray-800/50 border border-gray-700/50">
          <p className="text-sm text-gray-300 leading-relaxed">
            {summary}
          </p>
        </div>
      </div>

      {/* Timeline with clear start/end */}
      <div className="px-6 pb-4">
        <div className="rounded-xl overflow-hidden" style={{ backgroundColor: `${colors.primary}08` }}>
          {/* Start/End dates - prominently displayed */}
          <div className="grid grid-cols-2 gap-0 border-b" style={{ borderColor: `${colors.primary}20` }}>
            <div className="p-4 border-r" style={{ borderColor: `${colors.primary}20` }}>
              <div className="flex items-center gap-2 mb-2">
                <Play className="h-4 w-4" style={{ color: colors.primary }} />
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Start</span>
              </div>
              <p className="text-sm font-bold text-white">{formatTimestamp(test.startDate)}</p>
            </div>
            <div className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Flag className="h-4 w-4" style={{ color: colors.primary }} />
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Slutt</span>
              </div>
              <p className="text-sm font-bold text-white">{formatTimestamp(test.endDate)}</p>
            </div>
          </div>

          {/* Progress - CEO-DIR-2026-CALENDAR-FIX-001: Database-verified calculation */}
          <div className="p-4">
            <AnimatedProgressBar
              elapsed={test.daysElapsed}
              total={test.requiredDays}
              color={colors.primary}
              startDate={test.startDate}
              endDate={test.endDate}
            />
          </div>
        </div>
      </div>

      {/* Test Progress (Database-Verified) */}
      {test.testProgress && (
        <div className="px-6 pb-4">
          <div
            className="rounded-xl p-4 border"
            style={{
              background: `linear-gradient(135deg, ${colors.primary}10, transparent)`,
              borderColor: `${colors.primary}30`,
            }}
          >
            <div className="flex items-center gap-2 mb-4">
              <Activity className="h-5 w-5" style={{ color: colors.primary }} />
              <h4 className="font-semibold text-white">Live Fremgang</h4>
              <div className="flex items-center gap-1 ml-auto text-xs text-gray-500">
                <Database className="h-3 w-3" />
                <span>Verifisert: {new Date(test.testProgress.verifiedAt).toLocaleTimeString('nb-NO')}</span>
              </div>
            </div>

            <DeathRateGauge
              value={test.testProgress.deathRateInWindow}
              trajectory={test.testProgress.trajectory}
              accentColor={colors.primary}
            />

            {/* Metrics grid */}
            <div className="grid grid-cols-4 gap-2 mt-4">
              {[
                { value: test.testProgress.hypothesesInWindow, label: 'I vindu', color: 'white' },
                { value: test.testProgress.falsifiedInWindow, label: 'Falsifisert', color: '#ef4444' },
                { value: test.testProgress.activeInWindow, label: 'Aktive', color: colors.primary },
                { value: test.testProgress.draftInWindow, label: 'Utkast', color: '#6b7280' },
              ].map((m, i) => (
                <div key={i} className="bg-gray-800/50 rounded-lg p-3 text-center">
                  <p className="text-xl font-bold" style={{ color: m.color }}>{m.value}</p>
                  <p className="text-xs text-gray-500 mt-1">{m.label}</p>
                </div>
              ))}
            </div>

            {test.testProgress.lastHypothesisInWindow && (
              <div className="mt-4 flex items-center gap-2 text-sm text-gray-400">
                <Clock className="h-4 w-4" />
                <span>Siste hypotese: </span>
                <span className="text-white font-medium">
                  {new Date(test.testProgress.lastHypothesisInWindow).toLocaleString('nb-NO', {
                    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit'
                  })}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Collapsible sections */}
      <div className="px-6 pb-6 space-y-4">
        <Section title="Formål" icon={Lightbulb} defaultOpen={false} accentColor={colors.primary}>
          <p className="text-sm text-gray-300">{test.businessIntent}</p>
          {test.beneficiarySystem && (
            <p className="text-xs text-gray-500 mt-2">
              Gevinst for: <span className="text-white">{test.beneficiarySystem}</span>
            </p>
          )}
        </Section>

        <Section title="Måling" icon={BarChart3} accentColor={colors.primary}>
          <div className="bg-gray-800/30 rounded-lg p-3">
            <p className="text-sm text-white">
              Dag {test.daysElapsed} av {test.requiredDays} — {' '}
              {test.daysRemaining > 0 ? `${test.daysRemaining} dager igjen` : 'Ferdig'}
            </p>
          </div>
        </Section>

        <Section title="Suksess/Fiasko" icon={Target} accentColor={colors.primary}>
          {test.successCriteria && (
            <div className="flex items-start gap-2">
              <CheckCircle className="h-4 w-4 text-green-400 mt-0.5" />
              <p className="text-sm text-gray-300">
                {typeof test.successCriteria === 'object'
                  ? test.successCriteria.beskrivelse || test.successCriteria.description
                  : test.successCriteria}
              </p>
            </div>
          )}
          {test.failureCriteria && (
            <div className="flex items-start gap-2">
              <XCircle className="h-4 w-4 text-red-400 mt-0.5" />
              <p className="text-sm text-gray-300">
                {typeof test.failureCriteria === 'object'
                  ? test.failureCriteria.beskrivelse || test.failureCriteria.description
                  : test.failureCriteria}
              </p>
            </div>
          )}
        </Section>

        <Section title="Governance" icon={Shield} accentColor={colors.primary}>
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4" style={{ color: colors.primary }} />
            <span className="text-sm text-gray-400">Neste checkpoint:</span>
            <span className="text-sm text-white">{test.midTestCheckpoint || 'Ved avslutning'}</span>
          </div>
        </Section>
      </div>

      {/* Add shimmer keyframe animation */}
      <style jsx>{`
        @keyframes shimmer {
          0% { background-position: 200% 0; }
          100% { background-position: -200% 0; }
        }
      `}</style>
    </div>
  )
}
