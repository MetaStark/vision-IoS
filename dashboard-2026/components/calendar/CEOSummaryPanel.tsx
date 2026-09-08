/**
 * CEO 30-Second Summary Panel
 *
 * Calendar-as-Law Doctrine: CEO understanding target <30 seconds.
 * This panel delivers system state in one glance:
 *   1. Status icon + sentence (2 sec)
 *   2. Action items if any (5 sec per item)
 *   3. Key metrics row (5 sec)
 *   4. Next critical date (3 sec)
 */

'use client'

import { AlertTriangle, CheckCircle, Clock, TrendingUp, Shield, Zap } from 'lucide-react'

interface CEOSummaryProps {
  canonicalTests: {
    id: string
    name: string
    status: string
    progressPct: number
    verdict?: string
    ceoActionRequired?: boolean
    daysRemaining: number
  }[]
  economicEvents: {
    id: string
    name: string
    status: string
    impactRank: number
    timestamp: string
  }[]
  lvgStatus: {
    deathRatePct: number
    daemonStatus: string
    totalHypotheses: number
    totalActive: number
  }
  alerts: any[]
  governanceChecks: { name: string; status: string; discrepancy?: string }[]
  regime?: {
    currentRegime: string
    confidence: number
    microRegime?: string | null
    momentum?: string | null
  } | null
}

