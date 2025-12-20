/**
 * Operations - Scheduled Tasks API
 * =================================
 * CEO Dashboard: Complete overview of all scheduled operations
 *
 * Sources:
 * 1. Windows Task Scheduler (FHQ_* tasks)
 * 2. Database task registry (fhq_governance.task_registry)
 * 3. Scheduled jobs (fhq_governance.scheduled_tasks)
 *
 * Authority: CEO Directive - Full operational visibility
 */

import { NextResponse } from 'next/server'
import { queryMany, queryOne } from '@/lib/db'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

interface WindowsTask {
  taskName: string
  status: string
  lastRunTime: string | null
  nextRunTime: string | null
  lastResult: string | null
  schedule: string | null
  source: 'WINDOWS_SCHEDULER'
}

interface DatabaseTask {
  taskName: string
  taskType: string
  status: string
  agentId: string | null
  description: string | null
  enabled: boolean
  lastRun: string | null
  nextRun: string | null
  source: 'DATABASE'
}

async function getWindowsScheduledTasks(): Promise<WindowsTask[]> {
  try {
    // PowerShell command to get FHQ scheduled tasks
    const cmd = `powershell -NoProfile -Command "Get-ScheduledTask -TaskName 'FHQ*' -ErrorAction SilentlyContinue | ForEach-Object { $info = $_ | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue; [PSCustomObject]@{ TaskName = $_.TaskName; State = $_.State; LastRunTime = $info.LastRunTime; NextRunTime = $info.NextRunTime; LastResult = $info.LastTaskResult; Trigger = ($_.Triggers | Select-Object -First 1).ToString() } } | ConvertTo-Json -Compress"`

    const { stdout } = await execAsync(cmd, { timeout: 10000 })

    if (!stdout.trim()) {
      return []
    }

    // Parse JSON - handle single object vs array
    let tasks = JSON.parse(stdout)
    if (!Array.isArray(tasks)) {
      tasks = [tasks]
    }

    return tasks.map((t: any) => {
      // Safely parse dates - handle PowerShell date format issues
      let lastRunTime: string | null = null
      let nextRunTime: string | null = null

      try {
        if (t.LastRunTime && typeof t.LastRunTime === 'string' && !t.LastRunTime.includes('1999')) {
          lastRunTime = new Date(t.LastRunTime).toISOString()
        }
      } catch { /* ignore invalid dates */ }

      try {
        if (t.NextRunTime && typeof t.NextRunTime === 'string') {
          nextRunTime = new Date(t.NextRunTime).toISOString()
        }
      } catch { /* ignore invalid dates */ }

      return {
        taskName: t.TaskName,
        status: t.State || 'Unknown',
        lastRunTime,
        nextRunTime,
        lastResult: t.LastResult === 0 ? 'SUCCESS' : t.LastResult === 1 ? 'ERROR' : String(t.LastResult),
        schedule: t.Trigger || null,
        source: 'WINDOWS_SCHEDULER' as const,
      }
    })
  } catch (error) {
    console.error('Error fetching Windows tasks:', error)
    return []
  }
}

async function getDatabaseTasks(): Promise<DatabaseTask[]> {
  try {
    const tasks = await queryMany<any>(`
      SELECT
        task_name,
        COALESCE(task_type, 'SCHEDULED_JOB') as task_type,
        status,
        agent_id,
        task_description as description,
        enabled,
        updated_at as last_run
      FROM fhq_governance.task_registry
      WHERE status IN ('ACTIVE', 'ENABLED', 'READY')
      OR enabled = true
      ORDER BY task_name
    `)

    return (tasks || []).map(t => ({
      taskName: t.task_name,
      taskType: t.task_type,
      status: t.status,
      agentId: t.agent_id,
      description: t.description,
      enabled: t.enabled,
      lastRun: t.last_run,
      nextRun: null,
      source: 'DATABASE' as const,
    }))
  } catch (error) {
    console.error('Error fetching database tasks:', error)
    return []
  }
}

async function getSystemHeartbeats(): Promise<any[]> {
  try {
    const heartbeats = await queryMany<any>(`
      SELECT
        component_name,
        heartbeat_type,
        last_heartbeat,
        status,
        metadata
      FROM fhq_governance.system_heartbeats
      WHERE last_heartbeat > NOW() - INTERVAL '24 hours'
      ORDER BY last_heartbeat DESC
    `)
    return heartbeats || []
  } catch (error) {
    console.error('Error fetching heartbeats:', error)
    return []
  }
}

async function getDataFreshness(): Promise<any> {
  // Simplified version - skip slow queries for now
  // TODO: Enable full freshness checks after database optimization
  return {
    price: { latestDate: null, daysStale: 0 },
    regime: { latestDate: null, daysStale: 0 },
  }
}

export async function GET() {
  try {
    // Fetch all data sources in parallel
    const [windowsTasks, databaseTasks, heartbeats, freshness] = await Promise.all([
      getWindowsScheduledTasks(),
      getDatabaseTasks(),
      getSystemHeartbeats(),
      getDataFreshness(),
    ])

    // Categorize Windows tasks
    const priceIngestTasks = windowsTasks.filter(t =>
      t.taskName.includes('IOS001') || t.taskName.includes('INGEST')
    )
    const regimeTasks = windowsTasks.filter(t =>
      t.taskName.includes('REGIME') || t.taskName.includes('HMM')
    )
    const otherWindowsTasks = windowsTasks.filter(t =>
      !priceIngestTasks.includes(t) && !regimeTasks.includes(t)
    )

    // Summary
    const summary = {
      totalWindowsTasks: windowsTasks.length,
      totalDatabaseTasks: databaseTasks.length,
      activeHeartbeats: heartbeats.length,
      priceDataStale: freshness.price.daysStale > 1,
      regimeDataStale: freshness.regime.daysStale > 1,
      lastUpdated: new Date().toISOString(),
    }

    return NextResponse.json({
      summary,
      freshness,
      windowsTasks: {
        priceIngest: priceIngestTasks,
        regime: regimeTasks,
        other: otherWindowsTasks,
      },
      databaseTasks,
      heartbeats,
    }, {
      headers: {
        'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
      },
    })
  } catch (error) {
    console.error('Error in operations API:', error)
    return NextResponse.json(
      { error: 'Failed to fetch operations data', details: String(error) },
      { status: 500 }
    )
  }
}
