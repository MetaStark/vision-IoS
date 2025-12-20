/**
 * EC-018 Alpha Hunt Endpoint
 * POST /api/alpha/hunt
 *
 * Authority: CEO Directive CD-EXEC-EC018-DEEPSEEK-ALPHA-001
 * Constitutional Basis: EC-018, ADR-018 (State Discipline), ADR-016 (DEFCON)
 *
 * This endpoint:
 * 1. Captures current market state with cryptographic hash (ADR-018)
 * 2. Calls DeepSeek V3 (deepseek-chat) for G0 hypothesis generation
 * 3. Stores G0 draft proposals with per-artifact state-lock
 * 4. Returns proposals with executive summaries
 *
 * CONSTITUTIONAL CONSTRAINT: EC-018 has ZERO execution authority.
 * All outputs are G0 hypotheses only - no trading decisions.
 */

import { NextRequest, NextResponse } from 'next/server'
import { Pool } from 'pg'
import crypto from 'crypto'

// Database connection with UTF-8 encoding (Windows compatibility)
const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
})

// Force UTF-8 on every new connection (Windows workaround)
pool.on('connect', (client) => {
  client.query('SET client_encoding TO \'UTF8\'')
})

// Helper to sanitize non-ASCII characters for Windows PostgreSQL
function sanitizeForDb(str: string): string {
  if (!str) return str
  // Replace problematic Unicode characters with ASCII equivalents
  return str
    .replace(/[\u03B1-\u03C9]/g, '') // Greek letters
    .replace(/[\u2018\u2019]/g, "'") // Smart quotes
    .replace(/[\u201C\u201D]/g, '"') // Smart double quotes
    .replace(/[\u2013\u2014]/g, '-') // En/em dashes
    .replace(/[\u2026]/g, '...')     // Ellipsis
    .replace(/[^\x00-\x7F]/g, '')    // Remove remaining non-ASCII
}

// DeepSeek configuration (CD-EXEC-EC018-DEEPSEEK-ALPHA-001)
const DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
const DEEPSEEK_MODEL = 'deepseek-chat' // V3 for broad reasoning
const BUDGET_CAP_USD = 2.00
const TOKEN_CAP = 50000

// Pricing per TCS-v1 (2025-12-14)
const COST_PER_1K_INPUT = 0.00028
const COST_PER_1K_OUTPUT = 0.00042

// ============================================================================
// Types
// ============================================================================

interface HuntRequest {
  focus_areas?: string[]
  budget_cap_usd?: number
  initiated_by?: string
}

interface StateVector {
  state_vector_id: string
  state_hash: string
  captured_at: string
  market_regime: string
  regime_confidence: number
  btc_price: number | null
  btc_24h_change: number | null
  vix_value: number | null
  defcon_level: number
  daily_budget_remaining: number
}

interface G0Proposal {
  proposal_id: string
  hypothesis_id: string
  hypothesis_title: string
  hypothesis_category: string
  hypothesis_statement: string
  confidence_score: number
  executive_summary: string
  falsifiability_statement: string
  state_hash_at_creation: string
  defcon_at_generation: number
  downstream_pipeline: string[]
  supporting_evidence?: string[]
  risk_factors?: string[]
  expected_edge_bps?: number | null
  backtest_requirements?: { lookback_days?: number; min_samples?: number } | null
}

// ============================================================================
// Helper Functions
// ============================================================================

function computeStateHash(state: Record<string, any>): string {
  const ordered = JSON.stringify(state, Object.keys(state).sort())
  return crypto.createHash('sha256').update(ordered).digest('hex')
}

function generateHypothesisId(): string {
  const date = new Date().toISOString().split('T')[0].replace(/-/g, '')
  const seq = Math.floor(Math.random() * 1000).toString().padStart(3, '0')
  return `ALPHA-${date}-${seq}`
}

// ============================================================================
// State Vector Capture (ADR-018 Compliance)
// ============================================================================

