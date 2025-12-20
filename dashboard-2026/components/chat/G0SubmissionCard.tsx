/**
 * G0 Submission Card Component
 * Narrative vector injection with governance routing
 * Authority: G1 UI Governance Patch - Vision-Chat 2026
 *
 * Routes to oracle_staging for VEGA review (not direct to narrative_vectors)
 *
 * Features:
 * - Domain selector
 * - Probability/confidence sliders
 * - Half-life selector
 * - Governance routing indicator
 */

'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils/cn'
import { Send, AlertCircle, Loader2, CheckCircle, Syringe, Clock, Target, BarChart3 } from 'lucide-react'

interface G0SubmissionCardProps {
  onSubmit: (submission: NarrativeSubmission) => Promise<void>
  isLoading?: boolean
}

export interface NarrativeSubmission {
  domain: string
  narrative: string
  probability: number
  confidence: number
  halfLifeHours: number
}

const DOMAINS = [
  { value: 'Regulatory', color: 'hsl(0, 84%, 60%)' },
  { value: 'Geopolitical', color: 'hsl(217, 91%, 60%)' },
  { value: 'Liquidity', color: 'hsl(142, 76%, 36%)' },
  { value: 'Reflexivity', color: 'hsl(280, 70%, 60%)' },
  { value: 'Sentiment', color: 'hsl(38, 92%, 50%)' },
  { value: 'Technical', color: 'hsl(200, 80%, 50%)' },
  { value: 'Macro', color: 'hsl(320, 70%, 60%)' },
]

const HALF_LIFE_OPTIONS = [
  { hours: 4, label: '4h (Flash)' },
  { hours: 12, label: '12h (Short)' },
  { hours: 24, label: '24h (Day)' },
  { hours: 48, label: '48h (Extended)' },
  { hours: 72, label: '72h (Persistent)' },
  { hours: 168, label: '168h (Week)' },
]

