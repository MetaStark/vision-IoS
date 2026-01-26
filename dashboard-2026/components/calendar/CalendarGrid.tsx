/**
 * Calendar Grid Component - CEO-DIR-2026-CALENDAR-VISUAL-ENHANCEMENT
 *
 * Modern monthly grid with:
 * - Test period indicators with unique colors
 * - Start/End date markers
 * - Clean, contemporary design
 */

'use client'

import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight, Play, Flag } from 'lucide-react'
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

interface TestPeriod {
  id: string
  name: string
  startDate: string
  endDate: string
  color: string
}

interface CalendarGridProps {
  events: CalendarEvent[]
  testPeriods?: TestPeriod[]
  currentYear: number
  currentMonth: number
  onEventClick?: (event: CalendarEvent) => void
  onDayClick?: (day: number, month: number, year: number, events: CalendarEvent[]) => void
}

// Test colors matching CanonicalTestCard
const TEST_PERIOD_COLORS: Record<string, string> = {
  'EC-022': '#a78bfa',   // Violet - Reward Logic
  'Tier-1': '#60a5fa',   // Blue - Brutality Calibration
  'Golden': '#fbbf24',   // Gold - Golden Needles
  'FINN-T': '#34d399',   // Emerald - World Model
  'G1.5': '#f472b6',     // Pink - Calibration Freeze
}

function getTestColor(testName: string): string {
  if (testName.includes('Reward') || testName.includes('EC-022')) return TEST_PERIOD_COLORS['EC-022']
  if (testName.includes('Tier-1') || testName.includes('Brutality')) return TEST_PERIOD_COLORS['Tier-1']
  if (testName.includes('Golden') || testName.includes('Shadow')) return TEST_PERIOD_COLORS['Golden']
  if (testName.includes('FINN-T') || testName.includes('World-Model')) return TEST_PERIOD_COLORS['FINN-T']
  if (testName.includes('G1.5') || testName.includes('Calibration Freeze')) return TEST_PERIOD_COLORS['G1.5']
  return '#60a5fa'
}

