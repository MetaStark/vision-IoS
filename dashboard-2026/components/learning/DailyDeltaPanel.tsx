/**
 * Daily Delta Panel - CEO-DIR-2026-057
 * "What Did We Learn Today?" - Max 5 bullet points
 *
 * No prose. No fluff. Facts only.
 */

'use client'

import { CheckCircle, XCircle, AlertTriangle, TrendingDown, TrendingUp, Lightbulb } from 'lucide-react'

export interface DailyLearningItem {
  id: string
  type: 'closure' | 'improvement' | 'discovery' | 'warning' | 'no_change'
  text: string
  metric?: string
  delta?: string
}

interface DailyDeltaPanelProps {
  date: string
  items: DailyLearningItem[]
}

const ICON_MAP = {
  closure: CheckCircle,
  improvement: TrendingUp,
  discovery: Lightbulb,
  warning: AlertTriangle,
  no_change: TrendingDown,
}

const COLOR_MAP = {
  closure: 'text-green-400',
  improvement: 'text-blue-400',
  discovery: 'text-yellow-400',
  warning: 'text-orange-400',
  no_change: 'text-gray-400',
}

const BG_MAP = {
  closure: 'bg-green-500/10 border-green-500/20',
  improvement: 'bg-blue-500/10 border-blue-500/20',
  discovery: 'bg-yellow-500/10 border-yellow-500/20',
  warning: 'bg-orange-500/10 border-orange-500/20',
  no_change: 'bg-gray-500/10 border-gray-500/20',
}

export function DailyDeltaPanel({ date, items }: DailyDeltaPanelProps) {
  // Limit to max 5 items per directive
  const displayItems = items.slice(0, 5)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">
            What Did We Learn Today?
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Daily Delta Panel | Facts Only
          </p>
        </div>
        <div className="text-sm text-gray-400 font-mono">
          {date}
        </div>
      </div>

      {/* Learning Items */}
      <div className="space-y-3">
        {displayItems.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <AlertTriangle className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p>No learning events recorded today</p>
          </div>
        ) : (
          displayItems.map((item) => {
            const Icon = ICON_MAP[item.type]
            const colorClass = COLOR_MAP[item.type]
            const bgClass = BG_MAP[item.type]

            return (
              <div
                key={item.id}
                className={`flex items-start gap-3 p-3 rounded-lg border ${bgClass}`}
              >
                <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${colorClass}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200">
                    {item.text}
                  </p>
                  {(item.metric || item.delta) && (
                    <div className="flex items-center gap-3 mt-1">
                      {item.metric && (
                        <span className="text-xs text-gray-500 font-mono">
                          {item.metric}
                        </span>
                      )}
                      {item.delta && (
                        <span className={`text-xs font-mono ${colorClass}`}>
                          {item.delta}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Footer */}
      <div className="mt-4 pt-4 border-t border-gray-800">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <span>{displayItems.length}/5 items</span>
          <span>Source: fhq_governance.v_daily_learning_delta</span>
        </div>
      </div>
    </div>
  )
}
