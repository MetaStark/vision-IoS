/**
 * Vision-OS Dashboard Page
 * CEO Oracle Channel, Narrative Vectors, and System State
 * Authority: ADR-019, IoS-009
 */

import { Suspense } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { queryMany, queryOne } from '@/lib/db'
import { Brain, Eye, Shield, Clock, Zap, MessageSquare } from 'lucide-react'

export const revalidate = 10 // Revalidate every 10 seconds

export default async function VisionOSPage() {
  return (
    <div className="space-y-8 fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-display">Vision-OS</h1>
        <p className="mt-2" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Human Oracle Channel, System State, and Governance Overview
        </p>
      </div>

      {/* System Roles Status */}
      <Suspense fallback={<SkeletonCard />}>
        <SystemRolesSection />
      </Suspense>

      {/* Active Narrative Vectors */}
      <Suspense fallback={<SkeletonCard />}>
        <NarrativeVectorsSection />
      </Suspense>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* IoS Registry */}
        <Suspense fallback={<SkeletonCard />}>
          <IoSRegistrySection />
        </Suspense>

        {/* ADR Registry */}
        <Suspense fallback={<SkeletonCard />}>
          <ADRRegistrySection />
        </Suspense>
      </div>

      {/* Recent Governance Actions */}
      <Suspense fallback={<SkeletonCard />}>
        <GovernanceActionsSection />
      </Suspense>
    </div>
  )
}

/**
 * System Roles Overview
 */
