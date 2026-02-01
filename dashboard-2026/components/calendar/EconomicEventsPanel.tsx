/**
 * Economic Events Panel - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Section 2: IoS-016 Economic Calendar integration.
 * Display upcoming economic events with date, time, and event details.
 */

'use client'

import { TrendingUp, Clock, Calendar as CalendarIcon, Landmark, Briefcase, BarChart3, DollarSign, Bitcoin, AlertCircle } from 'lucide-react'

interface EconomicEvent {
  id: string
  name: string
  typeCode: string
  timestamp: string
  consensus: number | null
  previous: number | null
  actual: number | null
  surprise: number | null
  impactRank: number
  category: string
  status: string
}

interface EconomicEventsPanelProps {
  events: EconomicEvent[]
}

// Map event type codes to icons
function getEventIcon(typeCode: string) {
  if (typeCode.includes('FOMC') || typeCode.includes('FED') || typeCode.includes('RATE') || typeCode.includes('ECB')) {
    return <Landmark className="h-4 w-4" />
  }
  if (typeCode.includes('NFP') || typeCode.includes('EMPLOYMENT') || typeCode.includes('JOBLESS')) {
    return <Briefcase className="h-4 w-4" />
  }
  if (typeCode.includes('CPI') || typeCode.includes('PPI') || typeCode.includes('INFLATION')) {
    return <BarChart3 className="h-4 w-4" />
  }
  if (typeCode.includes('GDP') || typeCode.includes('RETAIL') || typeCode.includes('TRADE')) {
    return <DollarSign className="h-4 w-4" />
  }
  if (typeCode.includes('BTC') || typeCode.includes('CRYPTO')) {
    return <Bitcoin className="h-4 w-4" />
  }
  return <CalendarIcon className="h-4 w-4" />
}

// Get impact color
function getImpactColor(impactRank: number) {
  switch (impactRank) {
    case 5: return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' }
    case 4: return { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/30' }
    case 3: return { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' }
    case 2: return { bg: 'bg-lime-500/20', text: 'text-lime-400', border: 'border-lime-500/30' }
    default: return { bg: 'bg-gray-500/20', text: 'text-gray-400', border: 'border-gray-500/30' }
  }
}

// Format timestamp for display
function formatEventTime(timestamp: string) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function formatEventDate(timestamp: string) {
  const date = new Date(timestamp)
  return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

// Group events by date
function groupEventsByDate(events: EconomicEvent[]): Record<string, EconomicEvent[]> {
  return events.reduce((groups, event) => {
    const dateKey = new Date(event.timestamp).toISOString().split('T')[0]
    if (!groups[dateKey]) {
      groups[dateKey] = []
    }
    groups[dateKey].push(event)
    return groups
  }, {} as Record<string, EconomicEvent[]>)
}

function EconomicEventRow({ event }: { event: EconomicEvent }) {
  const colors = getImpactColor(event.impactRank)

  return (
    <div className={`flex items-center gap-3 p-3 rounded-lg ${colors.bg} border ${colors.border} mb-2`}>
      {/* Icon */}
      <div className={colors.text}>
        {getEventIcon(event.typeCode)}
      </div>

      {/* Event Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-white truncate">{event.name}</p>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
            event.status === 'RELEASED' ? 'bg-green-500/20 text-green-400' :
            event.status === 'PENDING' ? 'bg-yellow-500/20 text-yellow-400' :
            'bg-gray-500/20 text-gray-400'
          }`}>
            {event.status}
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-0.5">{event.category}</p>
      </div>

      {/* Time */}
      <div className="text-right">
        <div className="flex items-center gap-1 text-xs text-gray-400">
          <Clock className="h-3 w-3" />
          <span>{formatEventTime(event.timestamp)}</span>
        </div>
      </div>

      {/* Values */}
      <div className="text-right min-w-[100px]">
        {event.actual !== null ? (
          <div>
            <p className="text-sm font-mono text-white">{event.actual}</p>
            {event.surprise !== null && parseFloat(String(event.surprise)) !== 0 && (
              <p className={`text-xs ${parseFloat(String(event.surprise)) > 0 ? 'text-green-400' : 'text-red-400'}`}>
                {parseFloat(String(event.surprise)) > 0 ? '+' : ''}{(parseFloat(String(event.surprise)) * 100).toFixed(2)}% surprise
              </p>
            )}
          </div>
        ) : (
          <div>
            <p className="text-xs text-gray-500">Consensus</p>
            <p className="text-sm font-mono text-gray-300">{event.consensus ?? 'N/A'}</p>
          </div>
        )}
      </div>

      {/* Impact Badge */}
      <div className={`flex items-center gap-1 px-2 py-1 rounded ${colors.bg} ${colors.text} text-xs font-medium`}>
        <AlertCircle className="h-3 w-3" />
        <span>{event.impactRank}</span>
      </div>
    </div>
  )
}

export function EconomicEventsPanel({ events }: EconomicEventsPanelProps) {
  if (events.length === 0) {
    return (
      <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="h-5 w-5 text-amber-400" />
          <h3 className="text-lg font-semibold text-white">Economic Calendar</h3>
          <span className="ml-auto text-xs text-gray-500">IoS-016</span>
        </div>
        <p className="text-gray-500 text-sm">No upcoming economic events in the selected range.</p>
      </div>
    )
  }

  const groupedEvents = groupEventsByDate(events)
  const today = new Date().toISOString().split('T')[0]

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-amber-400" />
        <h3 className="text-lg font-semibold text-white">Economic Calendar</h3>
        <span className="ml-auto px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded-full text-xs font-medium">
          {events.length} events
        </span>
        <span className="text-xs text-gray-500">IoS-016</span>
      </div>

      {/* Impact Legend */}
      <div className="flex items-center gap-4 mb-4 text-xs">
        <span className="text-gray-500">Impact:</span>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-gray-400">5 (High)</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-orange-500" />
          <span className="text-gray-400">4</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-500" />
          <span className="text-gray-400">3</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-lime-500" />
          <span className="text-gray-400">2</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-gray-500" />
          <span className="text-gray-400">1 (Low)</span>
        </div>
      </div>

      {/* Events by Date */}
      <div className="space-y-6 max-h-[500px] overflow-y-auto pr-2">
        {Object.entries(groupedEvents)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([date, dateEvents]) => (
            <div key={date}>
              <div className="flex items-center gap-2 mb-2">
                <CalendarIcon className="h-4 w-4 text-gray-500" />
                <p className={`text-sm font-medium ${date === today ? 'text-amber-400' : 'text-gray-400'}`}>
                  {formatEventDate(dateEvents[0].timestamp)}
                  {date === today && (
                    <span className="ml-2 px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded text-[10px]">
                      TODAY
                    </span>
                  )}
                </p>
                <span className="text-xs text-gray-600">{dateEvents.length} event{dateEvents.length > 1 ? 's' : ''}</span>
              </div>
              <div>
                {dateEvents
                  .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
                  .map((event) => (
                    <EconomicEventRow key={event.id} event={event} />
                  ))}
              </div>
            </div>
          ))}
      </div>
    </div>
  )
}
