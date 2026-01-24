/**
 * Calendar Grid Component - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Modern monthly grid view with clean, contemporary, light color palette.
 * CEO must understand system state in <30 seconds.
 */

'use client'

import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils/cn'

interface CalendarEvent {
  id: string
  name: string
  category: string
  date: string
  endDate?: string
  status: string
  owner: string
  details: any
  color: string
  day: number
  month: number
  year: number
}

interface CalendarGridProps {
  events: CalendarEvent[]
  currentYear: number
  currentMonth: number
  onEventClick?: (event: CalendarEvent) => void
}

// Category labels for legend (CEO-facing, no internal names)
const CATEGORY_LABELS: Record<string, string> = {
  CANONICAL_TEST: 'Tests',
  ACTIVE_TEST: 'Tests',
  OBSERVATION_WINDOW: 'Observation Windows',
  CEO_ACTION_REQUIRED: 'CEO Action Required',
  DIVERGENCE_POINT: 'Divergence Points',
  ECONOMIC_EVENT: 'Economic Events',
  COMPLETED: 'Completed',
  ARCHIVED: 'Archived',
}

export function CalendarGrid({
  events,
  currentYear,
  currentMonth,
  onEventClick,
}: CalendarGridProps) {
  const [viewYear, setViewYear] = useState(currentYear)
  const [viewMonth, setViewMonth] = useState(currentMonth)

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ]

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  // Calculate calendar grid
  const calendarDays = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth - 1, 1)
    const lastDay = new Date(viewYear, viewMonth, 0)
    const startDayOfWeek = firstDay.getDay()
    const daysInMonth = lastDay.getDate()

    const days: (number | null)[] = []

    // Add empty cells for days before the first of the month
    for (let i = 0; i < startDayOfWeek; i++) {
      days.push(null)
    }

    // Add days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      days.push(day)
    }

    return days
  }, [viewYear, viewMonth])

  // Get events for a specific day
  const getEventsForDay = (day: number) => {
    return events.filter((event) => {
      const eventDate = new Date(event.date)
      return (
        eventDate.getFullYear() === viewYear &&
        eventDate.getMonth() + 1 === viewMonth &&
        eventDate.getDate() === day
      )
    })
  }

  // Navigation
  const goToPreviousMonth = () => {
    if (viewMonth === 1) {
      setViewMonth(12)
      setViewYear(viewYear - 1)
    } else {
      setViewMonth(viewMonth - 1)
    }
  }

  const goToNextMonth = () => {
    if (viewMonth === 12) {
      setViewMonth(1)
      setViewYear(viewYear + 1)
    } else {
      setViewMonth(viewMonth + 1)
    }
  }

  const goToToday = () => {
    setViewYear(currentYear)
    setViewMonth(currentMonth)
  }

  const isToday = (day: number) => {
    const today = new Date()
    return (
      today.getFullYear() === viewYear &&
      today.getMonth() + 1 === viewMonth &&
      today.getDate() === day
    )
  }

  // Get unique categories for legend
  const uniqueCategories = useMemo(() => {
    const categories = new Set(events.map((e) => e.category))
    return Array.from(categories)
  }, [events])

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={goToPreviousMonth}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <ChevronLeft className="h-5 w-5 text-gray-400" />
          </button>
          <h2 className="text-xl font-semibold text-white min-w-[200px] text-center">
            {monthNames[viewMonth - 1]} {viewYear}
          </h2>
          <button
            onClick={goToNextMonth}
            className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
          >
            <ChevronRight className="h-5 w-5 text-gray-400" />
          </button>
        </div>
        <button
          onClick={goToToday}
          className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg text-sm font-medium hover:bg-blue-500/30 transition-colors"
        >
          Today
        </button>
      </div>

      {/* Day names */}
      <div className="grid grid-cols-7 border-b border-gray-800">
        {dayNames.map((day) => (
          <div
            key={day}
            className="px-2 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7">
        {calendarDays.map((day, index) => {
          const dayEvents = day ? getEventsForDay(day) : []
          const today = day && isToday(day)

          return (
            <div
              key={index}
              className={cn(
                'min-h-[120px] p-2 border-b border-r border-gray-800/50',
                day ? 'bg-gray-900/30' : 'bg-gray-950/50',
                today && 'bg-blue-500/10'
              )}
            >
              {day && (
                <>
                  <div
                    className={cn(
                      'text-sm font-medium mb-1',
                      today ? 'text-blue-400' : 'text-gray-400'
                    )}
                  >
                    <span
                      className={cn(
                        'inline-flex items-center justify-center w-7 h-7 rounded-full',
                        today && 'bg-blue-500 text-white'
                      )}
                    >
                      {day}
                    </span>
                  </div>
                  <div className="space-y-1">
                    {dayEvents.slice(0, 3).map((event) => (
                      <button
                        key={event.id}
                        onClick={() => onEventClick?.(event)}
                        className="w-full text-left px-2 py-1 rounded text-xs font-medium truncate transition-opacity hover:opacity-80"
                        style={{ backgroundColor: event.color + '30', color: event.color }}
                        title={event.name}
                      >
                        {event.name}
                      </button>
                    ))}
                    {dayEvents.length > 3 && (
                      <div className="text-xs text-gray-500 px-2">
                        +{dayEvents.length - 3} more
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="px-6 py-4 border-t border-gray-800">
        <div className="flex flex-wrap gap-4">
          {uniqueCategories.map((category) => {
            const event = events.find((e) => e.category === category)
            return (
              <div key={category} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: event?.color || '#6b7280' }}
                />
                <span className="text-xs text-gray-400">
                  {CATEGORY_LABELS[category] || category}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
