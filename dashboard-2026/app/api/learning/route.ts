/**
 * Learning Dashboard API - CEO-DIR-2026-057, 058, 059, 060
 * Provides REAL data from database views for the Learning Observability Dashboard
 *
 * CEO-DIR-2026-058 UPDATE:
 * Now returns DUAL metrics:
 * - System Maturity (FMCL, safety, governance)
 * - Market Learning (holdout performance - starts at 0%)
 *
 * CEO-DIR-2026-060 UPDATE:
 * Now returns Time Integrity status:
 * - Artifact validity counts (valid, invalid, pre-canonical)
 * - Blocking status for learning/reporting/QG-F6
 */

import { NextResponse } from 'next/server'
import { Pool } from 'pg'

// Direct PostgreSQL connection
const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
})

export async function GET() {
  let client
  try {
    client = await pool.connect()

    // Fetch learning progress
    const progressResult = await client.query(`
      SELECT * FROM fhq_governance.v_learning_progress
    `)
    const progress = progressResult.rows[0]

    // Fetch daily delta
    const deltaResult = await client.query(`
      SELECT * FROM fhq_governance.v_daily_learning_delta
    `)
    const dailyDelta = deltaResult.rows

    // Fetch cognitive activity
    const activityResult = await client.query(`
      SELECT * FROM fhq_governance.v_cognitive_activity
    `)
    const activity = activityResult.rows[0]

    // Fetch learning mechanisms
    const mechanismResult = await client.query(`
      SELECT * FROM fhq_governance.learning_mechanism_log
      ORDER BY logged_at DESC
      LIMIT 5
    `)
    const mechanisms = mechanismResult.rows

    // CEO-DIR-2026-058: Fetch Market Learning status (separate from System Maturity)
    const marketLearningResult = await client.query(`
      SELECT * FROM fhq_governance.v_market_learning_status
    `)
    const marketLearning = marketLearningResult.rows[0]

    // CEO-DIR-2026-059: Fetch Evidence Clock (canonical time + data availability)
    const evidenceClockResult = await client.query(`
      SELECT * FROM fhq_governance.v_evidence_clock
    `)
    const evidenceClock = evidenceClockResult.rows[0]

    // CEO-DIR-2026-060: Fetch Time Integrity status
    const timeIntegrityResult = await client.query(`
      SELECT * FROM fhq_governance.v_time_integrity_status
    `)
    const timeIntegrity = timeIntegrityResult.rows[0]

    // CEO-DIR-2026-LEARNING-OBSERVABILITY: Research Trinity metrics
    let researchTrinity = null
    try {
      const trinityResult = await client.query(`
        SELECT * FROM fhq_learning.v_learning_throughput_status
      `)
      if (trinityResult.rows[0]) {
        const t = trinityResult.rows[0]
        researchTrinity = {
          finnE: { count: parseInt(t.finn_e_count) || 0, share: parseFloat(t.finn_e_count) / Math.max(parseInt(t.total_hypotheses) || 1, 1) },
          finnT: { count: parseInt(t.finn_t_count) || 0, share: parseFloat(t.finn_t_count) / Math.max(parseInt(t.total_hypotheses) || 1, 1) },
          gnS: { count: parseInt(t.gn_s_count) || 0, share: parseFloat(t.gn_s_count) / Math.max(parseInt(t.total_hypotheses) || 1, 1) },
          totalHypotheses: parseInt(t.total_hypotheses) || 0,
          tier1DeathRate: parseFloat(t.tier1_death_rate) || 0,
          errorConversionRate: parseFloat(t.error_to_hypothesis_rate) || 0,
          avgCausalDepth: parseFloat(t.avg_causal_depth) || 0,
          learningHealth: t.learning_health || 'RED',
        }
      }
    } catch (e) {
      console.warn('Research Trinity view not available:', e)
    }

    // CEO-DIR-2026-DAY25-LEARNING-VISIBILITY-002: Four-Plane Learning Data
    let fourPlanes = null
    try {
      // PLANE 1: Learning Permission (MIC-aware from fn_get_learnable_asset_classes)
      const permissionResult = await client.query(`
        SELECT * FROM fhq_learning.fn_get_learnable_asset_classes()
      `)
      const permissionRows = permissionResult.rows

      // PLANE 2: Learning Engine Status (daemon health + scheduler)
      const engineResult = await client.query(`
        SELECT
          daemon_name, status, staleness_seconds, last_heartbeat
        FROM fhq_governance.daemon_health
        WHERE daemon_name IN ('finn_scheduler', 'cnrp_orchestrator', 'price_freshness_heartbeat')
        ORDER BY daemon_name
      `)
      const finnScheduler = engineResult.rows.find(r => r.daemon_name === 'finn_scheduler')
      const cnrpOrchestrator = engineResult.rows.find(r => r.daemon_name === 'cnrp_orchestrator')

      // DEFCON check
      const defconResult = await client.query(`
        SELECT current_level FROM fhq_governance.defcon_status ORDER BY updated_at DESC LIMIT 1
      `)
      const defconLevel = defconResult.rows[0]?.current_level || 5

      // PLANE 3: Learning Quality (Tier-1 Death Rate)
      const qualityResult = await client.query(`
        SELECT
          COALESCE(death_rate_pct, 0) as death_rate_pct,
          COALESCE(total_evaluated, 0) as total_evaluated,
          COALESCE(total_killed, 0) as total_killed
        FROM fhq_learning.v_tier1_death_rate_timeseries
        ORDER BY report_date DESC
        LIMIT 1
      `)
      const quality = qualityResult.rows[0]

      // PLANE 4: Learning Production (Generator Distribution - last 24h)
      const productionResult = await client.query(`
        SELECT
          COALESCE(finn_e_count, 0) as finn_e_count,
          COALESCE(finn_t_count, 0) as finn_t_count,
          COALESCE(gn_s_count, 0) as gn_s_count,
          COALESCE(total_count, 0) as total_count,
          COALESCE(finn_e_pct, 0) as finn_e_pct,
          COALESCE(finn_t_pct, 0) as finn_t_pct,
          COALESCE(gn_s_pct, 0) as gn_s_pct
        FROM fhq_learning.v_learning_generator_distribution
        ORDER BY report_date DESC
        LIMIT 1
      `)
      const production = productionResult.rows[0]

      // Construct four-plane response
      const cryptoRow = permissionRows.find(r => r.asset_class === 'CRYPTO')
      const equityRow = permissionRows.find(r => r.asset_class === 'US_EQUITY')
      const forexRow = permissionRows.find(r => r.asset_class === 'FOREX')

      // Determine engine status (PLANE 2 logic)
      let engineStatus = 'RUNNING'
      if (defconLevel <= 2) engineStatus = 'BLOCKED'
      else if (!finnScheduler || finnScheduler.status !== 'HEALTHY') engineStatus = 'STOPPED'
      else if (!cnrpOrchestrator || cnrpOrchestrator.status !== 'HEALTHY') engineStatus = 'PAUSED'

      // Determine quality status (PLANE 3 logic)
      const deathRate = quality ? parseFloat(quality.death_rate_pct) : 0
      let qualityStatus = 'NO_DATA'
      if (quality && parseInt(quality.total_evaluated) > 0) {
        if (deathRate >= 60 && deathRate <= 90) qualityStatus = 'ON_TARGET'
        else if (deathRate > 90) qualityStatus = 'TOO_BRUTAL'
        else qualityStatus = 'TOO_LENIENT'
      }

      fourPlanes = {
        permission: {
          permitted: permissionRows.some(r => r.is_learnable),
          assetClasses: {
            crypto: {
              permitted: cryptoRow?.is_learnable || false,
              learningOnly: true, // Always true per CEO-DIR-2026-CRYPTO-LEARNING-ACTIVATION-002
              reason: cryptoRow?.reason || 'Unknown'
            },
            equity: {
              permitted: equityRow?.is_learnable || false,
              learningOnly: false,
              reason: equityRow?.reason || 'Unknown'
            },
            forex: {
              permitted: forexRow?.is_learnable || false,
              learningOnly: false,
              reason: forexRow?.reason || 'Unknown'
            },
          },
          constraints: {
            allocationAllowed: false, // Per governance
            executionAllowed: false,
            decisionRights: false,
          },
        },
        engine: {
          schedulerRunning: finnScheduler?.status === 'HEALTHY',
          engineStatus,
          lastHeartbeat: finnScheduler?.last_heartbeat || null,
          staleness: finnScheduler?.staleness_seconds || null,
          defconLevel,
        },
        quality: {
          tier1DeathRate: deathRate,
          totalEvaluated: quality ? parseInt(quality.total_evaluated) : 0,
          totalKilled: quality ? parseInt(quality.total_killed) : 0,
          qualityStatus,
          targetMin: 60,
          targetMax: 90,
        },
        production: {
          finnE: {
            count: production ? parseInt(production.finn_e_count) : 0,
            pct: production ? parseFloat(production.finn_e_pct) : 0
          },
          finnT: {
            count: production ? parseInt(production.finn_t_count) : 0,
            pct: production ? parseFloat(production.finn_t_pct) : 0
          },
          gnS: {
            count: production ? parseInt(production.gn_s_count) : 0,
            pct: production ? parseFloat(production.gn_s_pct) : 0
          },
          total: production ? parseInt(production.total_count) : 0,
          dominant: production ? (
            parseFloat(production.finn_e_pct) >= parseFloat(production.finn_t_pct) &&
            parseFloat(production.finn_e_pct) >= parseFloat(production.gn_s_pct)
              ? 'FINN-E'
              : parseFloat(production.finn_t_pct) >= parseFloat(production.gn_s_pct)
                ? 'FINN-T'
                : 'GN-S'
          ) : null,
        },
        lastRefresh: new Date().toISOString(),
      }
    } catch (e) {
      console.warn('Four-Plane Learning data not available:', e)
    }

    // CEO-DIR-2026-DAY25-VISUAL-TRUTH: Learning Trajectory Time Series
    let learningTrajectory = null
    try {
      // Fetch all four time series views in parallel
      const [deathRateRes, conversionRes, generatorsRes, depthRes] = await Promise.all([
        client.query(`SELECT * FROM fhq_learning.v_tier1_death_rate_timeseries ORDER BY report_date`),
        client.query(`SELECT * FROM fhq_learning.v_error_to_hypothesis_conversion ORDER BY report_date`),
        client.query(`SELECT * FROM fhq_learning.v_learning_generator_distribution ORDER BY report_date`),
        client.query(`SELECT * FROM fhq_learning.v_hypothesis_causal_depth_timeseries ORDER BY report_date`),
      ])

      const deathRateRows = deathRateRes.rows
      const conversionRows = conversionRes.rows
      const generatorRows = generatorsRes.rows
      const depthRows = depthRes.rows

      // Get latest non-null values for current state
      const latestDeathRate = [...deathRateRows].reverse().find(r => r.death_rate_pct !== null)
      const latestConversion = [...conversionRows].reverse().find(r => r.conversion_rate_pct !== null)
      const latestGenerator = [...generatorRows].reverse().find(r => parseInt(r.total_count) > 0)
      const latestDepth = [...depthRows].reverse().find(r => parseFloat(r.avg_causal_depth) > 0)

      // Calculate day number (days since first hypothesis)
      const firstHypothesisDate = deathRateRows.find(r => parseInt(r.total_evaluated) > 0)?.report_date
      const dayNumber = firstHypothesisDate
        ? Math.ceil((Date.now() - new Date(firstHypothesisDate).getTime()) / (1000 * 60 * 60 * 24))
        : 1

      learningTrajectory = {
        deathRate: {
          timeSeries: deathRateRows.map(r => ({
            date: r.report_date,
            value: r.death_rate_pct !== null ? parseFloat(r.death_rate_pct) : null
          })),
          current: latestDeathRate ? parseFloat(latestDeathRate.death_rate_pct) : null,
          targetMin: 60,
          targetMax: 90,
          healthStatus: latestDeathRate?.health_status || 'NO DATA',
          dayNumber,
        },
        conversion: {
          timeSeries: conversionRows.map(r => ({
            date: r.report_date,
            value: r.conversion_rate_pct !== null ? parseFloat(r.conversion_rate_pct) : null
          })),
          current: latestConversion ? parseFloat(latestConversion.conversion_rate_pct) : null,
          targetMin: 25,
          healthStatus: latestConversion?.health_status || 'NO DATA',
        },
        generators: {
          timeSeries: generatorRows.map(r => ({
            date: r.report_date,
            finnE: parseInt(r.finn_e_count) || 0,
            finnT: parseInt(r.finn_t_count) || 0,
            gnS: parseInt(r.gn_s_count) || 0,
          })),
          current: {
            finnE: latestGenerator ? parseInt(latestGenerator.finn_e_count) || 0 : 0,
            finnT: latestGenerator ? parseInt(latestGenerator.finn_t_count) || 0 : 0,
            gnS: latestGenerator ? parseInt(latestGenerator.gn_s_count) || 0 : 0,
            dominant: latestGenerator?.dominant_generator || null,
            dominantPct: latestGenerator ? Math.max(
              parseFloat(latestGenerator.finn_e_pct) || 0,
              parseFloat(latestGenerator.finn_t_pct) || 0,
              parseFloat(latestGenerator.gn_s_pct) || 0
            ) : 0,
          },
          monocultureThreshold: 60,
          healthStatus: latestGenerator?.health_status || 'NO DATA',
        },
        causalDepth: {
          timeSeries: depthRows.map(r => ({
            date: r.report_date,
            value: parseFloat(r.avg_causal_depth) > 0 ? parseFloat(r.avg_causal_depth) : null
          })),
          current: latestDepth ? parseFloat(latestDepth.avg_causal_depth) : null,
          targetMin: 2.5,
          healthStatus: latestDepth?.health_status || 'NO DATA',
          trend: latestDepth?.trend || null,
        },
        lastRefresh: new Date().toISOString(),
      }
    } catch (e) {
      console.warn('Learning Trajectory views not available:', e)
    }

    return NextResponse.json({
      progress: progress?.current_progress_pct || 80,
      fmclDistribution: progress?.fmcl_distribution || '0-0-0-0-0',
      highSeverityClosed: progress?.high_severity_closed || 0,
      highSeverityTotal: progress?.high_severity_total || 0,

      dailyDelta: dailyDelta.map((item: any) => ({
        id: item.id,
        type: item.item_type,
        text: item.item_text,
        metric: item.metric,
        delta: item.delta,
      })),

      mechanisms: mechanisms.map((m: any) => ({
        id: m.mechanism_id,
        signal: m.signal_description,
        signalSource: m.signal_source,
        reasoning: m.reasoning_description,
        test: m.test_description,
        outcome: m.outcome_description,
        outcomeStatus: m.outcome_status,
      })),

      searchActivity: {
        queriesPerDay: activity?.search_queries_per_day || 0,
        domainsCovered: ['macro', 'rates', 'crypto', 'equity'].slice(0, activity?.search_domains_covered || 4),
        trend: activity?.search_trend || 'stable',
      },

      reasoningIntensity: {
        callsPerDay: activity?.llm_calls_per_day || 0,
        tierUsed: activity?.llm_tier_used || 'tier2',
        purposes: ['diagnosis', 'synthesis', 'validation'],
        costToday: parseFloat(activity?.llm_cost_today) || 0,
      },

      learningYield: {
        failureModesClosed: activity?.failure_modes_closed_7d || 0,
        invariantsCreated: activity?.invariants_created || 0,
        suppressionRegretReduced: activity?.suppression_regret_reduced || 0,
        trend: activity?.yield_trend || 'stable',
      },

      llmBalance: parseFloat(activity?.llm_balance_remaining) || 0,
      activeProviders: activity?.active_providers || '',

      // CEO-DIR-2026-058: Dual-track metrics
      systemMaturity: progress?.current_progress_pct || 0,  // Renamed from "progress"
      marketLearning: {
        progress: marketLearning?.market_learning_pct || 0,
        status: evidenceClock?.holdout_eligibility_status || marketLearning?.status_label || 'BLOCKED: View not found',
        labelLocked: marketLearning?.label_locked || false,
        labelVersion: marketLearning?.label_version || null,
        labelHash: marketLearning?.label_hash || null,
        holdoutCount: marketLearning?.holdout_count || 0,
        holdoutFrozen: (marketLearning?.frozen_count || 0) > 0,
        holdoutVerified: (marketLearning?.verified_count || 0) > 0,
        latestBrier: marketLearning?.latest_brier || null,
        latestDelta: marketLearning?.latest_delta || null,
        latestDirection: marketLearning?.latest_direction || null,
        totalEvaluations: marketLearning?.total_evaluations || 0,
        significantImprovements: marketLearning?.significant_improvements || 0,
      },

      // CEO-DIR-2026-059: Evidence Clock (canonical time + data availability)
      // CEO-DIR-2026-060: Time Integrity status included
      evidenceClock: {
        canonicalNow: evidenceClock?.canonical_now_utc || new Date().toISOString(),
        operationalStart: evidenceClock?.operational_start || null,
        holdoutWindowStart: evidenceClock?.holdout_window_start || null,
        holdoutWindowEnd: evidenceClock?.holdout_window_end || null,
        forecastDaysAvailable: parseInt(evidenceClock?.forecast_days_available) || 0,
        outcomeDaysAvailable: parseInt(evidenceClock?.outcome_days_available) || 0,
        totalHoldoutEligibleRecords: parseInt(evidenceClock?.total_holdout_eligible_records) || 0,
        holdoutEligibilityStatus: evidenceClock?.holdout_eligibility_status || 'UNKNOWN',
        // CEO-DIR-2026-060: Time Integrity
        timeIntegrity: timeIntegrity ? {
          status: timeIntegrity.time_integrity_status || 'UNKNOWN',
          validCount: parseInt(timeIntegrity.valid_count) || 0,
          invalidCount: parseInt(timeIntegrity.invalid_count) || 0,
          pendingCount: parseInt(timeIntegrity.pending_count) || 0,
          preCanonicalCount: parseInt(timeIntegrity.pre_canonical_count) || 0,
          totalCount: parseInt(timeIntegrity.total_count) || 0,
          integrityPct: parseFloat(timeIntegrity.time_integrity_pct) || 100,
          canProceedWithLearning: timeIntegrity.can_proceed_with_learning || false,
          canProceedWithReporting: timeIntegrity.can_proceed_with_reporting || false,
          canProceedWithQgf6: timeIntegrity.can_proceed_with_qgf6 || false,
        } : undefined,
      },

      // CEO-DIR-2026-LEARNING-OBSERVABILITY: Research Trinity metrics
      researchTrinity,

      // CEO-DIR-2026-DAY25-VISUAL-TRUTH: Learning Trajectory Time Series
      learningTrajectory,

      // CEO-DIR-2026-DAY25-LEARNING-VISIBILITY-002: Four-Plane Learning Data
      fourPlanes,

      lastUpdated: new Date().toISOString(),
      source: 'database',
    })
  } catch (error) {
    console.error('Learning API error:', error)

    // Return error with details for debugging
    return NextResponse.json(
      {
        error: 'Failed to fetch learning data',
        details: error instanceof Error ? error.message : 'Unknown error',
        source: 'error'
      },
      { status: 500 }
    )
  } finally {
    if (client) {
      client.release()
    }
  }
}
