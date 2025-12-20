/**
 * Scheduled Tasks API Route
 * Fetches task registry with scheduling information
 * Shows which tasks have schedules configured and which are missing
 */

import { NextResponse } from 'next/server'
import { queryMany } from '@/lib/db'

interface ScheduledTask {
  task_name: string
  task_type: string | null
  task_status: string
  owned_by_agent: string | null
  schedule_cron: string | null
  schedule_timezone: string | null
  schedule_description: string | null
  schedule_enabled: boolean
  last_scheduled_run: string | null
  next_scheduled_run: string | null
  run_count: number | null
  last_run_duration_ms: number | null
  last_run_status: string | null
}

export async function GET() {
  try {
    // Query fhq_governance.task_registry with actual column names
    const tasks = await queryMany<ScheduledTask>(`
      SELECT
        task_name,
        COALESCE(task_type, 'VISION_FUNCTION') as task_type,
        status as task_status,
        agent_id as owned_by_agent,
        NULL::text as schedule_cron,
        NULL::text as schedule_timezone,
        task_description as schedule_description,
        enabled as schedule_enabled,
        NULL::timestamp as last_scheduled_run,
        NULL::timestamp as next_scheduled_run,
        NULL::int as run_count,
        NULL::int as last_run_duration_ms,
        NULL::text as last_run_status
      FROM fhq_governance.task_registry
      WHERE status = 'ACTIVE' OR enabled = true
      ORDER BY
        enabled DESC,
        task_name
    `)

    // Separate scheduled and unscheduled tasks
    const scheduled = tasks?.filter(t => t.schedule_enabled) || []
    const unscheduled = tasks?.filter(t => !t.schedule_enabled && t.task_type === 'VISION_FUNCTION') || []
    const otherTasks = tasks?.filter(t => !t.schedule_enabled && t.task_type !== 'VISION_FUNCTION') || []

    // Calculate summary stats
    const summary = {
      total_active: tasks?.length || 0,
      scheduled_count: scheduled.length,
      unscheduled_vision_functions: unscheduled.length,
      other_tasks: otherTasks.length,
    }

    return NextResponse.json(
      {
        summary,
        scheduled,
        unscheduled,
        other_tasks: otherTasks
      },
      {
        headers: {
          'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=120',
        },
      }
    )
  } catch (error) {
    console.error('Error fetching scheduled tasks:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
