'use client'

/**
 * Operations Dashboard
 * ====================
 * CEO Directive: Full visibility into all scheduled operations
 *
 * Shows:
 * - Windows Task Scheduler tasks (FHQ_*)
 * - Database scheduled tasks
 * - Data freshness status
 * - System heartbeats
 */

import { useEffect, useState } from 'react'
import {
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Calendar,
  Database,
  Server,
  Activity,
  Cpu
} from 'lucide-react'

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

interface OperationsData {
  summary: {
    totalWindowsTasks: number
    totalDatabaseTasks: number
    activeHeartbeats: number
    priceDataStale: boolean
    regimeDataStale: boolean
    lastUpdated: string
  }
  freshness: {
    price: { latestDate: string; daysStale: number }
    regime: { latestDate: string; daysStale: number }
  }
  windowsTasks: {
    priceIngest: WindowsTask[]
    regime: WindowsTask[]
    other: WindowsTask[]
  }
  databaseTasks: DatabaseTask[]
  heartbeats: any[]
}

function StatusBadge({ status }: { status: string }) {
  const isGood = ['Ready', 'SUCCESS', 'ACTIVE', 'Running', '0'].includes(status)
  const isError = ['ERROR', 'FAILED', '1', 'Disabled'].includes(status)

  return (
    <span className={`px-2 py-1 rounded text-xs font-medium ${
      isGood ? 'bg-green-500/20 text-green-400' :
      isError ? 'bg-red-500/20 text-red-400' :
      'bg-yellow-500/20 text-yellow-400'
    }`}>
      {status}
    </span>
  )
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('nb-NO', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

function TaskCard({
  title,
  icon: Icon,
  tasks,
  type
}: {
  title: string
  icon: any
  tasks: (WindowsTask | DatabaseTask)[]
  type: 'windows' | 'database'
}) {
  return (
    <div className="bg-[hsl(var(--card))] border border-[hsl(var(--border))] rounded-lg p-4">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-5 h-5 text-[hsl(var(--primary))]" />
        <h3 className="font-semibold text-[hsl(var(--foreground))]">{title}</h3>
        <span className="ml-auto text-xs bg-[hsl(var(--secondary))] px-2 py-1 rounded">
          {tasks.length} tasks
        </span>
      </div>

      <div className="space-y-2">
        {tasks.length === 0 ? (
          <p className="text-sm text-[hsl(var(--muted-foreground))]">No tasks found</p>
        ) : (
          tasks.map((task, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between p-3 bg-[hsl(var(--secondary))] rounded-lg"
            >
              <div className="flex-1">
                <p className="font-mono text-sm text-[hsl(var(--foreground))]">
                  {task.taskName}
                </p>
                {type === 'windows' && (task as WindowsTask).schedule && (
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {(task as WindowsTask).schedule}
                  </p>
                )}
                {type === 'database' && (task as DatabaseTask).description && (
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {(task as DatabaseTask).description}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs">
                {type === 'windows' && (
                  <>
                    <div className="text-right">
                      <p className="text-[hsl(var(--muted-foreground))]">Last Run</p>
                      <p className="text-[hsl(var(--foreground))]">
                        {formatDate((task as WindowsTask).lastRunTime)}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-[hsl(var(--muted-foreground))]">Next Run</p>
                      <p className="text-[hsl(var(--foreground))]">
                        {formatDate((task as WindowsTask).nextRunTime)}
                      </p>
                    </div>
                  </>
                )}
                <StatusBadge status={
                  type === 'windows'
                    ? (task as WindowsTask).lastResult || task.status
                    : task.status
                } />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default function OperationsPage() {
  const [data, setData] = useState<OperationsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function fetchData() {
    setLoading(true)
    try {
      const res = await fetch('/api/operations/scheduled-tasks')
      if (!res.ok) throw new Error('Failed to fetch')
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (err) {
      setError(String(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 animate-spin text-[hsl(var(--primary))]" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">
            Operations Center
          </h1>
          <p className="text-[hsl(var(--muted-foreground))]">
            CEO Dashboard - All Scheduled Operations
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-[hsl(var(--primary))] text-white rounded-lg hover:opacity-90 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-500/20 border border-red-500 text-red-400 p-4 rounded-lg">
          {error}
        </div>
      )}

      {data && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Price Data Freshness */}
            <div className={`p-4 rounded-lg border ${
              data.freshness.price.daysStale > 1
                ? 'bg-red-500/10 border-red-500'
                : 'bg-green-500/10 border-green-500'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Database className="w-5 h-5" />
                <span className="font-semibold">Price Data</span>
              </div>
              <p className="text-2xl font-bold">
                {data.freshness.price.daysStale} days old
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Latest: {data.freshness.price.latestDate || 'N/A'}
              </p>
            </div>

            {/* Regime Freshness */}
            <div className={`p-4 rounded-lg border ${
              data.freshness.regime.daysStale > 1
                ? 'bg-red-500/10 border-red-500'
                : 'bg-green-500/10 border-green-500'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-5 h-5" />
                <span className="font-semibold">Regime Data</span>
              </div>
              <p className="text-2xl font-bold">
                {data.freshness.regime.daysStale} days old
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Latest: {data.freshness.regime.latestDate || 'N/A'}
              </p>
            </div>

            {/* Windows Tasks */}
            <div className="p-4 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
              <div className="flex items-center gap-2 mb-2">
                <Server className="w-5 h-5 text-blue-400" />
                <span className="font-semibold">Windows Tasks</span>
              </div>
              <p className="text-2xl font-bold">{data.summary.totalWindowsTasks}</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Scheduled in Task Scheduler
              </p>
            </div>

            {/* Database Tasks */}
            <div className="p-4 rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
              <div className="flex items-center gap-2 mb-2">
                <Cpu className="w-5 h-5 text-purple-400" />
                <span className="font-semibold">Database Tasks</span>
              </div>
              <p className="text-2xl font-bold">{data.summary.totalDatabaseTasks}</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                Registered in task_registry
              </p>
            </div>
          </div>

          {/* Windows Scheduled Tasks */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TaskCard
              title="Price Ingest (IoS-001)"
              icon={Database}
              tasks={data.windowsTasks.priceIngest}
              type="windows"
            />
            <TaskCard
              title="Regime Updates (IoS-003)"
              icon={Activity}
              tasks={data.windowsTasks.regime}
              type="windows"
            />
          </div>

          {/* Other Windows Tasks */}
          {data.windowsTasks.other.length > 0 && (
            <TaskCard
              title="Other Scheduled Tasks"
              icon={Calendar}
              tasks={data.windowsTasks.other}
              type="windows"
            />
          )}

          {/* Database Tasks */}
          {data.databaseTasks.length > 0 && (
            <TaskCard
              title="Database Task Registry"
              icon={Cpu}
              tasks={data.databaseTasks}
              type="database"
            />
          )}

          {/* Last Updated */}
          <div className="text-center text-xs text-[hsl(var(--muted-foreground))]">
            Last updated: {new Date(data.summary.lastUpdated).toLocaleString('nb-NO')}
          </div>
        </>
      )}
    </div>
  )
}