export function CalendarGrid({
  events,
  testPeriods = [],
  currentYear,
  currentMonth,
  onEventClick,
  onDayClick,
}: CalendarGridProps) {
  const [viewYear, setViewYear] = useState(currentYear)
  const [viewMonth, setViewMonth] = useState(currentMonth)

  const monthNames = [
    'Januar', 'Februar', 'Mars', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Desember'
  ]

  const dayNames = ['Søn', 'Man', 'Tir', 'Ons', 'Tor', 'Fre', 'Lør']

  // Calculate calendar grid
  const calendarDays = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth - 1, 1)
    const lastDay = new Date(viewYear, viewMonth, 0)
    const startDayOfWeek = firstDay.getDay()
    const daysInMonth = lastDay.getDate()

    const days: (number | null)[] = []

    for (let i = 0; i < startDayOfWeek; i++) {
      days.push(null)
    }

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

  // Check if a day is within a test period
  const getTestPeriodsForDay = (day: number) => {
    const checkDate = new Date(viewYear, viewMonth - 1, day)
    return testPeriods.filter(period => {
      const start = new Date(period.startDate)
      const end = new Date(period.endDate)
      return checkDate >= start && checkDate <= end
    })
  }

  // Check if day is start or end of a test
  const isTestStart = (day: number) => {
    const checkDate = new Date(viewYear, viewMonth - 1, day).toDateString()
    return testPeriods.filter(p => new Date(p.startDate).toDateString() === checkDate)
  }

  const isTestEnd = (day: number) => {
    const checkDate = new Date(viewYear, viewMonth - 1, day).toDateString()
    return testPeriods.filter(p => new Date(p.endDate).toDateString() === checkDate)
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

  return (
    <div className="bg-gray-900/50 border border-gray-800 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between bg-gradient-to-r from-gray-900 to-gray-800">
        <div className="flex items-center gap-4">
          <button
            onClick={goToPreviousMonth}
            className="p-2 hover:bg-gray-700 rounded-lg transition-all hover:scale-105"
          >
            <ChevronLeft className="h-5 w-5 text-gray-400" />
          </button>
          <h2 className="text-xl font-bold text-white min-w-[200px] text-center">
            {monthNames[viewMonth - 1]} {viewYear}
          </h2>
          <button
            onClick={goToNextMonth}
            className="p-2 hover:bg-gray-700 rounded-lg transition-all hover:scale-105"
          >
            <ChevronRight className="h-5 w-5 text-gray-400" />
          </button>
        </div>
        <button
          onClick={goToToday}
          className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg text-sm font-medium hover:bg-blue-500/30 transition-all hover:scale-105"
        >
          I dag
        </button>
      </div>

      {/* Test Period Legend */}
      {testPeriods.length > 0 && (
        <div className="px-6 py-3 border-b border-gray-800 bg-gray-900/50">
          <div className="flex flex-wrap gap-4">
            {testPeriods.map((period) => (
              <div key={period.id} className="flex items-center gap-2">
                <div
                  className="w-4 h-4 rounded-md animate-pulse"
                  style={{ backgroundColor: getTestColor(period.name) + '60' }}
                />
                <span className="text-xs text-gray-400">{period.name.split(' - ')[0]}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Day names */}
      <div className="grid grid-cols-7 border-b border-gray-800 bg-gray-900/30">
        {dayNames.map((day) => (
          <div
            key={day}
            className="px-2 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider"
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
          const periodsForDay = day ? getTestPeriodsForDay(day) : []
          const startingTests = day ? isTestStart(day) : []
          const endingTests = day ? isTestEnd(day) : []

          return (
            <div
              key={index}
              className={cn(
                'min-h-[120px] p-2 border-b border-r border-gray-800/50 relative transition-all',
                day ? 'bg-gray-900/30 hover:bg-gray-800/50' : 'bg-gray-950/50',
                today && 'ring-2 ring-blue-500/50 ring-inset'
              )}
            >
              {day && (
                <>
                  {/* Test period background strips */}
                  {periodsForDay.length > 0 && (
                    <div className="absolute inset-0 pointer-events-none">
                      {periodsForDay.map((period, i) => (
                        <div
                          key={period.id}
                          className="absolute left-0 right-0"
                          style={{
                            top: `${85 + i * 4}%`,
                            height: '3px',
                            backgroundColor: getTestColor(period.name),
                            opacity: 0.6,
                          }}
                        />
                      ))}
                    </div>
                  )}

                  {/* Start marker */}
                  {startingTests.length > 0 && (
                    <div className="absolute top-1 left-1">
                      {startingTests.map((test, i) => (
                        <div
                          key={test.id}
                          className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold mb-0.5"
                          style={{
                            backgroundColor: getTestColor(test.name) + '30',
                            color: getTestColor(test.name),
                          }}
                        >
                          <Play className="h-2.5 w-2.5" />
                          START
                        </div>
                      ))}
                    </div>
                  )}

                  {/* End marker */}
                  {endingTests.length > 0 && (
                    <div className="absolute top-1 right-1">
                      {endingTests.map((test, i) => (
                        <div
                          key={test.id}
                          className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold mb-0.5"
                          style={{
                            backgroundColor: getTestColor(test.name) + '30',
                            color: getTestColor(test.name),
                          }}
                        >
                          <Flag className="h-2.5 w-2.5" />
                          SLUTT
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Day number */}
                  <div className={cn('text-sm font-medium mb-1', today ? 'text-blue-400' : 'text-gray-400')}>
                    <button
                      onClick={() => onDayClick?.(day, viewMonth, viewYear, dayEvents)}
                      className={cn(
                        'inline-flex items-center justify-center w-8 h-8 rounded-full transition-all',
                        today && 'bg-blue-500 text-white font-bold shadow-lg shadow-blue-500/30',
                        !today && 'hover:bg-gray-700'
                      )}
                    >
                      {day}
                    </button>
                  </div>

                  {/* Events */}
                  <div className="space-y-1 mt-6">
                    {dayEvents.slice(0, 2).map((event) => (
                      <button
                        key={event.id}
                        onClick={() => onEventClick?.(event)}
                        className="w-full text-left px-2 py-1 rounded-md text-xs font-medium truncate transition-all hover:scale-105"
                        style={{
                          backgroundColor: event.color + '25',
                          color: event.color,
                          borderLeft: `2px solid ${event.color}`,
                        }}
                        title={event.name}
                      >
                        {event.name}
                      </button>
                    ))}
                    {dayEvents.length > 2 && (
                      <button
                        onClick={() => onDayClick?.(day, viewMonth, viewYear, dayEvents)}
                        className="text-xs text-blue-400 px-2 hover:text-blue-300 transition-colors"
                      >
                        +{dayEvents.length - 2} flere
                      </button>
                    )}
                  </div>
                </>
              )}
            </div>
          )
        })}
      </div>

      {/* Footer legend */}
      <div className="px-6 py-4 border-t border-gray-800 bg-gray-900/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span className="text-xs text-gray-400">I dag</span>
            </div>
            <div className="flex items-center gap-2">
              <Play className="h-3 w-3 text-green-400" />
              <span className="text-xs text-gray-400">Test start</span>
            </div>
            <div className="flex items-center gap-2">
              <Flag className="h-3 w-3 text-red-400" />
              <span className="text-xs text-gray-400">Test slutt</span>
            </div>
          </div>
          <span className="text-xs text-gray-600">
            Fargede linjer = aktive testperioder
          </span>
        </div>
      </div>
    </div>
  )
}
