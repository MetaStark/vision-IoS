/**
 * Alert Detail Panel Component
 * CEO-DIR-2026-META-ANALYSIS Phase 4
 *
 * Displays control room alerts with:
 * - Severity-based visual hierarchy
 * - Alert drill-down details
 * - Resolution workflow
 * - Historical context
 *
 * Authority: Dashboard UX Specification 2026 v2.0
 */

'use client'

import { useEffect, useState, useCallback } from 'react'
import { cn } from '@/lib/utils/cn'
import {
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  RefreshCw
} from 'lucide-react'

interface Alert {
  alert_id: string
  alert_type: string
  alert_severity: 'CRITICAL' | 'WARNING' | 'INFO'
  alert_message: string
  alert_source: string | null
  is_resolved: boolean
  created_at: string
  resolved_at: string | null
  resolved_by: string | null
  resolution_notes: string | null
  auto_generated: boolean
  hours_since_created: number
}

interface AlertSummary {
  active_count: number
  critical_count: number
  warning_count: number
  resolved_count: number
  total_count: number
}

interface AlertDetailPanelProps {
  className?: string
  refreshKey?: number
  maxAlerts?: number
  showResolved?: boolean
}

export function AlertDetailPanel({
  className,
  refreshKey = 0,
  maxAlerts = 20,
  showResolved = false
}: AlertDetailPanelProps) {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [summary, setSummary] = useState<AlertSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null)
  const [resolutionNotes, setResolutionNotes] = useState<string>('')
  const [isResolving, setIsResolving] = useState(false)

  const fetchAlerts = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams({
        limit: maxAlerts.toString(),
        resolved: showResolved ? 'true' : 'false'
      })

      const response = await fetch(`/api/alerts?${params}`)

      if (!response.ok) {
        throw new Error('Failed to fetch alerts')
      }

      const data = await response.json()
      setAlerts(data.alerts)
      setSummary(data.summary)
    } catch (err) {
      console.error('[AlertDetailPanel] Fetch error:', err)
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [maxAlerts, showResolved])

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts, refreshKey])

  const resolveAlert = async (alertId: string) => {
    setIsResolving(true)
    try {
      const response = await fetch('/api/alerts', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alert_id: alertId,
          is_resolved: true,
          resolved_by: 'DASHBOARD_USER',
          resolution_notes: resolutionNotes || 'Resolved via dashboard'
        })
      })

      if (!response.ok) {
        throw new Error('Failed to resolve alert')
      }

      // Refresh alerts
      await fetchAlerts()
      setExpandedAlert(null)
      setResolutionNotes('')
    } catch (err) {
      console.error('[AlertDetailPanel] Resolve error:', err)
      setError(err instanceof Error ? err.message : 'Failed to resolve alert')
    } finally {
      setIsResolving(false)
    }
  }

  const getSeverityConfig = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return {
          icon: <AlertCircle className="h-5 w-5" />,
          bgColor: 'bg-red-950/40',
          borderColor: 'border-red-800',
          textColor: 'text-red-400',
          badgeColor: 'bg-red-900 text-red-300'
        }
      case 'WARNING':
        return {
          icon: <AlertTriangle className="h-5 w-5" />,
          bgColor: 'bg-yellow-950/40',
          borderColor: 'border-yellow-800',
          textColor: 'text-yellow-400',
          badgeColor: 'bg-yellow-900 text-yellow-300'
        }
      case 'INFO':
      default:
        return {
          icon: <Info className="h-5 w-5" />,
          bgColor: 'bg-blue-950/40',
          borderColor: 'border-blue-800',
          textColor: 'text-blue-400',
          badgeColor: 'bg-blue-900 text-blue-300'
        }
    }
  }

  const formatTimeAgo = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m ago`
    if (hours < 24) return `${Math.round(hours)}h ago`
    return `${Math.round(hours / 24)}d ago`
  }

  const formatAlertType = (type: string) => {
    return type
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  }

  if (isLoading) {
    return (
      <div className={cn('border border-gray-800 rounded-lg p-6 bg-gray-900/50', className)}>
        <div className="flex items-center justify-center gap-2 text-gray-500">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>Loading alerts...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={cn('border border-red-800 rounded-lg p-6 bg-red-950/30', className)}>
        <div className="flex items-center gap-2 text-red-400">
          <XCircle className="h-5 w-5" />
          <span>{error}</span>
        </div>
      </div>
    )
  }

  return (
    <div className={cn('border border-gray-800 rounded-lg bg-gray-900/50', className)}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-400" />
          <h3 className="font-semibold text-white">Control Room Alerts</h3>
        </div>

        {/* Summary badges */}
        {summary && (
          <div className="flex items-center gap-2">
            {summary.critical_count > 0 && (
              <span className="px-2 py-1 text-xs rounded bg-red-900 text-red-300">
                {summary.critical_count} Critical
              </span>
            )}
            {summary.warning_count > 0 && (
              <span className="px-2 py-1 text-xs rounded bg-yellow-900 text-yellow-300">
                {summary.warning_count} Warning
              </span>
            )}
            <span className="px-2 py-1 text-xs rounded bg-gray-800 text-gray-400">
              {summary.active_count} Active
            </span>
          </div>
        )}
      </div>

      {/* Alert list */}
      <div className="divide-y divide-gray-800">
        {alerts.length === 0 ? (
          <div className="p-6 text-center text-gray-500">
            <CheckCircle className="h-8 w-8 mx-auto mb-2 text-green-500" />
            <p>No active alerts</p>
          </div>
        ) : (
          alerts.map((alert) => {
            const config = getSeverityConfig(alert.alert_severity)
            const isExpanded = expandedAlert === alert.alert_id

            return (
              <div
                key={alert.alert_id}
                className={cn(
                  'transition-colors',
                  config.bgColor,
                  alert.is_resolved && 'opacity-60'
                )}
              >
                {/* Alert row */}
                <button
                  onClick={() => setExpandedAlert(isExpanded ? null : alert.alert_id)}
                  className="w-full p-4 text-left"
                >
                  <div className="flex items-start gap-3">
                    {/* Severity icon */}
                    <div className={cn('mt-0.5', config.textColor)}>
                      {alert.is_resolved ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        config.icon
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={cn('text-xs px-2 py-0.5 rounded', config.badgeColor)}>
                          {alert.alert_severity}
                        </span>
                        <span className="text-xs text-gray-500 truncate">
                          {formatAlertType(alert.alert_type)}
                        </span>
                      </div>
                      <p className={cn('text-sm', alert.is_resolved ? 'text-gray-500' : 'text-gray-300')}>
                        {alert.alert_message}
                      </p>
                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatTimeAgo(alert.hours_since_created)}
                        </span>
                        {alert.alert_source && (
                          <span className="truncate">
                            Source: {alert.alert_source}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Expand arrow */}
                    <div className="text-gray-500">
                      {isExpanded ? (
                        <ChevronUp className="h-5 w-5" />
                      ) : (
                        <ChevronDown className="h-5 w-5" />
                      )}
                    </div>
                  </div>
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-0 border-t border-gray-800/50">
                    <div className="bg-gray-950/50 rounded-lg p-4 space-y-4">
                      {/* Alert details */}
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-gray-500">Alert ID</span>
                          <p className="text-gray-300 font-mono text-xs mt-1">
                            {alert.alert_id}
                          </p>
                        </div>
                        <div>
                          <span className="text-gray-500">Created</span>
                          <p className="text-gray-300 text-xs mt-1">
                            {new Date(alert.created_at).toLocaleString()}
                          </p>
                        </div>
                      </div>

                      {/* Resolution section */}
                      {alert.is_resolved ? (
                        <div className="bg-green-950/30 border border-green-800 rounded p-3">
                          <div className="flex items-center gap-2 text-green-400 text-sm mb-2">
                            <CheckCircle className="h-4 w-4" />
                            <span>Resolved</span>
                          </div>
                          <div className="text-xs text-gray-400 space-y-1">
                            <p>By: {alert.resolved_by}</p>
                            <p>At: {alert.resolved_at ? new Date(alert.resolved_at).toLocaleString() : 'N/A'}</p>
                            {alert.resolution_notes && (
                              <p className="text-gray-300 mt-2">{alert.resolution_notes}</p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <textarea
                            value={resolutionNotes}
                            onChange={(e) => setResolutionNotes(e.target.value)}
                            placeholder="Add resolution notes (optional)..."
                            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-300 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-none"
                            rows={2}
                          />
                          <button
                            onClick={() => resolveAlert(alert.alert_id)}
                            disabled={isResolving}
                            className="flex items-center gap-2 px-4 py-2 bg-green-800 hover:bg-green-700 text-white text-sm rounded transition-colors disabled:opacity-50"
                          >
                            {isResolving ? (
                              <RefreshCw className="h-4 w-4 animate-spin" />
                            ) : (
                              <CheckCircle className="h-4 w-4" />
                            )}
                            Mark as Resolved
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-800 text-xs text-gray-500 text-center">
        Showing {alerts.length} of {summary?.total_count || 0} alerts
      </div>
    </div>
  )
}
