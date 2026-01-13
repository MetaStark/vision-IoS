/**
 * Evidence Clock Widget - CEO-DIR-2026-059
 * Canonical Time Anchor & Evidence-Clock Protocol
 *
 * Shows:
 * - Canonical NOW (DB time)
 * - Data coverage span (earliest → latest)
 * - Holdout eligibility status
 */

'use client'

import { Clock, Database, Calendar, AlertTriangle, CheckCircle } from 'lucide-react'

export interface EvidenceClockData {
  canonicalNow: string
  operationalStart: string | null
  holdoutWindowStart: string | null
  holdoutWindowEnd: string | null
  forecastDaysAvailable: number
  outcomeDaysAvailable: number
  totalHoldoutEligibleRecords: number
  holdoutEligibilityStatus: string
}

interface EvidenceClockProps {
  data: EvidenceClockData | null
}

function formatDate(dateString: string | null): string {
  if (!dateString) return '—'
  try {
    return new Date(dateString).toLocaleDateString('en-GB', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  } catch {
    return '—'
  }
}

function formatTime(dateString: string | null): string {
  if (!dateString) return '—'
  try {
    return new Date(dateString).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short'
    })
  } catch {
    return '—'
  }
}

export function EvidenceClock({ data }: EvidenceClockProps) {
  const isBlocked = data?.holdoutEligibilityStatus?.startsWith('BLOCKED') ?? true

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Clock className="h-5 w-5 text-cyan-400" />
          <div>
            <h3 className="text-lg font-semibold text-white">
              Evidence Clock
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Canonical Time & Data Availability
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500">CEO-DIR-2026-059</div>
        </div>
      </div>

      {/* Canonical Now */}
      <div className="mb-4 p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-cyan-400" />
            <span className="text-xs text-cyan-400">Canonical NOW (DB Time)</span>
          </div>
          <div className="text-right">
            <div className="text-sm font-mono text-cyan-400">
              {formatTime(data?.canonicalNow ?? null)}
            </div>
            <div className="text-xs text-cyan-400/70">
              {formatDate(data?.canonicalNow ?? null)}
            </div>
          </div>
        </div>
      </div>

      {/* Data Coverage Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* Operational Start */}
        <div className="p-3 bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Calendar className="h-3.5 w-3.5 text-gray-400" />
            <span className="text-xs text-gray-400">Operational Start</span>
          </div>
          <div className="text-sm font-mono text-white">
            {formatDate(data?.operationalStart ?? null)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {data?.forecastDaysAvailable ?? 0} days of forecasts
          </div>
        </div>

        {/* Holdout Window */}
        <div className="p-3 bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-2">
            <Calendar className="h-3.5 w-3.5 text-gray-400" />
            <span className="text-xs text-gray-400">Holdout Eligible Window</span>
          </div>
          <div className="text-sm font-mono text-white">
            {formatDate(data?.holdoutWindowStart ?? null)} → {formatDate(data?.holdoutWindowEnd ?? null)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {data?.outcomeDaysAvailable ?? 0} days with outcomes
          </div>
        </div>
      </div>

      {/* Records Count */}
      <div className="mb-4 p-3 bg-gray-800/50 rounded-lg">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">Total Holdout-Eligible Records</span>
          <span className="text-sm font-mono text-white">
            {(data?.totalHoldoutEligibleRecords ?? 0).toLocaleString()}
          </span>
        </div>
      </div>

      {/* Holdout Eligibility Status */}
      <div className={`p-3 rounded-lg border ${
        isBlocked
          ? 'bg-yellow-500/10 border-yellow-500/30'
          : 'bg-green-500/10 border-green-500/30'
      }`}>
        <div className="flex items-start gap-2">
          {isBlocked ? (
            <AlertTriangle className="h-4 w-4 text-yellow-400 mt-0.5" />
          ) : (
            <CheckCircle className="h-4 w-4 text-green-400 mt-0.5" />
          )}
          <div>
            <div className={`text-xs font-medium ${
              isBlocked ? 'text-yellow-400' : 'text-green-400'
            }`}>
              Holdout Eligibility
            </div>
            <div className={`text-xs mt-1 ${
              isBlocked ? 'text-yellow-400/80' : 'text-green-400/80'
            }`}>
              {data?.holdoutEligibilityStatus ?? 'Loading...'}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-gray-800">
        <div className="text-xs text-gray-600">
          Source: fhq_governance.v_evidence_clock
        </div>
      </div>
    </div>
  )
}