async function SystemRolesSection() {
  // Check if roles exist
  const roles = await queryMany<any>(`
    SELECT rolname, rolcanlogin, rolsuper
    FROM pg_roles
    WHERE rolname IN ('ceo_read_only', 'stig_write_engine')
  `)

  const ceoRole = roles?.find(r => r.rolname === 'ceo_read_only')
  const stigRole = roles?.find(r => r.rolname === 'stig_write_engine')

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>System Roles (ADR-019)</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* CEO Read-Only Role */}
          <div className="p-4 rounded-lg border" style={{ borderColor: 'hsl(var(--border))' }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4" style={{ color: 'hsl(var(--primary))' }} />
                <span className="font-semibold">ceo_read_only</span>
              </div>
              <StatusBadge variant={ceoRole ? 'pass' : 'fail'}>
                {ceoRole ? 'ACTIVE' : 'MISSING'}
              </StatusBadge>
            </div>
            <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Zero-risk God-View. SELECT-only access to all schemas. Cannot modify any data.
            </p>
            <div className="mt-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Used by: VisionChat, Claude Inquiry
            </div>
          </div>

          {/* STIG Write Engine Role */}
          <div className="p-4 rounded-lg border" style={{ borderColor: 'hsl(var(--border))' }}>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4" style={{ color: 'hsl(142, 76%, 36%)' }} />
                <span className="font-semibold">stig_write_engine</span>
              </div>
              <StatusBadge variant={stigRole ? 'pass' : 'fail'}>
                {stigRole ? 'ACTIVE' : 'MISSING'}
              </StatusBadge>
            </div>
            <p className="text-sm" style={{ color: 'hsl(var(--muted-foreground))' }}>
              DML-only engineering access. No DDL. Governance tables append-only. Execution plane sealed.
            </p>
            <div className="mt-3 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
              Used by: STIG Engineering API
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Active Narrative Vectors (Human Oracle Channel)
 */
async function NarrativeVectorsSection() {
  const vectors = await queryMany<any>(`
    SELECT
      vector_id,
      domain,
      narrative,
      probability,
      confidence,
      half_life_hours,
      created_at,
      created_by,
      POWER(0.5, EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 / half_life_hours) AS current_weight
    FROM fhq_meta.narrative_vectors
    WHERE is_expired = FALSE
      AND EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 < (half_life_hours * 6.64)
    ORDER BY created_at DESC
    LIMIT 10
  `)

  const domainColors: Record<string, string> = {
    'Regulatory': 'hsl(0, 84%, 60%)',
    'Geopolitical': 'hsl(217, 91%, 60%)',
    'Liquidity': 'hsl(142, 76%, 36%)',
    'Reflexivity': 'hsl(280, 70%, 60%)',
    'Sentiment': 'hsl(38, 92%, 50%)',
    'Other': 'hsl(var(--muted-foreground))',
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <MessageSquare className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>Active Narrative Vectors (IoS-009 G1)</CardTitle>
        </div>
        <p className="text-sm mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
          Human Oracle inputs with half-life decay. Source: fhq_meta.narrative_vectors
        </p>
      </CardHeader>
      <CardContent>
        {vectors && vectors.length > 0 ? (
          <div className="space-y-4">
            {vectors.map((v: any) => {
              const weight = parseFloat(v.current_weight) * 100
              const ageHours = (Date.now() - new Date(v.created_at).getTime()) / (1000 * 60 * 60)

              return (
                <div
                  key={v.vector_id}
                  className="p-4 rounded-lg border"
                  style={{ borderColor: 'hsl(var(--border))' }}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: domainColors[v.domain] || domainColors['Other'] }}
                      />
                      <span className="text-xs font-medium uppercase">{v.domain}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                        Weight: {weight.toFixed(1)}%
                      </span>
                      <StatusBadge variant={weight > 50 ? 'pass' : weight > 20 ? 'warning' : 'stale'}>
                        {weight > 50 ? 'STRONG' : weight > 20 ? 'DECAYING' : 'WEAK'}
                      </StatusBadge>
                    </div>
                  </div>

                  <p className="text-sm mb-3">{v.narrative}</p>

                  <div className="grid grid-cols-4 gap-4 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    <div>
                      <span className="block">Probability</span>
                      <span className="font-mono font-medium">{(parseFloat(v.probability) * 100).toFixed(0)}%</span>
                    </div>
                    <div>
                      <span className="block">Confidence</span>
                      <span className="font-mono font-medium">{(parseFloat(v.confidence) * 100).toFixed(0)}%</span>
                    </div>
                    <div>
                      <span className="block">Half-Life</span>
                      <span className="font-mono font-medium">{v.half_life_hours}h</span>
                    </div>
                    <div>
                      <span className="block">Age</span>
                      <span className="font-mono font-medium">{ageHours.toFixed(1)}h</span>
                    </div>
                  </div>

                  {/* Decay Progress Bar */}
                  <div className="mt-3">
                    <div className="h-1.5 rounded-full" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${weight}%`,
                          backgroundColor: weight > 50 ? 'hsl(142, 76%, 36%)' : weight > 20 ? 'hsl(38, 92%, 50%)' : 'hsl(0, 84%, 60%)'
                        }}
                      />
                    </div>
                  </div>

                  <div className="mt-2 text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    Created by {v.created_by} at {new Date(v.created_at).toLocaleString()}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p style={{ color: 'hsl(var(--muted-foreground))' }}>
            No active narrative vectors. Use <code>fhq_meta.submit_narrative_vector()</code> to add human oracle inputs.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * IoS Registry Section
 */
async function IoSRegistrySection() {
  const iosModules = await queryMany<any>(`
    SELECT
      ios_id,
      title,
      version,
      status,
      owner_role
    FROM fhq_meta.ios_registry
    ORDER BY ios_id
    LIMIT 15
  `)

  const statusColors: Record<string, 'pass' | 'warning' | 'info' | 'stale'> = {
    'G4_CONSTITUTIONAL': 'pass',
    'G3_COMPLETE': 'pass',
    'G2_VALIDATED': 'info',
    'G1_TECHNICAL': 'warning',
    'G0_SUBMITTED': 'stale',
    'ACTIVE': 'pass',
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Brain className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>IoS Registry</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {iosModules?.map((ios: any) => (
            <div
              key={ios.ios_id}
              className="flex items-center justify-between p-3 rounded-lg"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium">{ios.ios_id}</span>
                  <span className="text-xs" style={{ color: 'hsl(var(--muted-foreground))' }}>
                    {ios.version}
                  </span>
                </div>
                <p className="text-xs truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  {ios.title}
                </p>
              </div>
              <StatusBadge variant={statusColors[ios.status] || 'info'}>
                {ios.status}
              </StatusBadge>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * ADR Registry Section
 */
async function ADRRegistrySection() {
  const adrs = await queryMany<any>(`
    SELECT
      adr_id,
      COALESCE(title, adr_title) as title,
      COALESCE(version, current_version) as version,
      COALESCE(status, adr_status) as status,
      governance_tier as tier
    FROM fhq_meta.adr_registry
    ORDER BY adr_id
    LIMIT 20
  `)

  const tierColors: Record<string, string> = {
    'TIER-1': 'hsl(0, 84%, 60%)',
    'TIER-2': 'hsl(38, 92%, 50%)',
    'TIER-3': 'hsl(217, 91%, 60%)',
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Shield className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>ADR Registry</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {adrs?.map((adr: any) => (
            <div
              key={adr.adr_id}
              className="flex items-center justify-between p-3 rounded-lg"
              style={{ backgroundColor: 'hsl(var(--secondary))' }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium">{adr.adr_id}</span>
                  <div
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: tierColors[adr.tier] || 'hsl(var(--muted-foreground))' }}
                    title={adr.tier}
                  />
                </div>
                <p className="text-xs truncate" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  {adr.title}
                </p>
              </div>
              <StatusBadge variant={adr.status === 'ACTIVE' ? 'pass' : 'info'}>
                {adr.status}
              </StatusBadge>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Recent Governance Actions
 */
async function GovernanceActionsSection() {
  const actions = await queryMany<any>(`
    SELECT
      action_id,
      action_type,
      action_target,
      initiated_by,
      initiated_at,
      decision
    FROM fhq_governance.governance_actions_log
    ORDER BY initiated_at DESC
    LIMIT 10
  `)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Clock className="w-5 h-5" style={{ color: 'hsl(var(--primary))' }} />
          <CardTitle>Recent Governance Actions</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {actions?.map((action: any) => (
            <div
              key={action.action_id}
              className="flex items-center justify-between p-3 rounded-lg border"
              style={{ borderColor: 'hsl(var(--border))' }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{action.action_type}</span>
                  <span className="text-xs px-2 py-0.5 rounded" style={{ backgroundColor: 'hsl(var(--secondary))' }}>
                    {action.initiated_by}
                  </span>
                </div>
                <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  Target: {action.action_target}
                </p>
              </div>
              <div className="text-right">
                <StatusBadge variant={action.decision === 'APPROVED' ? 'pass' : action.decision === 'REJECTED' ? 'fail' : 'info'}>
                  {action.decision}
                </StatusBadge>
                <p className="text-xs mt-1" style={{ color: 'hsl(var(--muted-foreground))' }}>
                  {new Date(action.initiated_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