async function captureStateVector(): Promise<StateVector> {
  const client = await pool.connect()
  try {
    // Get current regime from IoS-003 (with fallback)
    let regime = { market_regime: 'NEUTRAL', regime_confidence: 0.5 }
    try {
      const regimeResult = await client.query(`
        SELECT
          sovereign_regime as market_regime,
          COALESCE((state_probabilities->sovereign_regime)::float, 0.5) as regime_confidence
        FROM fhq_perception.sovereign_regime_state_v4
        WHERE asset_id = 'BTC-USD'
        ORDER BY timestamp DESC
        LIMIT 1
      `)
      if (regimeResult.rows[0]) regime = regimeResult.rows[0]
    } catch (e) {
      console.log('[EC-018] Regime query failed, using default')
    }

    // Get current BTC price (with fallback)
    let price = { btc_price: null, btc_24h_change: null }
    try {
      const priceResult = await client.query(`
        SELECT
          close as btc_price
        FROM fhq_data.price_series
        WHERE listing_id = (SELECT listing_id FROM fhq_meta.asset_registry WHERE asset_id = 'BTC-USD' LIMIT 1)
        ORDER BY timestamp DESC
        LIMIT 1
      `)
      if (priceResult.rows[0]) price = { btc_price: priceResult.rows[0].btc_price, btc_24h_change: null }
    } catch (e) {
      console.log('[EC-018] Price query failed, using default')
    }

    // Get current DEFCON level (with fallback)
    let defcon = { defcon_level: 5 }
    try {
      const defconResult = await client.query(`
        SELECT current_level as defcon_level
        FROM fhq_governance.defcon_status
        ORDER BY changed_at DESC
        LIMIT 1
      `)
      if (defconResult.rows[0]) defcon = defconResult.rows[0]
    } catch (e) {
      console.log('[EC-018] DEFCON query failed, using default')
    }

    // Get today's LLM spend (with fallback)
    let spent = 0
    try {
      const budgetResult = await client.query(`
        SELECT COALESCE(SUM(cost_usd), 0)::float as spent_today
        FROM fhq_governance.llm_routing_log
        WHERE DATE(timestamp_utc) = CURRENT_DATE
          AND agent_id = 'EC-018'
      `)
      spent = budgetResult.rows[0]?.spent_today || 0
    } catch (e) {
      console.log('[EC-018] Budget query failed, using default')
    }

    const daily_budget_remaining = Math.max(0, BUDGET_CAP_USD - spent)

    // Build state object
    const stateData = {
      captured_at: new Date().toISOString(),
      market_regime: regime.market_regime,
      regime_confidence: Number(regime.regime_confidence) || 0.5,
      btc_price: price.btc_price ? Number(price.btc_price) : null,
      btc_24h_change: price.btc_24h_change ? Number(price.btc_24h_change) : null,
      vix_value: null, // TODO: Add VIX from macro data
      defcon_level: Number(defcon.defcon_level) || 5,
      daily_budget_remaining,
    }

    // Compute cryptographic state hash (ADR-018)
    const state_hash = computeStateHash(stateData)

    // Insert state vector
    const insertResult = await client.query(`
      INSERT INTO fhq_alpha.state_vectors (
        state_hash,
        market_regime,
        regime_confidence,
        btc_price,
        btc_24h_change,
        vix_value,
        defcon_level,
        daily_budget_remaining,
        daily_budget_cap,
        source_agent
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'EC-018')
      RETURNING state_vector_id, state_hash, created_at
    `, [
      state_hash,
      stateData.market_regime,
      stateData.regime_confidence,
      stateData.btc_price,
      stateData.btc_24h_change,
      stateData.vix_value,
      stateData.defcon_level,
      daily_budget_remaining,
      BUDGET_CAP_USD
    ])

    return {
      state_vector_id: insertResult.rows[0].state_vector_id,
      state_hash: insertResult.rows[0].state_hash,
      captured_at: insertResult.rows[0].created_at,
      ...stateData
    }
  } finally {
    client.release()
  }
}

// ============================================================================
// DeepSeek Hypothesis Generation
// ============================================================================

