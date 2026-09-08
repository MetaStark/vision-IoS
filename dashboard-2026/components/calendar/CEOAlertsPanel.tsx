/**
 * CEO Alerts Panel - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Section 4.3: Calendar-Driven CEO Interaction.
 * CEO is only interrupted when judgment is required.
 */

'use client'

import { AlertTriangle, AlertCircle, Info, ChevronRight } from 'lucide-react'

interface CEOAlert {
  id: string
  type: string
  title: string
  summary: string
  options: any[]
  priority: string
  status: string
  date: string
  createdAt: string
}

interface CEOAlertsPanelProps {
  alerts: CEOAlert[]
  onAlertClick?: (alert: CEOAlert) => void
}

const PRIORITY_CONFIG: Record<string, { icon: any; color: string; bg: string }> = {
  CRITICAL: {
    icon: AlertTriangle,
    color: 'text-red-400',
    bg: 'bg-red-500/10 border-red-500/30',
  },
  HIGH: {
    icon: AlertCircle,
    color: 'text-orange-400',
    bg: 'bg-orange-500/10 border-orange-500/30',
  },
  NORMAL: {
    icon: Info,
    color: 'text-blue-400',
    bg: 'bg-blue-500/10 border-blue-500/30',
  },
  LOW: {
    icon: Info,
    color: 'text-gray-400',
    bg: 'bg-gray-500/10 border-gray-500/30',
  },
}

const ALERT_TYPE_LABELS: Record<string, string> = {
  SAMPLE_BEHIND_PLAN: 'Sample Size',
  METRIC_DRIFT: 'Metric Drift',
  REGIME_MISALIGNMENT: 'Regime Alert',
  MID_TEST_REVIEW: 'Mid-Test Review',
  END_TEST_REVIEW: 'End-Test Review',
  JUDGMENT_REQUIRED: 'Decision Required',
  GOVERNANCE_FAILURE: 'Governance',
  DIVERGENCE_DETECTED: 'Divergence',
  VELOCITY_SPIKE: 'Velocity Spike',
}

export function CEOAlertsPanel({ alerts, onAlertClick }: CEOAlertsPanelProps) {
  if (alerts.length === 0) {
    return (
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className="h-5 w-5 text-green-400" />
          <h3 className="text-lg font-semibold text-white">CEO Alerts</h3>
        </div>
        <div className="text-center py-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-500/10 mb-3">
            <AlertCircle className="h-6 w-6 text-green-400" />
          </div>
          <p className="text-gray-400 text-sm">No pending alerts</p>
          <p className="text-gray-600 text-xs mt-1">System operating normally</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="h-5 w-5 text-yellow-400" />
        <h3 className="text-lg font-semibold text-white">CEO Alerts</h3>
        <span className="ml-auto px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded-full text-xs font-medium">
          {alerts.length} pending
        </span>
      </div>

      <div className="space-y-3">
        {alerts.map((alert) => {
          const config = PRIORITY_CONFIG[alert.priority] || PRIORITY_CONFIG.NORMAL
          const Icon = config.icon

          return (
            <button
              key={alert.id}
              onClick={() => onAlertClick?.(alert)}
              className={`w-full text-left p-4 rounded-lg border transition-all hover:scale-[1.01] ${config.bg}`}
            >
              <div className="flex items-start gap-3">
                <Icon className={`h-5 w-5 flex-shrink-0 mt-0.5 ${config.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-medium uppercase ${config.color}`}>
                      {ALERT_TYPE_LABELS[alert.type] || alert.type}
                    </span>
                    <span className="text-xs text-gray-600">
                      {new Date(alert.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                  <h4 className="font-medium text-white text-sm truncate">
                    {alert.title}
                  </h4>
                  <p className="text-xs text-gray-400 mt-1 line-clamp-2">
                    {alert.summary}
                  </p>
                  {alert.options && alert.options.length > 0 && (
                    <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
                      <span>{alert.options.length} decision options available</span>
                      <ChevronRight className="h-3 w-3" />
                    </div>
                  )}
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