export function G0SubmissionCard({ onSubmit, isLoading }: G0SubmissionCardProps) {
  const [domain, setDomain] = useState('Sentiment')
  const [narrative, setNarrative] = useState('')
  const [probability, setProbability] = useState(0.5)
  const [confidence, setConfidence] = useState(0.5)
  const [halfLifeHours, setHalfLifeHours] = useState(24)
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = async () => {
    if (!narrative.trim() || isLoading) return

    try {
      await onSubmit({
        domain,
        narrative: narrative.trim(),
        probability,
        confidence,
        halfLifeHours,
      })
      setSubmitted(true)
      setTimeout(() => {
        setSubmitted(false)
        setNarrative('')
      }, 3000)
    } catch (error) {
      console.error('Submission failed:', error)
    }
  }

  const selectedDomain = DOMAINS.find(d => d.value === domain)

  return (
    <div
      className="g0-submission-card rounded-lg overflow-hidden"
      style={{
        backgroundColor: 'hsl(var(--card))',
        border: '1px solid hsl(var(--border))',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: '1px solid hsl(var(--border))' }}
      >
        <div className="flex items-center gap-2">
          <Syringe className="w-4 h-4" style={{ color: 'hsl(38, 92%, 50%)' }} />
          <span className="font-semibold text-sm">G0 Submission</span>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded"
            style={{
              backgroundColor: 'hsl(var(--secondary))',
              color: 'hsl(var(--muted-foreground))',
            }}
          >
            Human Oracle Input
          </span>
        </div>
        <div
          className="flex items-center gap-1.5 text-xs px-2 py-1 rounded"
          style={{
            backgroundColor: 'rgba(167, 139, 250, 0.15)',
            color: 'rgb(167, 139, 250)',
          }}
        >
          <AlertCircle className="w-3.5 h-3.5" />
          Routes to VEGA for review
        </div>
      </div>

      {/* Form */}
      <div className="p-4 space-y-4">
        {/* Domain Selector */}
        <div>
          <label className="block text-xs mb-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Domain
          </label>
          <div className="flex flex-wrap gap-2">
            {DOMAINS.map((d) => (
              <button
                key={d.value}
                onClick={() => setDomain(d.value)}
                className={cn(
                  'px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                  domain === d.value ? 'opacity-100' : 'opacity-50 hover:opacity-75'
                )}
                style={{
                  backgroundColor: domain === d.value ? `${d.color}20` : 'transparent',
                  color: d.color,
                  border: `1px solid ${domain === d.value ? `${d.color}40` : 'transparent'}`,
                }}
              >
                {d.value}
              </button>
            ))}
          </div>
        </div>

        {/* Narrative Input */}
        <div>
          <label className="block text-xs mb-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
            Narrative Vector
          </label>
          <textarea
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            placeholder="Describe the narrative or thesis..."
            rows={3}
            className="w-full px-3 py-2 rounded-lg text-sm resize-none"
            style={{
              backgroundColor: 'hsl(var(--secondary))',
              color: 'hsl(var(--foreground))',
              border: '1px solid hsl(var(--border))',
            }}
          />
        </div>

        {/* Sliders Row */}
        <div className="grid grid-cols-2 gap-4">
          {/* Probability */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="flex items-center gap-1.5 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                <Target className="w-3.5 h-3.5" />
                Probability
              </label>
              <span className="text-xs font-mono">{(probability * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={probability * 100}
              onChange={(e) => setProbability(parseInt(e.target.value) / 100)}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, hsl(var(--primary)) ${probability * 100}%, hsl(var(--secondary)) ${probability * 100}%)`,
              }}
            />
          </div>

          {/* Confidence */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="flex items-center gap-1.5 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                <BarChart3 className="w-3.5 h-3.5" />
                Confidence
              </label>
              <span className="text-xs font-mono">{(confidence * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={confidence * 100}
              onChange={(e) => setConfidence(parseInt(e.target.value) / 100)}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
              style={{
                background: `linear-gradient(to right, hsl(142, 76%, 36%) ${confidence * 100}%, hsl(var(--secondary)) ${confidence * 100}%)`,
              }}
            />
          </div>
        </div>

        {/* Half-Life Selector */}
        <div>
          <label className="flex items-center gap-1.5 text-xs mb-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
            <Clock className="w-3.5 h-3.5" />
            Half-Life (Decay Rate)
          </label>
          <div className="flex flex-wrap gap-2">
            {HALF_LIFE_OPTIONS.map((opt) => (
              <button
                key={opt.hours}
                onClick={() => setHalfLifeHours(opt.hours)}
                className={cn(
                  'px-3 py-1.5 rounded text-xs font-mono transition-all',
                  halfLifeHours === opt.hours ? 'opacity-100' : 'opacity-50 hover:opacity-75'
                )}
                style={{
                  backgroundColor: halfLifeHours === opt.hours ? 'hsl(var(--primary) / 0.2)' : 'hsl(var(--secondary))',
                  color: halfLifeHours === opt.hours ? 'hsl(var(--primary))' : 'hsl(var(--muted-foreground))',
                  border: halfLifeHours === opt.hours ? '1px solid hsl(var(--primary) / 0.4)' : '1px solid transparent',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Footer / Submit */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{
          backgroundColor: 'hsl(var(--secondary) / 0.5)',
          borderTop: '1px solid hsl(var(--border))',
        }}
      >
        <div className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Submission routes to <code className="px-1 rounded" style={{ backgroundColor: 'hsl(var(--secondary))' }}>oracle_staging</code> for VEGA G1 review
        </div>
        <button
          onClick={handleSubmit}
          disabled={!narrative.trim() || isLoading || submitted}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
          style={{
            backgroundColor: submitted ? 'rgba(34, 197, 94, 0.2)' : 'hsl(38, 92%, 50%)',
            color: submitted ? 'rgb(134, 239, 172)' : 'black',
          }}
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Submitting...
            </>
          ) : submitted ? (
            <>
              <CheckCircle className="w-4 h-4" />
              Submitted for Review
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Submit G0
            </>
          )}
        </button>
      </div>
    </div>
  )
}