export function CEOSummaryPanel({
  canonicalTests,
  economicEvents,
  lvgStatus,
  alerts,
  governanceChecks,
  regime,
}: CEOSummaryProps) {
  const overdueTests = canonicalTests.filter(t => t.progressPct > 100 && !t.verdict)
  const pendingEconomic = economicEvents.filter(e => e.status === 'PENDING')
  const pendingHighImpact = pendingEconomic.filter(e => e.impactRank >= 4)
  const nextCriticalEvents = economicEvents
    .filter(e => e.status === 'SCHEDULED' && e.impactRank >= 4)
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .slice(0, 2)

  const activeTests = canonicalTests.filter(t => t.status === 'ACTIVE')
  const deathRate = lvgStatus?.deathRatePct || 0
  const deathRateOnTarget = deathRate >= 60 && deathRate <= 90
  const daemonRunning = lvgStatus?.daemonStatus === 'RUNNING'
  const failedChecks = governanceChecks.filter(c => c.status === 'FAIL')

  // Build action items
  const actionItems: { text: string; severity: 'red' | 'yellow' }[] = []

  overdueTests.forEach(t => {
    const overduePct = Math.round(t.progressPct - 100)
    actionItems.push({
      text: `${t.name} \u2014 ${overduePct > 0 ? overduePct + '% overdue, ' : ''}needs verdict`,
      severity: 'red',
    })
  })

  if (pendingHighImpact.length > 0) {
    const names = pendingHighImpact.map(e => e.name).slice(0, 3).join(', ')
    actionItems.push({
      text: `${pendingHighImpact.length} high-impact event${pendingHighImpact.length > 1 ? 's' : ''} missing actuals (${names})`,
      severity: 'yellow',
    })
  }

  if (failedChecks.length > 0) {
    actionItems.push({
      text: `Governance: ${failedChecks.map(c => c.discrepancy || c.name).join('; ')}`,
      severity: 'yellow',
    })
  }

  // Status determination
  let statusLevel: 'green' | 'yellow' | 'red' = 'green'
  let statusSentence = ''

  if (actionItems.some(a => a.severity === 'red')) {
    statusLevel = 'red'
    statusSentence = `${actionItems.length} item${actionItems.length > 1 ? 's' : ''} require CEO attention.`
  } else if (actionItems.length > 0 || !daemonRunning) {
    statusLevel = 'yellow'
    if (!daemonRunning && actionItems.length === 0) {
      statusSentence = 'Learning paused. FINN scheduler not running.'
    } else {
      statusSentence = `${actionItems.length} advisory item${actionItems.length > 1 ? 's' : ''}.`
    }
  } else {
    statusSentence = `All systems nominal. ${activeTests.length} tests active, ${deathRate}% death rate on target.`
  }

  const statusColors = {
    green: {
      bg: 'from-emerald-500/10 to-green-500/10',
      border: 'border-emerald-500/30',
      icon: 'text-emerald-400',
      text: 'text-emerald-400',
    },
    yellow: {
      bg: 'from-amber-500/10 to-yellow-500/10',
      border: 'border-amber-500/30',
      icon: 'text-amber-400',
      text: 'text-amber-400',
    },
    red: {
      bg: 'from-red-500/10 to-rose-500/10',
      border: 'border-red-500/30',
      icon: 'text-red-400',
      text: 'text-red-400',
    },
  }

  const colors = statusColors[statusLevel]
  const StatusIcon = statusLevel === 'green' ? CheckCircle : AlertTriangle

  return (
    <div className={`bg-gradient-to-r ${colors.bg} border ${colors.border} rounded-xl p-5`}>
      {/* Line 1: Status sentence */}
      <div className="flex items-center gap-3 mb-3">
        <StatusIcon className={`h-5 w-5 ${colors.icon} flex-shrink-0`} />
        <p className={`text-sm font-medium ${colors.text}`}>{statusSentence}</p>
      </div>

      {/* Line 2+: Action items */}
      {actionItems.length > 0 && (
        <div className="mb-4 space-y-1.5">
          {actionItems.map((item, i) => (
            <div key={i} className="flex items-start gap-2 pl-8">
              <span
                className={`text-xs mt-0.5 ${
                  item.severity === 'red' ? 'text-red-400' : 'text-amber-400'
                }`}
              >
                {item.severity === 'red' ? '\u25CF' : '\u25CB'}
              </span>
              <p className="text-xs text-gray-300">{item.text}</p>
            </div>
          ))}
        </div>
      )}

      {/* Metrics row */}
      <div className="flex items-center gap-5 flex-wrap">
        <div className="flex items-center gap-1.5">
          <Shield className="h-3.5 w-3.5 text-blue-400" />
          <span className="text-xs text-gray-400">
            <span className="text-white font-semibold">{activeTests.length}</span> tests
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <TrendingUp className="h-3.5 w-3.5 text-purple-400" />
          <span className="text-xs text-gray-400">
            Death{' '}
            <span
              className={`font-semibold ${
                deathRateOnTarget ? 'text-green-400' : 'text-amber-400'
              }`}
            >
              {deathRate}%
            </span>
          </span>
        </div>

        {regime && (
          <div className="flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5 text-red-400" />
            <span className="text-xs text-gray-400">
              <span className="text-white font-semibold">{regime.currentRegime}</span>
              {regime.microRegime && (
                <span className="text-gray-500"> / {regime.microRegime.replace('MR_', '')}</span>
              )}
              <span className="text-gray-600 ml-1">
                ({Math.round(regime.confidence * 100)}%)
              </span>
            </span>
          </div>
        )}

        <div className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5 text-amber-400" />
          <span className="text-xs text-gray-400">
            <span className="text-white font-semibold">{economicEvents.length}</span> econ
          </span>
        </div>

        {alerts.length > 0 && (
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-yellow-400" />
            <span className="text-xs text-yellow-400 font-semibold">
              {alerts.length} alert{alerts.length > 1 ? 's' : ''}
            </span>
          </div>
        )}

        {nextCriticalEvents.length > 0 && (
          <>
            <div className="h-4 w-px bg-gray-700" />
            <div className="text-xs text-gray-500">
              Next:{' '}
              {nextCriticalEvents.map((e, i) => (
                <span key={e.id}>
                  {i > 0 && <span className="text-gray-700"> | </span>}
                  <span className="text-white">{e.name}</span>
                  <span className="text-gray-600">
                    {' '}
                    {new Date(e.timestamp).toLocaleDateString('nb-NO', {
                      day: 'numeric',
                      month: 'short',
                    })}
                  </span>
                </span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