async function generateHypotheses(
  stateVector: StateVector,
  focusAreas: string[],
  sessionId: string
): Promise<{ proposals: G0Proposal[], tokens_in: number, tokens_out: number, cost_usd: number }> {

  const systemPrompt = `You are EC-018, the Meta-Alpha & Freedom Optimizer for FjordHQ.
Your role is to generate FALSIFIABLE alpha hypotheses (G0 Draft Proposals).

CONSTITUTIONAL CONSTRAINTS:
- You have ZERO execution authority
- All outputs are hypotheses only - they require validation through IoS-004 backtest
- Pipeline: EC-018 → IoS-004 (backtest) → IoS-008 (decision) → IoS-012 (execution)

CURRENT MARKET STATE (ADR-018 State-Locked):
- State Hash: ${stateVector.state_hash.substring(0, 16)}...
- Regime: ${stateVector.market_regime} (confidence: ${(stateVector.regime_confidence * 100).toFixed(1)}%)
- BTC Price: ${stateVector.btc_price ? `$${stateVector.btc_price.toFixed(2)}` : 'N/A'}
- 24h Change: ${stateVector.btc_24h_change ? `${stateVector.btc_24h_change.toFixed(2)}%` : 'N/A'}
- DEFCON Level: ${stateVector.defcon_level}
- Budget Remaining: $${stateVector.daily_budget_remaining.toFixed(4)}

FOCUS AREAS: ${focusAreas.length > 0 ? focusAreas.join(', ') : 'General alpha discovery'}

OUTPUT FORMAT (JSON array):
[
  {
    "hypothesis_title": "Short descriptive title",
    "hypothesis_category": "REGIME_EDGE|CROSS_ASSET|TIMING|STRUCTURAL",
    "hypothesis_statement": "Clear, falsifiable claim about market behavior",
    "confidence_score": 0.0-1.0,
    "expected_edge_bps": integer (basis points),
    "executive_summary": "Human-readable explanation: Why is this smart? What's the insight?",
    "falsifiability_statement": "Specific criteria that would prove this wrong",
    "supporting_evidence": ["evidence1", "evidence2"],
    "risk_factors": ["risk1", "risk2"],
    "backtest_requirements": {"lookback_days": N, "min_samples": N}
  }
]

Generate 2-4 high-quality hypotheses. Quality over quantity.`

  const userPrompt = `Based on the current market state, generate G0 alpha hypotheses.
Focus on opportunities that can be validated through historical backtesting.
Remember: These are hypotheses, not recommendations. They require IoS-004 validation.`

  try {
    const apiKey = process.env.DEEPSEEK_API_KEY
    console.log('[EC-018] DeepSeek API key present:', !!apiKey, apiKey ? `(${apiKey.substring(0, 8)}...)` : '(missing)')

    if (!apiKey) {
      console.error('[EC-018] DEEPSEEK_API_KEY not found in environment')
      return { proposals: [], tokens_in: 0, tokens_out: 0, cost_usd: 0 }
    }

    const response = await fetch(DEEPSEEK_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: DEEPSEEK_MODEL,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userPrompt }
        ],
        temperature: 0.7,
        max_tokens: 4000,
      }),
    })

    if (!response.ok) {
      throw new Error(`DeepSeek API error: ${response.status}`)
    }

    const data = await response.json()
    const tokens_in = data.usage?.prompt_tokens || 0
    const tokens_out = data.usage?.completion_tokens || 0
    const cost_usd = (tokens_in / 1000 * COST_PER_1K_INPUT) + (tokens_out / 1000 * COST_PER_1K_OUTPUT)

    // Parse response
    const content = data.choices?.[0]?.message?.content || '[]'
    let hypotheses: any[] = []

    try {
      // Extract JSON from response (handle markdown code blocks)
      const jsonMatch = content.match(/\[[\s\S]*\]/)
      if (jsonMatch) {
        hypotheses = JSON.parse(jsonMatch[0])
      }
    } catch (parseError) {
      console.error('[EC-018] Failed to parse hypotheses:', parseError)
      hypotheses = []
    }

    // Convert to G0Proposals with state-lock
    const proposals: G0Proposal[] = hypotheses.map((h: any) => ({
      proposal_id: crypto.randomUUID(),
      hypothesis_id: generateHypothesisId(),
      hypothesis_title: h.hypothesis_title || 'Untitled Hypothesis',
      hypothesis_category: h.hypothesis_category || 'STRUCTURAL',
      hypothesis_statement: h.hypothesis_statement || '',
      confidence_score: Math.min(1, Math.max(0, h.confidence_score || 0.5)),
      executive_summary: h.executive_summary || '',
      falsifiability_statement: h.falsifiability_statement || '',
      state_hash_at_creation: stateVector.state_hash,
      defcon_at_generation: stateVector.defcon_level,
      downstream_pipeline: ['IoS-004', 'IoS-008', 'IoS-012'],
      supporting_evidence: h.supporting_evidence || [],
      risk_factors: h.risk_factors || [],
      expected_edge_bps: h.expected_edge_bps || null,
      backtest_requirements: h.backtest_requirements || null,
    }))

    return { proposals, tokens_in, tokens_out, cost_usd }
  } catch (error) {
    console.error('[EC-018] DeepSeek call failed:', error)
    return { proposals: [], tokens_in: 0, tokens_out: 0, cost_usd: 0 }
  }
}

// ============================================================================
// Store G0 Proposals (Per-Artifact State-Lock)
// ============================================================================

