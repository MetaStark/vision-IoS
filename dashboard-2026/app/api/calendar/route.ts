/**
 * Calendar Dashboard API - CEO-DIR-2026-CALENDAR-GOVERNED-TESTING-001
 *
 * Calendar-as-Law Doctrine: If something matters, it exists as a canonical calendar event.
 * CEO must understand system state in <30 seconds.
 */

import { NextResponse } from 'next/server'
import { Pool } from 'pg'

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

    // Fetch dashboard calendar events
    const calendarResult = await client.query(`
      SELECT
        event_id,
        event_name,
        event_category,
        event_date,
        end_date,
        event_status,
        owning_agent,
        event_details,
        color_code,
        year,
        month,
        day,
        day_name
      FROM fhq_calendar.v_dashboard_calendar
      WHERE event_date >= CURRENT_DATE - INTERVAL '30 days'
        AND event_date <= CURRENT_DATE + INTERVAL '60 days'
      ORDER BY event_date ASC, created_at DESC
    `)

    // Fetch LVG status for daily reports
    const lvgResult = await client.query(`
      SELECT * FROM fhq_calendar.v_lvg_daily_status
    `)

    // CEO-DIR-2026-DAY25: Fetch cumulative hypothesis totals
    const cumulativeResult = await client.query(`
      SELECT
        COUNT(*) as total_hypotheses,
        COUNT(*) FILTER (WHERE status = 'FALSIFIED') as total_falsified,
        COUNT(*) FILTER (WHERE status NOT IN ('FALSIFIED', 'DRAFT')) as total_active,
        CASE
          WHEN COUNT(*) FILTER (WHERE status != 'DRAFT') = 0 THEN 0
          ELSE ROUND(COUNT(*) FILTER (WHERE status = 'FALSIFIED')::numeric /
               NULLIF(COUNT(*) FILTER (WHERE status != 'DRAFT'), 0) * 100, 1)
        END as death_rate_pct,
        MAX(created_at) as last_hypothesis_time
      FROM fhq_learning.hypothesis_canon
    `)
    const cumulative = cumulativeResult.rows[0] || {}

    // CEO-DIR-2026-DAY25: Fetch daemon health status for finn_scheduler
    const daemonHealthResult = await client.query(`
      SELECT daemon_name, status, last_heartbeat,
             EXTRACT(EPOCH FROM (NOW() - last_heartbeat)) as seconds_since_heartbeat
      FROM fhq_monitoring.daemon_health
      WHERE daemon_name = 'finn_scheduler'
      LIMIT 1
    `)
    const daemonHealth = daemonHealthResult.rows[0] || null
    // Daemon is RUNNING if healthy and heartbeat within 24 hours (86400 seconds)
    // Using 24h threshold since daemons run on scheduled intervals, not continuously
    const daemonStatus = daemonHealth?.status === 'HEALTHY' &&
                         daemonHealth?.seconds_since_heartbeat < 86400
                         ? 'RUNNING' : 'STOPPED'

    // Fetch shadow tier status
    const shadowTierResult = await client.query(`
      SELECT * FROM fhq_calendar.v_shadow_tier_calendar_status
    `)

    // Fetch fail-closed governance checks
    const governanceResult = await client.query(`
      SELECT * FROM fhq_calendar.check_calendar_sync()
    `)

    // Fetch canonical tests with ALL CEO-required fields (Migration 342)
    const canonicalTestsResult = await client.query(`
      SELECT
        test_id,
        test_code,
        COALESCE(display_name, test_name) as test_name,
        owning_agent,
        status,
        -- Timestamps (immutable once ACTIVE)
        start_ts,
        end_ts,
        -- Progress (computed from storage)
        days_elapsed,
        days_remaining,
        required_days,
        ROUND((COALESCE(days_elapsed, 0)::NUMERIC / NULLIF(required_days, 0)) * 100, 1) as progress_pct,
        -- Section 3 required fields
        business_intent,
        beneficiary_system,
        baseline_definition,
        target_metrics,
        hypothesis_code,
        success_criteria,
        failure_criteria,
        -- Governance (CEO Modification 5)
        monitoring_agent_ec,
        escalation_state,
        ceo_action_required,
        recommended_actions,
        mid_test_checkpoint,
        verdict,
        -- Calendar
        calendar_category
      FROM fhq_calendar.canonical_test_events
      WHERE status IN ('ACTIVE', 'SCHEDULED', 'COMPLETED')
      ORDER BY
        CASE WHEN ceo_action_required THEN 0 ELSE 1 END,
        start_ts ASC
    `)

    // Fetch economic events from IoS-016 (Section 2)
    const economicEventsResult = await client.query(`
      SELECT
        ce.event_id,
        etr.event_name,
        ce.event_type_code,
        ce.event_timestamp,
        ce.consensus_estimate,
        ce.previous_value,
        ce.actual_value,
        ce.surprise_score,
        etr.impact_rank,
        etr.event_category as economic_category,
        CASE
          WHEN ce.actual_value IS NOT NULL THEN 'RELEASED'
          WHEN ce.event_timestamp < NOW() THEN 'PENDING'
          ELSE 'SCHEDULED'
        END as status
      FROM fhq_calendar.calendar_events ce
      JOIN fhq_calendar.event_type_registry etr
        ON ce.event_type_code = etr.event_type_code
      WHERE ce.event_timestamp >= CURRENT_DATE - INTERVAL '7 days'
        AND ce.event_timestamp <= CURRENT_DATE + INTERVAL '60 days'
        AND ce.is_canonical = TRUE
      ORDER BY ce.event_timestamp ASC
    `)

    // Fetch pending CEO alerts
    const alertsResult = await client.query(`
      SELECT
        alert_id,
        alert_type,
        alert_title,
        alert_summary,
        decision_options,
        priority,
        status,
        calendar_date,
        created_at
      FROM fhq_calendar.ceo_calendar_alerts
      WHERE status = 'PENDING'
      ORDER BY
        CASE priority
          WHEN 'CRITICAL' THEN 1
          WHEN 'HIGH' THEN 2
          WHEN 'NORMAL' THEN 3
          ELSE 4
        END,
        created_at ASC
    `)

    // Fetch observation windows with rich details (Section 8)
    const observationResult = await client.query(`
      SELECT
        window_name,
        window_type,
        start_date,
        end_date,
        required_market_days,
        current_market_days,
        status,
        criteria_met,
        volume_scaling_active,
        metric_drift_alerts,
        expected_improvement,
        improvement_metrics,
        starting_consensus_state
      FROM fhq_learning.observation_window
      WHERE status = 'ACTIVE'
    `)

    // CEO-DIR-2026-DAY25-SESSION11: Test Progress Metrics (database-verified)
    // Fetch window-specific metrics for each canonical test
    const testProgressResult = await client.query(`
      WITH test_windows AS (
        SELECT
          test_code,
          start_ts,
          end_ts,
          hypothesis_code
        FROM fhq_calendar.canonical_test_events
        WHERE status = 'ACTIVE'
      ),
      window_metrics AS (
        SELECT
          tw.test_code,
          tw.start_ts,
          tw.end_ts,
          tw.hypothesis_code,
          COUNT(*) FILTER (WHERE hc.created_at >= tw.start_ts AND hc.created_at <= COALESCE(tw.end_ts, NOW())) as hypotheses_in_window,
          COUNT(*) FILTER (WHERE hc.created_at >= tw.start_ts AND hc.created_at <= COALESCE(tw.end_ts, NOW()) AND hc.status = 'FALSIFIED') as falsified_in_window,
          COUNT(*) FILTER (WHERE hc.created_at >= tw.start_ts AND hc.created_at <= COALESCE(tw.end_ts, NOW()) AND hc.status = 'ACTIVE') as active_in_window,
          COUNT(*) FILTER (WHERE hc.created_at >= tw.start_ts AND hc.created_at <= COALESCE(tw.end_ts, NOW()) AND hc.status = 'DRAFT') as draft_in_window,
          MAX(hc.created_at) FILTER (WHERE hc.created_at >= tw.start_ts) as last_hypothesis_in_window
        FROM test_windows tw
        CROSS JOIN fhq_learning.hypothesis_canon hc
        GROUP BY tw.test_code, tw.start_ts, tw.end_ts, tw.hypothesis_code
      )
      SELECT
        test_code,
        start_ts as window_start,
        end_ts as window_end,
        hypothesis_code as linked_hypothesis,
        hypotheses_in_window,
        falsified_in_window,
        active_in_window,
        draft_in_window,
        last_hypothesis_in_window,
        CASE
          WHEN (falsified_in_window + active_in_window) = 0 THEN NULL
          ELSE ROUND(falsified_in_window::numeric / (falsified_in_window + active_in_window) * 100, 1)
        END as death_rate_in_window,
        NOW() as verified_at
      FROM window_metrics
    `)

    // Build test progress map for easy lookup
    const testProgressMap: Record<string, any> = {}
    testProgressResult.rows.forEach((row: any) => {
      testProgressMap[row.test_code] = {
        windowStart: row.window_start,
        windowEnd: row.window_end,
        linkedHypothesis: row.linked_hypothesis,
        hypothesesInWindow: parseInt(row.hypotheses_in_window) || 0,
        falsifiedInWindow: parseInt(row.falsified_in_window) || 0,
        activeInWindow: parseInt(row.active_in_window) || 0,
        draftInWindow: parseInt(row.draft_in_window) || 0,
        lastHypothesisInWindow: row.last_hypothesis_in_window,
        deathRateInWindow: row.death_rate_in_window ? parseFloat(row.death_rate_in_window) : null,
        verifiedAt: row.verified_at,
      }
    })

    // CEO-DIR-2026-DAY25: Learning Visibility Metrics (time-series for graphs)
    const learningMetricsResult = await client.query(`
      SELECT
        metric_date,
        hypotheses_total,
        hypotheses_falsified,
        death_rate_pct,
        from_errors,
        avg_causal_depth,
        gen_finn_e,
        gen_finn_t,
        gen_gn_s,
        gen_other
      FROM fhq_learning.v_daily_learning_metrics
      ORDER BY metric_date ASC
      LIMIT 30
    `)

    // CEO-DIR-2026-DAY25: Learning Status Summary
    const learningSummaryResult = await client.query(`
      SELECT * FROM fhq_learning.v_learning_status_summary
    `)

    // CEO-DIR-2026-DAY25: Generator Performance
    const generatorPerfResult = await client.query(`
      SELECT * FROM fhq_learning.v_generator_performance
    `)

    // CEO-VEDTAK-2026-ALPHA-FACTORY: G1.5 Experiment Progression
    const g15ProgressionResult = await client.query(`
      SELECT * FROM fhq_learning.v_g1_5_throughput_tracker
    `)

    // G1.5 Generator Performance
    const g15GeneratorsResult = await client.query(`
      SELECT * FROM fhq_learning.v_g1_5_generator_performance
    `)

    // G1.5 Quartile Survival (for visual)
    const g15QuartilesResult = await client.query(`
      SELECT * FROM fhq_learning.v_g1_5_quartile_survival
    `)

    // G1.5 Spearman Correlation Status
    const g15SpearmanResult = await client.query(`
      SELECT * FROM fhq_learning.calculate_g1_5_spearman()
    `)

    // G1.5 Stale Candidates Count
    const g15StaleCandidatesResult = await client.query(`
      SELECT
        COUNT(*) FILTER (WHERE freshness_status = 'FRESH') as fresh_count,
        COUNT(*) FILTER (WHERE freshness_status = 'WARNING') as warning_count,
        COUNT(*) FILTER (WHERE freshness_status = 'STALE_CANDIDATE') as stale_count
      FROM fhq_learning.v_stale_candidates
    `)

    // G1.5 Validator Authority
    const g15ValidatorsResult = await client.query(`
      SELECT * FROM fhq_learning.v_authorized_validators
    `)

    // Get current date info
    const dateResult = await client.query(`
      SELECT
        CURRENT_DATE as today,
        EXTRACT(YEAR FROM CURRENT_DATE) as year,
        EXTRACT(MONTH FROM CURRENT_DATE) as month,
        TO_CHAR(CURRENT_DATE, 'Month') as month_name
    `)

    const lvg = lvgResult.rows[0] || {}
    const shadowTier = shadowTierResult.rows[0] || {}
    const dateInfo = dateResult.rows[0] || {}

    return NextResponse.json({
      // Calendar events
      events: calendarResult.rows.map((e: any) => ({
        id: e.event_id,
        name: e.event_name,
        category: e.event_category,
        date: e.event_date,
        endDate: e.end_date,
        status: e.event_status,
        owner: e.owning_agent,
        details: e.event_details,
        color: e.color_code,
        year: parseInt(e.year),
        month: parseInt(e.month),
        day: parseInt(e.day),
        dayName: e.day_name?.trim(),
      })),

      // Canonical tests with CEO-required fields (Migration 342)
      // CEO-DIR-2026-DAY25-SESSION11: Now includes test progress metrics
      canonicalTests: canonicalTestsResult.rows.map((t: any) => {
        const progress = testProgressMap[t.test_code] || null
        return {
          id: t.test_id,
          code: t.test_code,
          name: t.test_name,
          owner: t.owning_agent,
          status: t.status,
          category: t.calendar_category,
          // Timestamps (immutable)
          startDate: t.start_ts,
          endDate: t.end_ts,
          // Progress (computed from storage - CEO Mod 3)
          daysElapsed: parseInt(t.days_elapsed) || 0,
          daysRemaining: parseInt(t.days_remaining) || 0,
          requiredDays: parseInt(t.required_days) || 30,
          progressPct: parseFloat(t.progress_pct) || 0,
          // Purpose & Logic
          businessIntent: t.business_intent,
          beneficiarySystem: t.beneficiary_system,
          hypothesisCode: t.hypothesis_code,
          // Measurement
          baselineDefinition: t.baseline_definition,
          targetMetrics: t.target_metrics,
          successCriteria: t.success_criteria,
          failureCriteria: t.failure_criteria,
          // Governance (CEO Mod 5)
          monitoringAgent: t.monitoring_agent_ec,
          escalationState: t.escalation_state,
          ceoActionRequired: t.ceo_action_required || false,
          recommendedActions: t.recommended_actions || [],
          midTestCheckpoint: t.mid_test_checkpoint,
          verdict: t.verdict,
          // CEO-DIR-2026-DAY25-SESSION11: Test Progress (database-verified)
          testProgress: progress ? {
            hypothesesInWindow: progress.hypothesesInWindow,
            falsifiedInWindow: progress.falsifiedInWindow,
            activeInWindow: progress.activeInWindow,
            draftInWindow: progress.draftInWindow,
            deathRateInWindow: progress.deathRateInWindow,
            lastHypothesisInWindow: progress.lastHypothesisInWindow,
            verifiedAt: progress.verifiedAt,
            // Trajectory calculation
            trajectory: (() => {
              if (progress.deathRateInWindow === null) return 'INSUFFICIENT_DATA'
              // For Tier-1 Brutality/Calibration test: target is 60-90%
              if (t.test_code === 'TEST-TIER1-CAL-001' || t.test_code?.includes('TIER1')) {
                if (progress.deathRateInWindow >= 60 && progress.deathRateInWindow <= 90) return 'ON_TARGET'
                if (progress.deathRateInWindow > 90) return 'TOO_BRUTAL'
                return 'TOO_MILD'
              }
              // Default: just check if within reasonable bounds
              if (progress.deathRateInWindow >= 60 && progress.deathRateInWindow <= 90) return 'ON_TARGET'
              if (progress.deathRateInWindow > 90) return 'TOO_BRUTAL'
              if (progress.deathRateInWindow < 60) return 'TOO_MILD'
              return 'UNKNOWN'
            })(),
          } : null,
        }
      }),

      // Legacy activeTests mapping (for backwards compatibility)
      activeTests: canonicalTestsResult.rows
        .filter((t: any) => t.status === 'ACTIVE' || t.status === 'SCHEDULED')
        .map((t: any) => ({
          name: t.test_name,
          code: t.test_code,
          owner: t.owning_agent,
          status: t.status,
          daysElapsed: parseInt(t.days_elapsed) || 0,
          daysRemaining: parseInt(t.days_remaining) || 0,
          currentSamples: 0,
          targetSamples: 0,
          sampleStatus: 'ON_TRACK',
          category: t.calendar_category,
          businessIntent: t.business_intent,
          beneficiarySystem: t.beneficiary_system,
          baselineDefinition: t.baseline_definition,
          targetMetrics: t.target_metrics,
          hypothesisCode: t.hypothesis_code,
          successCriteria: t.success_criteria,
          failureCriteria: t.failure_criteria,
          escalationRules: t.recommended_actions,
          midTestCheckpoint: t.mid_test_checkpoint,
          outcome: t.verdict,
          startDate: t.start_ts,
          endDate: t.end_ts,
        })),

      // Economic events from IoS-016 (Section 2)
      economicEvents: economicEventsResult.rows.map((e: any) => ({
        id: e.event_id,
        name: e.event_name,
        typeCode: e.event_type_code,
        timestamp: e.event_timestamp,
        consensus: e.consensus_estimate,
        previous: e.previous_value,
        actual: e.actual_value,
        surprise: e.surprise_score,
        impactRank: e.impact_rank,
        category: e.economic_category,
        status: e.status,
      })),

      // CEO Alerts
      alerts: alertsResult.rows.map((a: any) => ({
        id: a.alert_id,
        type: a.alert_type,
        title: a.alert_title,
        summary: a.alert_summary,
        options: a.decision_options,
        priority: a.priority,
        status: a.status,
        date: a.calendar_date,
        createdAt: a.created_at,
      })),

      // Observation windows with rich details (Section 8)
      observationWindows: observationResult.rows.map((w: any) => ({
        name: w.window_name,
        type: w.window_type,
        startDate: w.start_date,
        endDate: w.end_date,
        requiredDays: w.required_market_days,
        currentDays: w.current_market_days,
        status: w.status,
        criteriaMet: w.criteria_met,
        volumeScaling: w.volume_scaling_active,
        driftAlerts: w.metric_drift_alerts,
        // Rich details (Section 8 required)
        expectedImprovement: w.expected_improvement,
        improvementMetrics: w.improvement_metrics,
        startingConsensusState: w.starting_consensus_state,
      })),

      // LVG Status (Section 5.5) + Cumulative Totals (CEO-DIR-2026-DAY25)
      lvgStatus: {
        hypothesesBornToday: lvg.hypotheses_born_today || 0,
        hypothesesKilledToday: lvg.hypotheses_killed_today || 0,
        entropyScore: lvg.entropy_score,
        thrashingIndex: lvg.thrashing_index,
        governorAction: lvg.governor_action || 'NORMAL',
        velocityBrakeActive: lvg.velocity_brake_active || false,
        // Cumulative totals (CEO-DIR-2026-DAY25)
        totalHypotheses: parseInt(cumulative.total_hypotheses) || 0,
        totalFalsified: parseInt(cumulative.total_falsified) || 0,
        totalActive: parseInt(cumulative.total_active) || 0,
        deathRatePct: parseFloat(cumulative.death_rate_pct) || 0,
        lastHypothesisTime: cumulative.last_hypothesis_time || null,
        // Daemon status from fhq_monitoring.daemon_health
        daemonStatus: daemonStatus,
      },

      // Shadow Tier Status (Section 6.3)
      shadowTier: {
        totalSamples: shadowTier.total_samples || 0,
        survivedCount: shadowTier.survived_count || 0,
        survivalRate: shadowTier.shadow_survival_rate || 0,
        calibrationStatus: shadowTier.calibration_status || 'NORMAL',
      },

      // Governance checks (Section 9)
      governanceChecks: governanceResult.rows.map((g: any) => ({
        name: g.check_name,
        status: g.check_status,
        discrepancy: g.discrepancy,
      })),

      // CEO-DIR-2026-DAY25: Learning Visibility (time-series for graphs)
      learningMetrics: learningMetricsResult.rows.map((m: any) => ({
        date: m.metric_date,
        hypothesesTotal: parseInt(m.hypotheses_total) || 0,
        hypothesesFalsified: parseInt(m.hypotheses_falsified) || 0,
        deathRatePct: parseFloat(m.death_rate_pct) || 0,
        fromErrors: parseInt(m.from_errors) || 0,
        avgCausalDepth: parseFloat(m.avg_causal_depth) || 0,
        genFinnE: parseInt(m.gen_finn_e) || 0,
        genFinnT: parseInt(m.gen_finn_t) || 0,
        genGnS: parseInt(m.gen_gn_s) || 0,
        genOther: parseInt(m.gen_other) || 0,
      })),

      // CEO-DIR-2026-DAY25: Learning Summary with status sentence
      learningSummary: (() => {
        const s = learningSummaryResult.rows[0] || {}
        const deathRate = parseFloat(s.death_rate_pct) || 0
        let statusSentence = ''
        if (deathRate >= 60 && deathRate <= 90) {
          statusSentence = 'ON TRACK: Death rate within target band (60-90%).'
        } else if (deathRate > 90) {
          statusSentence = 'BEHIND: Death rate too high - hypotheses dying too fast, need more robust generation.'
        } else {
          statusSentence = 'BEHIND: Death rate too low - Tier-1 not brutal enough, tighten falsification criteria.'
        }
        return {
          totalHypotheses: parseInt(s.total_hypotheses) || 0,
          totalFalsified: parseInt(s.total_falsified) || 0,
          totalActive: parseInt(s.total_active) || 0,
          deathRatePct: deathRate,
          deathRateStatus: s.death_rate_status || 'UNKNOWN',
          avgCausalDepth: parseFloat(s.avg_causal_depth) || 0,
          finnECount: parseInt(s.finn_e_count) || 0,
          finnTCount: parseInt(s.finn_t_count) || 0,
          gnSCount: parseInt(s.gn_s_count) || 0,
          lastHypothesisTime: s.last_hypothesis_time,
          todayCount: parseInt(s.today_count) || 0,
          statusSentence,
        }
      })(),

      // CEO-DIR-2026-DAY25: Generator Performance
      generatorPerformance: generatorPerfResult.rows.map((g: any) => ({
        name: g.generator_name,
        totalGenerated: parseInt(g.total_generated) || 0,
        falsified: parseInt(g.falsified) || 0,
        surviving: parseInt(g.surviving) || 0,
        deathRatePct: parseFloat(g.death_rate_pct) || 0,
        avgDepth: parseFloat(g.avg_depth) || 0,
      })),

      // Current date
      currentDate: {
        today: dateInfo.today,
        year: parseInt(dateInfo.year),
        month: parseInt(dateInfo.month),
        monthName: dateInfo.month_name?.trim(),
      },

      // CEO-VEDTAK-2026-ALPHA-FACTORY: G1.5 Experiment Progression
      g15Experiment: (() => {
        const prog = g15ProgressionResult.rows[0] || {}
        const spearman = g15SpearmanResult.rows[0] || {}
        const stale = g15StaleCandidatesResult.rows[0] || {}
        return {
          experimentId: prog.experiment_id || 'FHQ-EXP-PRETIER-G1.5',
          experimentStatus: prog.experiment_status || 'UNKNOWN',
          startTs: prog.start_ts,
          endTs: prog.end_ts,
          daysElapsed: parseInt(prog.days_elapsed) || 0,
          daysRemaining: parseInt(prog.days_remaining) || 0,
          // Throughput metrics
          todayHypotheses: parseInt(prog.today_hypotheses) || 0,
          todayGenerators: parseInt(prog.today_generators) || 0,
          todayAvgDepth: parseFloat(prog.today_avg_depth) || 0,
          totalHypotheses: parseInt(prog.total_hypotheses) || 0,
          avgDailyRate: parseFloat(prog.avg_daily_rate) || 0,
          avgDailyGenerators: parseFloat(prog.avg_daily_generators) || 0,
          avgCausalDepth: parseFloat(prog.avg_causal_depth) || 0,
          // Targets
          baselineRate: parseFloat(prog.baseline_rate) || 15,
          targetRate: parseFloat(prog.target_rate) || 30,
          rateStatus: prog.rate_status || 'BELOW_TARGET',
          targetGenerators: parseFloat(prog.target_generators) || 3,
          generatorStatus: prog.generator_status || 'BELOW_TARGET',
          // Death progress (primary trigger)
          deathsWithScore: parseInt(prog.deaths_with_score) || 0,
          targetDeaths: prog.target_deaths || 30,
          deathProgressPct: parseFloat(prog.death_progress_pct) || 0,
          calibrationTriggerMet: prog.calibration_trigger_met || false,
          endTriggerStatus: prog.end_trigger_status || 'IN_PROGRESS',
          // Freeze compliance
          weightsFrozen: prog.weights_frozen ?? true,
          thresholdsFrozen: prog.thresholds_frozen ?? true,
          agentRolesFrozen: prog.agent_roles_frozen ?? true,
          oxygenCriteriaFrozen: prog.oxygen_criteria_frozen ?? true,
          // Validator capacity
          activeValidators: parseInt(prog.active_validators) || 0,
          targetValidators: prog.target_validators || 5,
          validatorCapacityStatus: prog.validator_capacity_status || 'UNKNOWN',
          // Spearman correlation
          spearman: {
            sampleSize: parseInt(spearman.sample_size) || 0,
            rho: spearman.spearman_rho ? parseFloat(spearman.spearman_rho) : null,
            dataStatus: spearman.data_status || 'INSUFFICIENT_DATA',
            interpretation: spearman.interpretation || 'Awaiting data',
          },
          // Stale candidates
          staleCandidates: {
            fresh: parseInt(stale.fresh_count) || 0,
            warning: parseInt(stale.warning_count) || 0,
            stale: parseInt(stale.stale_count) || 0,
          },
          // Computed timestamp
          computedAt: prog.computed_at || new Date().toISOString(),
        }
      })(),

      // G1.5 Generators
      g15Generators: g15GeneratorsResult.rows.map((g: any) => ({
        generatorId: g.generator_id,
        totalHypotheses: parseInt(g.total_hypotheses) || 0,
        last24h: parseInt(g.last_24h) || 0,
        last7d: parseInt(g.last_7d) || 0,
        avgDepth: parseFloat(g.avg_depth) || 0,
        avgBirthScore: parseFloat(g.avg_birth_score) || null,
        deaths: parseInt(g.deaths) || 0,
        activeDrafts: parseInt(g.active_drafts) || 0,
        lastHypothesisAt: g.last_hypothesis_at,
        volumeSharePct: parseFloat(g.volume_share_pct) || 0,
      })),

      // G1.5 Quartile Survival
      g15Quartiles: g15QuartilesResult.rows.map((q: any) => ({
        quartile: parseInt(q.score_quartile) || 0,
        label: q.quartile_label,
        totalHypotheses: parseInt(q.total_hypotheses) || 0,
        deaths: parseInt(q.deaths) || 0,
        survivors: parseInt(q.survivors) || 0,
        avgBirthScore: parseFloat(q.avg_birth_score) || 0,
        avgSurvivalHours: parseFloat(q.avg_survival_hours) || null,
        minSurvivalHours: parseFloat(q.min_survival_hours) || null,
        maxSurvivalHours: parseFloat(q.max_survival_hours) || null,
      })),

      // G1.5 Validators
      g15Validators: g15ValidatorsResult.rows.map((v: any) => ({
        ec: v.validator_ec,
        name: v.validator_name,
        role: v.validator_role,
        wave: v.registration_wave,
        isActive: v.is_active,
        totalValidations: parseInt(v.total_validations) || 0,
        lastValidation: v.last_validation,
      })),

      // Metadata
      lastUpdated: new Date().toISOString(),
      source: 'database',
    })
  } catch (error) {
    console.error('Calendar API error:', error)
    return NextResponse.json(
      {
        error: 'Failed to fetch calendar data',
        details: error instanceof Error ? error.message : 'Unknown error',
        source: 'error',
      },
      { status: 500 }
    )
  } finally {
    if (client) client.release()
  }
}
