/**
 * Metacognitive Observability - Audit-Hardening Status API
 *
 * Authority: CEO Directive Metacognitive Observability & Audit-Hardening
 * Classification: CONSTITUTIONAL - G4+ Compliance
 *
 * Provides:
 * - Hash chain integrity status
 * - Court-proof evidence coverage
 * - Boundary violation tracking
 * - DEFCON system state
 * - Overall audit health score
 */

import { NextResponse } from 'next/server'
import { queryOne, queryMany } from '@/lib/db'

export const revalidate = 5 // 5-second polling (critical monitoring)

interface AuditStatus {
  hash_chain_checks_24h: number
  hash_chain_valid: number
  hash_chain_integrity_pct: number
  last_chain_check: string | null
  summaries_7d: number
  summaries_with_query: number
  court_proof_coverage_pct: number
  last_evidence: string | null
  boundary_checks_30d: number
  boundary_violations: number
  last_validation: string | null
  current_defcon: string
  defcon_updated_at: string | null
  audit_health_score: number
}

interface CircuitBreakerEvent {
  event_id: string
  breaker_name: string
  event_type: string
  defcon_before: string
  defcon_after: string
  triggered_at: string
}

export async function GET() {
  try {
    // Get main audit status
    const auditStatus = await queryOne<AuditStatus>(`
      SELECT * FROM fhq_governance.v_audit_hardening_status
    `)

    // Get recent circuit breaker events
    const circuitBreakerEvents = await queryMany<CircuitBreakerEvent>(`
      SELECT
        event_id::text,
        breaker_name,
        event_type,
        defcon_before::text,
        defcon_after::text,
        event_timestamp::text as triggered_at
      FROM fhq_governance.circuit_breaker_events
      WHERE event_timestamp >= NOW() - INTERVAL '24 hours'
      ORDER BY event_timestamp DESC
      LIMIT 10
    `)

    // Get evidence verification log (recent)
    const recentVerifications = await queryMany<{
      verification_id: string
      summary_type: string
      verification_result: string
      verified_at: string
    }>(`
      SELECT
        verification_id::text,
        COALESCE(verified_by, 'SYSTEM') as summary_type,
        CASE WHEN verification_result THEN 'VALID' ELSE 'INVALID' END as verification_result,
        verified_at::text
      FROM vision_verification.evidence_verification_log
      WHERE verified_at >= NOW() - INTERVAL '24 hours'
      ORDER BY verified_at DESC
      LIMIT 10
    `)

    // Determine health indicators (handle string numbers from Postgres)
    const hashIntegrity = parseFloat(String(auditStatus?.hash_chain_integrity_pct || 0))
    const courtProof = parseFloat(String(auditStatus?.court_proof_coverage_pct || 0))
    const violations = parseInt(String(auditStatus?.boundary_violations || 0))

    const healthIndicators = {
      hash_chain: hashIntegrity >= 100 ? 'PASS' : hashIntegrity >= 95 ? 'WARN' : 'FAIL',
      court_proof: courtProof >= 100 ? 'PASS' : courtProof >= 95 ? 'WARN' : 'FAIL',
      boundary: violations === 0 ? 'PASS' : violations < 5 ? 'WARN' : 'FAIL',
      defcon: auditStatus?.current_defcon === 'GREEN' ? 'PASS' :
              auditStatus?.current_defcon === 'YELLOW' ? 'WARN' : 'FAIL'
    }

    // Overall status
    const overallStatus = Object.values(healthIndicators).every(h => h === 'PASS') ? 'ALL_CLEAR' :
                          Object.values(healthIndicators).some(h => h === 'FAIL') ? 'CRITICAL' : 'WARNING'

    return NextResponse.json({
      overall_status: overallStatus,
      audit_health_score: auditStatus?.audit_health_score || 100,
      health_indicators: healthIndicators,
      metrics: {
        hash_chain: {
          checks_24h: auditStatus?.hash_chain_checks_24h || 0,
          valid: auditStatus?.hash_chain_valid || 0,
          integrity_pct: auditStatus?.hash_chain_integrity_pct || 100,
          last_check: auditStatus?.last_chain_check || null
        },
        court_proof: {
          summaries_7d: auditStatus?.summaries_7d || 0,
          with_raw_query: auditStatus?.summaries_with_query || 0,
          coverage_pct: auditStatus?.court_proof_coverage_pct || 100,
          last_evidence: auditStatus?.last_evidence || null
        },
        boundary: {
          checks_30d: auditStatus?.boundary_checks_30d || 0,
          violations: auditStatus?.boundary_violations || 0,
          last_validation: auditStatus?.last_validation || null
        },
        system: {
          defcon: auditStatus?.current_defcon || 'GREEN',
          defcon_updated: auditStatus?.defcon_updated_at || null
        }
      },
      recent_circuit_breaker_events: circuitBreakerEvents,
      recent_verifications: recentVerifications,
      _meta: {
        source_view: 'fhq_governance.v_audit_hardening_status',
        authority: 'CEO Directive Metacognitive Observability',
        adr_references: ['ADR-011', 'ADR-016'],
        fetched_at: new Date().toISOString()
      }
    })
  } catch (error) {
    console.error('[METACOGNITIVE/AUDIT-STATUS] Error:', error)
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Unknown error',
        overall_status: 'ERROR',
        audit_health_score: 0
      },
      { status: 500 }
    )
  }
}