async function storeProposals(
  proposals: G0Proposal[],
  sessionId: string,
  stateVectorId: string,
  tokens: number,
  cost: number
): Promise<void> {
  const client = await pool.connect()
  try {
    for (const p of proposals) {
      await client.query(`
        INSERT INTO fhq_alpha.g0_draft_proposals (
          proposal_id,
          hunt_session_id,
          hypothesis_id,
          hypothesis_title,
          hypothesis_category,
          hypothesis_statement,
          confidence_score,
          executive_summary,
          falsification_criteria,
          backtest_requirements,
          execution_authority,
          downstream_pipeline,
          state_vector_id,
          state_hash_at_creation
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
      `, [
        p.proposal_id,
        sessionId,
        p.hypothesis_id,
        sanitizeForDb(p.hypothesis_title),
        p.hypothesis_category,
        sanitizeForDb(p.hypothesis_statement),
        p.confidence_score,
        sanitizeForDb(p.executive_summary),
        JSON.stringify({ statement: sanitizeForDb(p.falsifiability_statement) }),
        JSON.stringify(p.backtest_requirements || {}),
        'NONE', // execution_authority - HARD CONSTRAINT
        JSON.stringify(p.downstream_pipeline),
        stateVectorId,
        p.state_hash_at_creation
      ])
    }
  } finally {
    client.release()
  }
}

// ============================================================================
// Main Handler
// ============================================================================

export async function POST(request: NextRequest) {
  try {
    const body: HuntRequest = await request.json()
    const focusAreas = body.focus_areas || []
    const budgetCap = Math.min(body.budget_cap_usd || BUDGET_CAP_USD, BUDGET_CAP_USD)
    const initiatedBy = body.initiated_by || 'CEO'

    // Step 1: Capture current state vector (ADR-018)
    const stateVector = await captureStateVector()

    // Check budget
    if (stateVector.daily_budget_remaining <= 0) {
      return NextResponse.json({
        success: false,
        error: 'Daily budget exhausted',
        state_vector: stateVector,
      }, { status: 429 })
    }

    // Step 2: Create hunt session
    const sessionId = crypto.randomUUID()
    const client = await pool.connect()
    try {
      await client.query(`
        INSERT INTO fhq_alpha.hunt_sessions (
          session_id,
          session_name,
          initiated_by,
          focus_areas,
          budget_cap_usd,
          primary_model,
          initial_state_vector_id,
          session_status
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'ACTIVE')
      `, [
        sessionId,
        `Alpha Hunt ${new Date().toISOString()}`,
        initiatedBy,
        JSON.stringify(focusAreas),
        budgetCap,
        DEEPSEEK_MODEL,
        stateVector.state_vector_id,
      ])
    } finally {
      client.release()
    }

    // Step 3: Generate hypotheses
    const { proposals, tokens_in, tokens_out, cost_usd } = await generateHypotheses(
      stateVector,
      focusAreas,
      sessionId
    )

    // Step 4: Store proposals with per-artifact state-lock
    if (proposals.length > 0) {
      await storeProposals(proposals, sessionId, stateVector.state_vector_id, tokens_in + tokens_out, cost_usd)
    }

    // Step 5: Update session with results
    const clientUpdate = await pool.connect()
    try {
      await clientUpdate.query(`
        UPDATE fhq_alpha.hunt_sessions
        SET
          session_status = 'COMPLETED',
          completed_at = NOW(),
          total_tokens_in = $2,
          total_tokens_out = $3,
          total_cost_usd = $4,
          hypotheses_generated = $5,
          session_metadata = $6
        WHERE session_id = $1
      `, [
        sessionId,
        tokens_in,
        tokens_out,
        cost_usd,
        proposals.length,
        JSON.stringify({
          focus_areas: focusAreas,
          state_hash: stateVector.state_hash,
          defcon_level: stateVector.defcon_level,
          regime: stateVector.market_regime,
        }),
      ])
    } finally {
      clientUpdate.release()
    }

    // Step 6: Log telemetry (with proper schema compliance)
    try {
      const clientTelemetry = await pool.connect()
      try {
        await clientTelemetry.query(`
          INSERT INTO fhq_governance.llm_routing_log (
            agent_id,
            request_timestamp,
            requested_provider,
            requested_tier,
            routed_provider,
            routed_tier,
            policy_satisfied,
            violation_detected,
            model,
            tokens_in,
            tokens_out,
            cost_usd,
            task_type
          ) VALUES ('FINN', NOW(), 'DEEPSEEK', 2, 'DEEPSEEK', 2, TRUE, FALSE, $1, $2, $3, $4, 'RESEARCH')
        `, [
          DEEPSEEK_MODEL,
          tokens_in,
          tokens_out,
          cost_usd,
        ])
      } finally {
        clientTelemetry.release()
      }
    } catch (telemetryError) {
      console.log('[EC-018] Telemetry logging failed (non-critical):', telemetryError)
    }

    return NextResponse.json({
      success: true,
      session_id: sessionId,
      state_vector: {
        id: stateVector.state_vector_id,
        hash: stateVector.state_hash,
        captured_at: stateVector.captured_at,
        regime: stateVector.market_regime,
        defcon: stateVector.defcon_level,
      },
      proposals: proposals.map(p => ({
        id: p.proposal_id,
        hypothesis_id: p.hypothesis_id,
        title: p.hypothesis_title,
        category: p.hypothesis_category,
        statement: p.hypothesis_statement,
        confidence: p.confidence_score,
        executive_summary: p.executive_summary,
        falsifiability: p.falsifiability_statement,
        state_lock: {
          hash: p.state_hash_at_creation,
          defcon: p.defcon_at_generation,
        },
        pipeline: p.downstream_pipeline,
      })),
      telemetry: {
        tokens_in,
        tokens_out,
        cost_usd,
        budget_remaining: stateVector.daily_budget_remaining - cost_usd,
      },
      governance: {
        execution_authority: 'NONE',
        requires_validation: true,
        next_step: 'IoS-004 Backtest',
      },
    })

  } catch (error) {
    console.error('[EC-018] Alpha hunt failed:', error)
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    }, { status: 500 })
  }
}

