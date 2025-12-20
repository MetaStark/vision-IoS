/**
 * Alpha Discovery (G0) Dashboard
 * EC-018 Meta-Alpha & Freedom Optimizer
 *
 * Per ADR-018 State Discipline: Each artifact displays state-lock indicators
 * (state_hash, regime_at_generation, defcon_at_generation)
 *
 * CRITICAL: EC-018 has ZERO execution authority. G0 = Hypothesis Only.
 * Pipeline: EC-018 → IoS-004 → IoS-008 → IoS-012
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Telescope,
  Play,
  Hash,
  Clock,
  Shield,
  ChevronRight,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Target,
  ArrowRight,
  RefreshCw,
  Lock,
} from 'lucide-react'

// Types matching the API response
interface StateVector {
  state_vector_id: string
  captured_at: string
  state_hash: string
  market_regime: string
  regime_confidence: number
  btc_price: number
  defcon_level: number
}

interface G0Proposal {
  proposal_id: string
  hypothesis_id: string
  hypothesis_title: string
  hypothesis_category: string
  hypothesis_statement: string
  expected_edge_bps: number
  confidence_score: number
  executive_summary: string
  risk_factors: string[]
  proposal_status: string
  created_at: string
  expires_at: string
  falsifiability_validated: boolean
  falsifiability_statement: string
  downstream_pipeline: string[]
  state_lock: {
    state_hash: string
    defcon_at_generation: number
    regime_at_generation: string
    captured_at: string
  }
  // Backtest results from IoS-004
  backtest?: {
    outcome: 'VALIDATED' | 'REJECTED' | 'INSUFFICIENT_DATA' | null
    win_rate: number | null
    sharpe: number | null
    samples: number | null
    rejection_reason: string | null
    completed_at: string | null
  } | null
  queue_status?: string
}

interface HuntSession {
  session_id: string
  session_name: string
  session_status: string
  started_at: string
  completed_at: string | null
  total_cost_usd: number
  hypotheses_generated: number
}

interface AlphaResponse {
  session: HuntSession
  proposals: G0Proposal[]
  state_vector: StateVector
  governance_constraints: {
    execution_authority: string
    capital_risk_allowed: boolean
    downstream_pipeline: string[]
    requires_g1_review: boolean
  }
  telemetry: {
    total_tokens: number
    total_cost_usd: number
    budget_remaining: number
  }
}

// DEFCON color mapping
const defconColors: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: 'rgba(239, 68, 68, 0.2)', text: '#ef4444', label: 'CRITICAL' },
  2: { bg: 'rgba(249, 115, 22, 0.2)', text: '#f97316', label: 'SEVERE' },
  3: { bg: 'rgba(234, 179, 8, 0.2)', text: '#eab308', label: 'ELEVATED' },
  4: { bg: 'rgba(34, 197, 94, 0.2)', text: '#22c55e', label: 'GUARDED' },
  5: { bg: 'rgba(59, 130, 246, 0.2)', text: '#3b82f6', label: 'NORMAL' },
}

// Category colors
const categoryColors: Record<string, { bg: string; text: string }> = {
  REGIME_EDGE: { bg: 'rgba(168, 85, 247, 0.2)', text: '#a855f7' },
  CROSS_ASSET: { bg: 'rgba(59, 130, 246, 0.2)', text: '#3b82f6' },
  TIMING: { bg: 'rgba(34, 197, 94, 0.2)', text: '#22c55e' },
  STRUCTURAL: { bg: 'rgba(249, 115, 22, 0.2)', text: '#f97316' },
}

export default function AlphaDiscoveryPage() {
  const [proposals, setProposals] = useState<G0Proposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [hunting, setHunting] = useState(false)
  const [huntResult, setHuntResult] = useState<AlphaResponse | null>(null)
  const [selectedProposal, setSelectedProposal] = useState<G0Proposal | null>(null)

  // Fetch existing proposals
  const fetchProposals = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/alpha/hunt')
      if (!response.ok) {
        throw new Error('Failed to fetch proposals')
      }
      const data = await response.json()
      setProposals(data.proposals || [])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchProposals()
  }, [fetchProposals])

  // Trigger alpha hunt
  const triggerHunt = async () => {
    try {
      setHunting(true)
      setError(null)
      const response = await fetch('/api/alpha/hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          focus_areas: ['regime_transitions', 'cross_asset_correlations', 'timing_edges'],
          budget_cap_usd: 2.0,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Hunt failed')
      }

      const result: AlphaResponse = await response.json()
      setHuntResult(result)
      // Add new proposals to list
      setProposals(prev => [...result.proposals, ...prev])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hunt failed')
    } finally {
      setHunting(false)
    }
  }

  // Format timestamp
  const formatTime = (iso: string) => {
    const date = new Date(iso)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  // Truncate hash for display
  const truncateHash = (hash: string) => {
    if (!hash) return 'N/A'
    return `${hash.slice(0, 8)}...${hash.slice(-8)}`
  }

  return (
    <div className="min-h-screen p-8" style={{ backgroundColor: 'hsl(var(--background))' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <div
            className="p-3 rounded-xl"
            style={{ backgroundColor: 'hsl(var(--primary) / 0.1)' }}
          >
            <Telescope className="w-8 h-8" style={{ color: 'hsl(var(--primary))' }} />
          </div>
          <div>
            <h1 className="text-2xl font-bold" style={{ color: 'hsl(var(--foreground))' }}>
              Alpha Discovery (G0)
            </h1>
            <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              EC-018 Meta-Alpha & Freedom Optimizer
            </p>
          </div>
        </div>

        {/* Hunt Button */}
        <button
          onClick={triggerHunt}
          disabled={hunting}
          className="flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all"
          style={{
            backgroundColor: hunting ? 'hsl(var(--muted))' : 'hsl(var(--primary))',
            color: hunting ? 'hsl(var(--muted-foreground))' : 'hsl(var(--primary-foreground))',
            opacity: hunting ? 0.7 : 1,
          }}
        >
          {hunting ? (
            <>
              <RefreshCw className="w-5 h-5 animate-spin" />
              Hunting...
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Start Alpha Hunt
            </>
          )}
        </button>
      </div>

      {/* Quick Stats Row - Beginner Friendly */}
      {proposals.length > 0 && (
        <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Total Hypotheses */}
          <div
            className="p-4 rounded-lg"
            style={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
          >
            <p className="text-xs mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Total Hypotheses
            </p>
            <p className="text-2xl font-bold" style={{ color: 'hsl(var(--foreground))' }}>
              {proposals.length}
            </p>
          </div>

          {/* Highest Confidence */}
          <div
            className="p-4 rounded-lg"
            style={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
          >
            <p className="text-xs mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Best Confidence Score
            </p>
            <p className="text-2xl font-bold" style={{ color: 'hsl(var(--primary))' }}>
              {Math.max(...proposals.map(p => (p.confidence_score || 0) * 100)).toFixed(0)}%
            </p>
          </div>

          {/* Top Category */}
          <div
            className="p-4 rounded-lg"
            style={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
          >
            <p className="text-xs mb-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Most Common Category
            </p>
            <p className="text-lg font-bold" style={{ color: 'hsl(var(--foreground))' }}>
              {(() => {
                const cats = proposals.map(p => p.hypothesis_category)
                const counts = cats.reduce((acc, cat) => ({ ...acc, [cat]: (acc[cat] || 0) + 1 }), {} as Record<string, number>)
                return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'
              })()}
            </p>
          </div>
        </div>
      )}

      {/* Top Signals by Confidence - Beginner Friendly Quick View */}
      {proposals.length > 0 && (
        <div
          className="mb-6 p-4 rounded-lg"
          style={{ backgroundColor: 'hsl(var(--card))', border: '1px solid hsl(var(--border))' }}
        >
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'hsl(var(--foreground))' }}>
            <Target className="w-4 h-4" style={{ color: 'hsl(var(--primary))' }} />
            Top Signals by Confidence
          </h3>
          <div className="space-y-2">
            {[...proposals]
              .sort((a, b) => (b.confidence_score || 0) - (a.confidence_score || 0))
              .slice(0, 5)
              .map((p, idx) => (
                <div
                  key={p.proposal_id}
                  className="flex items-center justify-between p-2 rounded cursor-pointer transition-all hover:scale-[1.01]"
                  style={{ backgroundColor: 'hsl(var(--muted) / 0.3)' }}
                  onClick={() => setSelectedProposal(p)}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className="w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold"
                      style={{
                        backgroundColor: idx === 0 ? 'hsl(var(--primary))' : 'hsl(var(--muted))',
                        color: idx === 0 ? 'hsl(var(--primary-foreground))' : 'hsl(var(--muted-foreground))',
                      }}
                    >
                      {idx + 1}
                    </span>
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'hsl(var(--foreground))' }}>
                        {p.hypothesis_title.length > 50 ? p.hypothesis_title.slice(0, 50) + '...' : p.hypothesis_title}
                      </p>
                      <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        {p.hypothesis_category} • +{p.expected_edge_bps}bp expected
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-right">
                    <p className="text-lg font-bold" style={{ color: 'hsl(var(--primary))' }}>
                      {((p.confidence_score || 0) * 100).toFixed(0)}%
                    </p>
                    <ChevronRight className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground))' }} />
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Pipeline Visualization - Compact */}
      <div
        className="mb-8 p-4 rounded-lg"
        style={{ backgroundColor: 'hsl(var(--card))' }}
      >
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'hsl(var(--foreground))' }}>
          Alpha Pipeline
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          {['EC-018', 'IoS-004', 'IoS-008', 'IoS-012'].map((step, idx) => (
            <div key={step} className="flex items-center gap-2">
              <div
                className="px-3 py-1.5 rounded-md text-sm font-medium"
                style={{
                  backgroundColor: idx === 0 ? 'hsl(var(--primary) / 0.2)' : 'hsl(var(--muted))',
                  color: idx === 0 ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))',
                  border: idx === 0 ? '1px solid hsl(var(--primary) / 0.3)' : 'none',
                }}
              >
                {step}
                {idx === 0 && <span className="ml-1 text-xs opacity-70">(G0 Hypothesis)</span>}
                {idx === 1 && <span className="ml-1 text-xs opacity-70">(Backtest)</span>}
                {idx === 2 && <span className="ml-1 text-xs opacity-70">(Runtime)</span>}
                {idx === 3 && <span className="ml-1 text-xs opacity-70">(Execution)</span>}
              </div>
              {idx < 3 && <ArrowRight className="w-4 h-4" style={{ color: 'hsl(var(--muted-foreground))' }} />}
            </div>
          ))}
        </div>
      </div>

      {/* Hunt Result Summary */}
      {huntResult && (
        <div
          className="mb-8 p-4 rounded-lg border"
          style={{
            backgroundColor: 'rgba(34, 197, 94, 0.1)',
            borderColor: 'rgba(34, 197, 94, 0.3)',
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-5 h-5 text-green-400" />
            <span className="font-semibold text-green-400">Hunt Complete</span>
          </div>
          <div className="grid grid-cols-4 gap-4 text-sm">
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>Hypotheses</p>
              <p className="font-semibold text-green-400">{huntResult.session.hypotheses_generated}</p>
            </div>
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>Cost</p>
              <p className="font-semibold text-green-400">${huntResult.telemetry.total_cost_usd.toFixed(4)}</p>
            </div>
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>Tokens</p>
              <p className="font-semibold text-green-400">{huntResult.telemetry.total_tokens.toLocaleString()}</p>
            </div>
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>Budget Remaining</p>
              <p className="font-semibold text-green-400">${huntResult.telemetry.budget_remaining.toFixed(2)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div
          className="mb-6 p-4 rounded-lg border flex items-center gap-3"
          style={{
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            borderColor: 'rgba(239, 68, 68, 0.3)',
          }}
        >
          <XCircle className="w-5 h-5 text-red-400" />
          <span className="text-red-400">{error}</span>
          <button
            onClick={fetchProposals}
            className="ml-auto text-sm underline text-red-400 hover:text-red-300"
          >
            Retry
          </button>
        </div>
      )}

      {/* Proposals Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {loading ? (
          <div className="col-span-2 flex items-center justify-center py-20">
            <RefreshCw className="w-8 h-8 animate-spin" style={{ color: 'hsl(var(--muted-foreground))' }} />
          </div>
        ) : proposals.length === 0 ? (
          <div className="col-span-2 text-center py-20">
            <Telescope className="w-16 h-16 mx-auto mb-4" style={{ color: 'hsl(var(--muted-foreground) / 0.3)' }} />
            <p style={{ color: 'hsl(var(--muted-foreground))' }}>No alpha hypotheses yet</p>
            <p className="text-sm mt-1" style={{ color: 'hsl(var(--muted-foreground) / 0.6)' }}>
              Start an Alpha Hunt to generate G0 proposals
            </p>
          </div>
        ) : (
          proposals.map((proposal) => (
            <ProposalCard
              key={proposal.proposal_id}
              proposal={proposal}
              onSelect={() => setSelectedProposal(proposal)}
              isSelected={selectedProposal?.proposal_id === proposal.proposal_id}
              formatTime={formatTime}
              truncateHash={truncateHash}
            />
          ))
        )}
      </div>

      {/* Selected Proposal Detail Modal */}
      {selectedProposal && (
        <ProposalDetailModal
          proposal={selectedProposal}
          onClose={() => setSelectedProposal(null)}
          formatTime={formatTime}
          truncateHash={truncateHash}
        />
      )}
    </div>
  )
}

// Proposal Card Component
function ProposalCard({
  proposal,
  onSelect,
  isSelected,
  formatTime,
  truncateHash,
}: {
  proposal: G0Proposal
  onSelect: () => void
  isSelected: boolean
  formatTime: (iso: string) => string
  truncateHash: (hash: string) => string
}) {
  const defcon = proposal.state_lock?.defcon_at_generation || 5
  const defconStyle = defconColors[defcon] || defconColors[5]
  const categoryStyle = categoryColors[proposal.hypothesis_category] || categoryColors['STRUCTURAL']

  return (
    <div
      className="rounded-lg border cursor-pointer transition-all hover:scale-[1.01]"
      style={{
        backgroundColor: 'hsl(var(--card))',
        borderColor: isSelected ? 'hsl(var(--primary))' : 'hsl(var(--border))',
      }}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="p-4 border-b" style={{ borderColor: 'hsl(var(--border))' }}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span
                className="px-2 py-0.5 text-xs font-semibold rounded"
                style={{ backgroundColor: categoryStyle.bg, color: categoryStyle.text }}
              >
                {proposal.hypothesis_category}
              </span>
              <span
                className="px-2 py-0.5 text-xs font-semibold rounded"
                style={{ backgroundColor: 'hsl(var(--muted))', color: 'hsl(var(--muted-foreground))' }}
              >
                {proposal.proposal_status}
              </span>
            </div>
            <h3 className="font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
              {proposal.hypothesis_title}
            </h3>
            <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {proposal.hypothesis_id}
            </p>
          </div>
          <div className="flex items-center gap-1">
            <Target className="w-4 h-4" style={{ color: 'hsl(var(--primary))' }} />
            <span className="font-semibold" style={{ color: 'hsl(var(--primary))' }}>
              +{proposal.expected_edge_bps}bp
            </span>
          </div>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="p-4 border-b" style={{ borderColor: 'hsl(var(--border))' }}>
        <div className="flex items-start gap-2">
          <Lightbulb className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'hsl(var(--primary))' }} />
          <p className="text-sm line-clamp-3" style={{ color: 'hsl(var(--foreground))' }}>
            {proposal.executive_summary}
          </p>
        </div>
      </div>

      {/* State Lock Indicators (ADR-018) */}
      <div className="p-4 bg-opacity-50" style={{ backgroundColor: 'hsl(var(--muted) / 0.3)' }}>
        <div className="flex items-center gap-2 mb-2">
          <Lock className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
          <span className="text-xs font-semibold" style={{ color: 'hsl(var(--muted-foreground))' }}>
            STATE LOCK (ADR-018)
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-xs">
          {/* State Hash */}
          <div className="flex items-center gap-1.5">
            <Hash className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
            <span
              className="font-mono truncate"
              style={{ color: 'hsl(var(--foreground))' }}
              title={proposal.state_lock?.state_hash}
            >
              {truncateHash(proposal.state_lock?.state_hash)}
            </span>
          </div>

          {/* Timestamp */}
          <div className="flex items-center gap-1.5">
            <Clock className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
            <span style={{ color: 'hsl(var(--foreground))' }}>
              {formatTime(proposal.state_lock?.captured_at || proposal.created_at)}
            </span>
          </div>

          {/* DEFCON */}
          <div className="flex items-center gap-1.5">
            <Shield className="w-3 h-3" style={{ color: defconStyle.text }} />
            <span
              className="px-1.5 py-0.5 rounded text-xs font-semibold"
              style={{ backgroundColor: defconStyle.bg, color: defconStyle.text }}
            >
              DEFCON-{defcon}
            </span>
          </div>
        </div>
      </div>

      {/* Footer with Backtest Status */}
      <div className="px-4 py-2 flex items-center justify-between text-xs"
        style={{ color: 'hsl(var(--muted-foreground))' }}
      >
        <div className="flex items-center gap-2">
          <span>
            Confidence: {((proposal.confidence_score || 0) * 100).toFixed(0)}%
          </span>
          {/* Backtest Status Badge */}
          {proposal.backtest ? (
            <span
              className="px-1.5 py-0.5 rounded text-xs font-medium"
              style={{
                backgroundColor: proposal.backtest.outcome === 'VALIDATED'
                  ? 'rgba(34, 197, 94, 0.2)'
                  : proposal.backtest.outcome === 'REJECTED'
                  ? 'rgba(239, 68, 68, 0.2)'
                  : 'rgba(234, 179, 8, 0.2)',
                color: proposal.backtest.outcome === 'VALIDATED'
                  ? '#22c55e'
                  : proposal.backtest.outcome === 'REJECTED'
                  ? '#ef4444'
                  : '#eab308',
              }}
            >
              {proposal.backtest.outcome === 'VALIDATED' && '✓ Validated'}
              {proposal.backtest.outcome === 'REJECTED' && '✗ Rejected'}
              {proposal.backtest.outcome === 'INSUFFICIENT_DATA' && '⚠ Need Data'}
            </span>
          ) : proposal.queue_status === 'PENDING' ? (
            <span
              className="px-1.5 py-0.5 rounded text-xs font-medium"
              style={{ backgroundColor: 'rgba(59, 130, 246, 0.2)', color: '#3b82f6' }}
            >
              ⏳ Queued
            </span>
          ) : (
            <span
              className="px-1.5 py-0.5 rounded text-xs font-medium"
              style={{ backgroundColor: 'hsl(var(--muted))', color: 'hsl(var(--muted-foreground))' }}
            >
              G0 Draft
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <span>View Details</span>
          <ChevronRight className="w-3 h-3" />
        </div>
      </div>
    </div>
  )
}

// Proposal Detail Modal
function ProposalDetailModal({
  proposal,
  onClose,
  formatTime,
  truncateHash,
}: {
  proposal: G0Proposal
  onClose: () => void
  formatTime: (iso: string) => string
  truncateHash: (hash: string) => string
}) {
  const defcon = proposal.state_lock?.defcon_at_generation || 5
  const defconStyle = defconColors[defcon] || defconColors[5]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.8)' }}
      onClick={onClose}
    >
      <div
        className="max-w-2xl w-full max-h-[90vh] overflow-auto rounded-xl"
        style={{ backgroundColor: 'hsl(var(--card))' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-6 border-b" style={{ borderColor: 'hsl(var(--border))' }}>
          <div className="flex items-start justify-between">
            <div>
              <span
                className="px-2 py-0.5 text-xs font-semibold rounded"
                style={{
                  backgroundColor: categoryColors[proposal.hypothesis_category]?.bg,
                  color: categoryColors[proposal.hypothesis_category]?.text,
                }}
              >
                {proposal.hypothesis_category}
              </span>
              <h2 className="text-xl font-bold mt-2" style={{ color: 'hsl(var(--foreground))' }}>
                {proposal.hypothesis_title}
              </h2>
              <p className="text-sm mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                {proposal.hypothesis_id}
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              style={{ color: 'hsl(var(--muted-foreground))' }}
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* State Lock Section */}
        <div
          className="p-4 border-b"
          style={{
            backgroundColor: 'hsl(var(--muted) / 0.3)',
            borderColor: 'hsl(var(--border))',
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <Lock className="w-4 h-4" style={{ color: 'hsl(var(--primary))' }} />
            <span className="text-sm font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
              State Lock (ADR-018 Immutability)
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>State Hash</p>
              <p className="font-mono text-xs break-all" style={{ color: 'hsl(var(--foreground))' }}>
                {proposal.state_lock?.state_hash || 'N/A'}
              </p>
            </div>
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>Captured At</p>
              <p style={{ color: 'hsl(var(--foreground))' }}>
                {formatTime(proposal.state_lock?.captured_at || proposal.created_at)}
              </p>
            </div>
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>Regime at Generation</p>
              <p style={{ color: 'hsl(var(--foreground))' }}>
                {proposal.state_lock?.regime_at_generation || 'N/A'}
              </p>
            </div>
            <div>
              <p style={{ color: 'hsl(var(--muted-foreground))' }}>DEFCON at Generation</p>
              <span
                className="px-2 py-0.5 rounded text-xs font-semibold inline-block"
                style={{ backgroundColor: defconStyle.bg, color: defconStyle.text }}
              >
                DEFCON-{defcon} ({defconStyle.label})
              </span>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-6">
          {/* Hypothesis Statement */}
          <div>
            <h3 className="text-sm font-semibold mb-2" style={{ color: 'hsl(var(--foreground))' }}>
              Hypothesis Statement
            </h3>
            <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {proposal.hypothesis_statement}
            </p>
          </div>

          {/* Executive Summary */}
          <div>
            <h3 className="text-sm font-semibold mb-2" style={{ color: 'hsl(var(--foreground))' }}>
              Executive Summary
            </h3>
            <p className="text-sm" style={{ color: 'hsl(var(--foreground))' }}>
              {proposal.executive_summary}
            </p>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-4">
            <div
              className="p-3 rounded-lg"
              style={{ backgroundColor: 'hsl(var(--muted) / 0.5)' }}
            >
              <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Expected Edge
              </p>
              <p className="text-xl font-bold" style={{ color: 'hsl(var(--primary))' }}>
                +{proposal.expected_edge_bps}bp
              </p>
            </div>
            <div
              className="p-3 rounded-lg"
              style={{ backgroundColor: 'hsl(var(--muted) / 0.5)' }}
            >
              <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Confidence
              </p>
              <p className="text-xl font-bold" style={{ color: 'hsl(var(--foreground))' }}>
                {((proposal.confidence_score || 0) * 100).toFixed(0)}%
              </p>
            </div>
            <div
              className="p-3 rounded-lg"
              style={{ backgroundColor: 'hsl(var(--muted) / 0.5)' }}
            >
              <p className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                Falsifiable
              </p>
              <p className="text-xl font-bold" style={{ color: proposal.falsifiability_validated ? '#22c55e' : '#eab308' }}>
                {proposal.falsifiability_validated ? 'Yes' : 'Pending'}
              </p>
            </div>
          </div>

          {/* IoS-004 Backtest Results */}
          {proposal.backtest && (
            <div
              className="p-4 rounded-lg border"
              style={{
                backgroundColor: proposal.backtest.outcome === 'VALIDATED'
                  ? 'rgba(34, 197, 94, 0.1)'
                  : proposal.backtest.outcome === 'REJECTED'
                  ? 'rgba(239, 68, 68, 0.1)'
                  : 'rgba(234, 179, 8, 0.1)',
                borderColor: proposal.backtest.outcome === 'VALIDATED'
                  ? 'rgba(34, 197, 94, 0.3)'
                  : proposal.backtest.outcome === 'REJECTED'
                  ? 'rgba(239, 68, 68, 0.3)'
                  : 'rgba(234, 179, 8, 0.3)',
              }}
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold" style={{ color: 'hsl(var(--foreground))' }}>
                  IoS-004 Backtest Results
                </h3>
                <span
                  className="px-2 py-1 rounded text-xs font-semibold"
                  style={{
                    backgroundColor: proposal.backtest.outcome === 'VALIDATED'
                      ? 'rgba(34, 197, 94, 0.2)'
                      : proposal.backtest.outcome === 'REJECTED'
                      ? 'rgba(239, 68, 68, 0.2)'
                      : 'rgba(234, 179, 8, 0.2)',
                    color: proposal.backtest.outcome === 'VALIDATED'
                      ? '#22c55e'
                      : proposal.backtest.outcome === 'REJECTED'
                      ? '#ef4444'
                      : '#eab308',
                  }}
                >
                  {proposal.backtest.outcome}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <p style={{ color: 'hsl(var(--muted-foreground))' }}>Win Rate</p>
                  <p className="font-semibold" style={{
                    color: (proposal.backtest.win_rate ?? 0) >= 0.52 ? '#22c55e' : '#ef4444'
                  }}>
                    {proposal.backtest.win_rate != null ? `${(proposal.backtest.win_rate * 100).toFixed(1)}%` : 'N/A'}
                  </p>
                </div>
                <div>
                  <p style={{ color: 'hsl(var(--muted-foreground))' }}>Sharpe Ratio</p>
                  <p className="font-semibold" style={{
                    color: (proposal.backtest.sharpe ?? 0) >= 0.3 ? '#22c55e' : '#ef4444'
                  }}>
                    {proposal.backtest.sharpe != null ? proposal.backtest.sharpe.toFixed(2) : 'N/A'}
                  </p>
                </div>
                <div>
                  <p style={{ color: 'hsl(var(--muted-foreground))' }}>Samples</p>
                  <p className="font-semibold" style={{
                    color: (proposal.backtest.samples ?? 0) >= 30 ? '#22c55e' : '#eab308'
                  }}>
                    {proposal.backtest.samples != null ? proposal.backtest.samples : 'N/A'}
                  </p>
                </div>
              </div>
              {proposal.backtest.rejection_reason && (
                <p className="mt-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  Reason: {proposal.backtest.rejection_reason}
                </p>
              )}
            </div>
          )}

          {/* Pending Backtest */}
          {!proposal.backtest && proposal.queue_status === 'PENDING' && (
            <div
              className="p-4 rounded-lg border"
              style={{
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderColor: 'rgba(59, 130, 246, 0.3)',
              }}
            >
              <div className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" style={{ color: '#3b82f6' }} />
                <span className="text-sm font-medium" style={{ color: '#3b82f6' }}>
                  Queued for IoS-004 Backtest Validation
                </span>
              </div>
            </div>
          )}

          {/* Falsification Statement */}
          {proposal.falsifiability_statement && (
            <div>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'hsl(var(--foreground))' }}>
                Falsification Criteria
              </h3>
              <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
                {proposal.falsifiability_statement}
              </p>
            </div>
          )}

          {/* Risk Factors */}
          {proposal.risk_factors && proposal.risk_factors.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'hsl(var(--foreground))' }}>
                Risk Factors
              </h3>
              <ul className="space-y-1">
                {proposal.risk_factors.map((risk, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm">
                    <AlertTriangle className="w-3 h-3 mt-1 text-yellow-400" />
                    <span style={{ color: 'hsl(var(--muted-foreground))' }}>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Pipeline */}
          <div>
            <h3 className="text-sm font-semibold mb-2" style={{ color: 'hsl(var(--foreground))' }}>
              Downstream Pipeline
            </h3>
            <div className="flex items-center gap-2">
              {(proposal.downstream_pipeline || ['IoS-004', 'IoS-008', 'IoS-012']).map((step, idx, arr) => (
                <div key={step} className="flex items-center gap-2">
                  <span
                    className="px-2 py-1 rounded text-xs font-medium"
                    style={{
                      backgroundColor: 'hsl(var(--muted))',
                      color: 'hsl(var(--muted-foreground))',
                    }}
                  >
                    {step}
                  </span>
                  {idx < arr.length - 1 && (
                    <ArrowRight className="w-3 h-3" style={{ color: 'hsl(var(--muted-foreground))' }} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          className="p-4 border-t flex items-center justify-between"
          style={{ borderColor: 'hsl(var(--border))' }}
        >
          <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Created: {formatTime(proposal.created_at)}
            {proposal.backtest?.completed_at && ` | Backtested: ${formatTime(proposal.backtest.completed_at)}`}
          </div>
          <div
            className="px-3 py-1 rounded text-xs font-semibold"
            style={{
              backgroundColor: proposal.backtest?.outcome === 'VALIDATED'
                ? 'rgba(34, 197, 94, 0.2)'
                : proposal.backtest?.outcome === 'REJECTED'
                ? 'rgba(239, 68, 68, 0.2)'
                : proposal.backtest?.outcome === 'INSUFFICIENT_DATA'
                ? 'rgba(234, 179, 8, 0.2)'
                : 'hsl(var(--primary) / 0.2)',
              color: proposal.backtest?.outcome === 'VALIDATED'
                ? '#22c55e'
                : proposal.backtest?.outcome === 'REJECTED'
                ? '#ef4444'
                : proposal.backtest?.outcome === 'INSUFFICIENT_DATA'
                ? '#eab308'
                : 'hsl(var(--primary))',
            }}
          >
            {proposal.backtest?.outcome === 'VALIDATED' && 'G1 Validated • Ready for IoS-008'}
            {proposal.backtest?.outcome === 'REJECTED' && 'G1 Rejected • Hypothesis Failed'}
            {proposal.backtest?.outcome === 'INSUFFICIENT_DATA' && 'G1 Pending • Need More Data'}
            {!proposal.backtest && proposal.queue_status === 'PENDING' && 'G0 Queued • Awaiting Backtest'}
            {!proposal.backtest && proposal.queue_status !== 'PENDING' && 'G0 Hypothesis • Awaiting Backtest'}
          </div>
        </div>
      </div>
    </div>
  )
}
