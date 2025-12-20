/**
 * Sandbox Page
 * Displays orchestrator configuration, scheduled tasks, and execution history
 * Authority: ADR-007 (Orchestrator Architecture)
 */

import { Suspense } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { queryMany, queryOne } from '@/lib/db'
import { Clock, Cpu, Activity, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'
import { HistoricalDataChart } from './HistoricalDataChart'

export const revalidate = 30 // Revalidate every 30 seconds

export default async function SandboxPage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-display">Sandbox</h1>
        <p className="mt-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Orchestrator configuration, scheduled tasks, and data pipelines
        </p>
      </div>

      {/* Orchestrator Status */}
      <Suspense fallback={<SkeletonCard />}>
        <OrchestratorStatusSection />
      </Suspense>

      {/* Historical Data Charts */}
      <HistoricalDataChart />

      {/* Task Registry by Category */}
      <Suspense fallback={<SkeletonCard />}>
        <TaskRegistrySection />
      </Suspense>

      {/* Recent Execution History */}
      <Suspense fallback={<SkeletonCard />}>
        <ExecutionHistorySection />
      </Suspense>
    </div>
  )
}

/**
 * Orchestrator Status Overview
 */
async function OrchestratorStatusSection() {
  const lastCycle = await queryOne<any>(`
    SELECT
      action_target as cycle_id,
      initiated_at,
      decision as status,
      decision_rationale
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'ORCHESTRATOR_CYCLE_COMPLETE'
    ORDER BY initiated_at DESC
    LIMIT 1
  `)

  const cycleCount = await queryOne<{ count: number }>(`
    SELECT COUNT(*) as count
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'ORCHESTRATOR_CYCLE_COMPLETE'
  `)

  const taskCount = await queryOne<{ count: number }>(`
    SELECT COUNT(*) as count
    FROM fhq_governance.task_registry
    WHERE (task_type = 'VISION_FUNCTION' OR task_type IS NULL) AND (status = 'ACTIVE' OR enabled = true)
  `)

  let cycleData = null
  if (lastCycle?.decision_rationale) {
    try {
      cycleData = JSON.parse(lastCycle.decision_rationale)
    } catch (e) {}
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Cpu className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>Orchestrator Status</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Version */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: 'hsl(var(--muted-foreground))' }}>Version</p>
            <p className="text-xl font-bold mt-1">v1.0.0</p>
            <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>LARS Orchestrator</p>
          </div>

          {/* Active Tasks */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: 'hsl(var(--muted-foreground))' }}>Active Tasks</p>
            <p className="text-xl font-bold mt-1">{taskCount?.count ?? 0}</p>
            <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>VISION_FUNCTION</p>
          </div>

          {/* Total Cycles */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: 'hsl(var(--muted-foreground))' }}>Total Cycles</p>
            <p className="text-xl font-bold mt-1">{cycleCount?.count ?? 0}</p>
            <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>Since deployment</p>
          </div>

          {/* Last Cycle */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
            <p className="text-xs uppercase tracking-wide" style={{ color: 'hsl(var(--muted-foreground))' }}>Last Cycle</p>
            <div className="mt-1">
              <StatusBadge
                variant={lastCycle?.status === 'COMPLETED' ? 'pass' : lastCycle?.status === 'COMPLETED_WITH_FAILURES' ? 'warning' : 'fail'}
              >
                {lastCycle?.status?.replace(/_/g, ' ') || 'N/A'}
              </StatusBadge>
            </div>
            <p className="text-xs mt-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
              {lastCycle?.initiated_at ? new Date(lastCycle.initiated_at).toLocaleString() : 'N/A'}
            </p>
          </div>
        </div>

        {/* Cycle Details */}
        {cycleData && (
          <div className="mt-6 pt-6" style={{ borderTop: '1px solid hsl(var(--border))' }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Last Cycle: {cycleData.cycle_id}</p>
                <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  {cycleData.success_count ?? 0} passed, {cycleData.failure_count ?? 0} failed
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>Interval:</span>
                <span className="text-sm font-medium">1 hour</span>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Task Registry by Agent and Schedule
 */
async function TaskRegistrySection() {
  const tasks = await queryMany<any>(`
    SELECT
      task_id,
      task_name,
      agent_id,
      COALESCE(task_description, description) as description,
      task_config as parameters_schema,
      COALESCE(status, CASE WHEN enabled THEN 'ACTIVE' ELSE 'INACTIVE' END) as task_status,
      created_at
    FROM fhq_governance.task_registry
    WHERE task_type = 'VISION_FUNCTION' OR task_type IS NULL
    ORDER BY agent_id, task_name
  `)

  // Group by agent
  const byAgent: Record<string, any[]> = {}
  tasks?.forEach(task => {
    const agent = task.agent_id || 'UNKNOWN'
    if (!byAgent[agent]) byAgent[agent] = []
    byAgent[agent].push(task)
  })

  const agentColors: Record<string, string> = {
    'LARS': 'hsl(217, 91%, 60%)',      // Blue
    'STIG': 'hsl(142, 76%, 36%)',      // Green
    'LINE': 'hsl(38, 92%, 50%)',       // Amber
    'FINN': 'hsl(280, 70%, 60%)',      // Purple
    'VEGA': 'hsl(0, 84%, 60%)',        // Red
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Activity className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>Task Registry</CardTitle>
        </div>
        <p className="text-sm mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
          {tasks?.length ?? 0} registered VISION_FUNCTION tasks grouped by agent
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {Object.entries(byAgent).map(([agent, agentTasks]) => (
            <div key={agent}>
              {/* Agent Header */}
              <div className="flex items-center gap-3 mb-3">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: agentColors[agent] || 'hsl(var(--muted-foreground))' }}
                />
                <h3 className="font-semibold">{agent}</h3>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    backgroundColor: 'hsl(var(--secondary))',
                    color: 'hsl(var(--muted-foreground))'
                  }}
                >
                  {agentTasks.length} tasks
                </span>
              </div>

              {/* Task List */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 ml-6">
                {agentTasks.map(task => {
                  const schedule = task.parameters_schema?.schedule || task.parameters_schema?.cron || 'on-demand'
                  const functionPath = task.parameters_schema?.function_path || 'N/A'

                  return (
                    <div
                      key={task.task_id}
                      className="p-3 rounded-lg border"
                      style={{
                        backgroundColor: 'hsl(var(--card))',
                        borderColor: 'hsl(var(--border))'
                      }}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{task.task_name}</p>
                          <p
                            className="text-xs mt-1 line-clamp-2"
                            style={{ color: 'hsl(var(--muted-foreground))' }}
                          >
                            {task.description}
                          </p>
                        </div>
                        <StatusBadge
                          variant={task.task_status === 'ACTIVE' ? 'pass' : 'stale'}
                        >
                          {task.task_status}
                        </StatusBadge>
                      </div>

                      <div className="mt-3 flex items-center gap-4 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        <div className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          <span>{schedule}</span>
                        </div>
                        <span className="truncate font-mono">{functionPath.split('/').pop()}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Recent Execution History
 */
async function ExecutionHistorySection() {
  const cycles = await queryMany<any>(`
    SELECT
      action_target as cycle_id,
      initiated_at,
      decision as status,
      decision_rationale
    FROM fhq_governance.governance_actions_log
    WHERE action_type = 'ORCHESTRATOR_CYCLE_COMPLETE'
    ORDER BY initiated_at DESC
    LIMIT 10
  `)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Clock className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>Recent Execution History</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {cycles && cycles.length > 0 ? (
          <div className="space-y-3">
            {cycles.map((cycle, idx) => {
              let data = null
              try {
                data = JSON.parse(cycle.decision_rationale)
              } catch (e) {}

              const successCount = data?.success_count ?? 0
              const failureCount = data?.failure_count ?? 0
              const totalTasks = data?.tasks_executed ?? 0

              return (
                <div
                  key={idx}
                  className="p-4 rounded-lg border"
                  style={{
                    backgroundColor: 'hsl(var(--secondary))',
                    borderColor: 'hsl(var(--border))'
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="font-medium text-sm">{cycle.cycle_id}</p>
                      <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        {new Date(cycle.initiated_at).toLocaleString()}
                      </p>
                    </div>
                    <StatusBadge
                      variant={
                        cycle.status === 'COMPLETED' ? 'pass' :
                        cycle.status === 'COMPLETED_WITH_FAILURES' ? 'warning' : 'fail'
                      }
                    >
                      {cycle.status?.replace(/_/g, ' ')}
                    </StatusBadge>
                  </div>

                  {data && (
                    <div className="mt-3 flex items-center gap-4">
                      <div className="flex items-center gap-1.5 text-sm">
                        <CheckCircle className="w-4 h-4 text-green-400" />
                        <span>{successCount} passed</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-sm">
                        <XCircle className="w-4 h-4 text-red-400" />
                        <span>{failureCount} failed</span>
                      </div>
                      <div
                        className="flex items-center gap-1.5 text-sm"
                        style={{ color: 'hsl(var(--muted-foreground))' }}
                      >
                        <span>{totalTasks} total tasks</span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <p style={{ color: 'hsl(var(--muted-foreground))' }}>No execution history available</p>
        )}
      </CardContent>
    </Card>
  )
}