// GET - Retrieve recent proposals with backtest results
export async function GET(request: NextRequest) {
  try {
    const client = await pool.connect()
    try {
      const result = await client.query(`
        SELECT
          p.proposal_id,
          p.hypothesis_id,
          p.hypothesis_title,
          p.hypothesis_category,
          p.hypothesis_statement,
          p.confidence_score,
          p.executive_summary,
          p.falsification_criteria,
          p.proposal_status,
          p.state_hash_at_creation,
          p.created_at,
          COALESCE(s.state_hash, p.state_hash_at_creation) as state_hash,
          COALESCE(s.market_regime, 'NEUTRAL') as market_regime,
          COALESCE(s.defcon_level, 4) as defcon_level,
          -- Backtest results from IoS-004
          b.validation_outcome as backtest_outcome,
          b.win_rate as backtest_win_rate,
          b.sharpe_ratio as backtest_sharpe,
          b.total_signals as backtest_samples,
          b.rejection_reason as backtest_rejection_reason,
          b.backtest_completed_at,
          -- Queue status
          q.status as queue_status
        FROM fhq_alpha.g0_draft_proposals p
        LEFT JOIN fhq_alpha.state_vectors s ON p.state_vector_id = s.state_vector_id
        LEFT JOIN fhq_alpha.backtest_results b ON p.proposal_id = b.proposal_id
        LEFT JOIN fhq_alpha.backtest_queue q ON p.proposal_id = q.proposal_id
        ORDER BY p.created_at DESC
        LIMIT 20
      `)

      return NextResponse.json({
        success: true,
        proposals: result.rows.map(r => ({
          proposal_id: r.proposal_id,
          hypothesis_id: r.hypothesis_id,
          hypothesis_title: r.hypothesis_title,
          hypothesis_category: r.hypothesis_category || 'STRUCTURAL',
          hypothesis_statement: r.hypothesis_statement,
          confidence_score: r.confidence_score ? Number(r.confidence_score) : 0.5,
          expected_edge_bps: 0,
          executive_summary: r.executive_summary,
          risk_factors: [],
          proposal_status: r.proposal_status,
          created_at: r.created_at,
          expires_at: r.created_at,
          falsifiability_validated: false,
          falsifiability_statement: r.falsification_criteria?.statement || '',
          downstream_pipeline: ['IoS-004', 'IoS-008', 'IoS-012'],
          state_lock: {
            state_hash: r.state_hash || r.state_hash_at_creation || '',
            defcon_at_generation: Number(r.defcon_level) || 4,
            regime_at_generation: r.market_regime || 'NEUTRAL',
            captured_at: r.created_at,
          },
          // Backtest info from IoS-004
          backtest: r.backtest_outcome ? {
            outcome: r.backtest_outcome,
            win_rate: r.backtest_win_rate != null ? Number(r.backtest_win_rate) : null,
            sharpe: r.backtest_sharpe != null ? Number(r.backtest_sharpe) : null,
            samples: r.backtest_samples != null ? Number(r.backtest_samples) : null,
            rejection_reason: r.backtest_rejection_reason || null,
            completed_at: r.backtest_completed_at,
          } : null,
          queue_status: r.queue_status || 'NOT_QUEUED',
        })),
      })
    } finally {
      client.release()
    }
  } catch (error) {
    console.error('[EC-018] Failed to retrieve proposals:', error)
    return NextResponse.json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    }, { status: 500 })
  }
}
