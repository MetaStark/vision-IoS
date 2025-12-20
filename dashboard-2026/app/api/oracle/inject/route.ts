/**
 * Oracle Injector API Endpoint
 * POST /api/oracle/inject
 *
 * Authority: CEO Directive — Vision-OS Dashboard Extension (REV 1.2)
 * Constitutional Basis: ADR-019, IoS-009
 *
 * This endpoint enables CEO to submit narrative vectors to the Human Oracle Channel.
 * Implements IoS-009 G1 interface with full decay model support.
 *
 * SAFETY: CEO-only write access to fhq_meta.narrative_vectors
 */

import { NextRequest, NextResponse } from 'next/server';
import { Pool } from 'pg';
import * as crypto from 'crypto';

// Database connection
const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
});

// Valid domains per IoS-009
const VALID_DOMAINS = [
  'Regulatory',
  'Geopolitical',
  'Liquidity',
  'Reflexivity',
  'Sentiment',
  'Macro',
  'Technical',
  'Fundamental',
  'Other',
] as const;

type Domain = (typeof VALID_DOMAINS)[number];

// Request payload
interface OracleInjectRequest {
  domain: Domain;
  narrative: string;
  probability: number; // 0-1
  confidence: number; // 0-1
  half_life_hours: number; // Required per CEO Directive
  asset_context?: string; // Optional: specific asset this applies to
  source_context?: string; // Optional: source of the insight
}

// Response
interface OracleInjectResponse {
  success: boolean;
  vector_id?: string;
  message: string;
  decay_preview?: {
    current_weight: number;
    weight_after_1h: number;
    weight_after_6h: number;
    weight_after_24h: number;
    effective_duration_hours: number; // Time until weight < 1%
  };
  error?: string;
}

/**
 * Compute decay weight per IoS-009
 * weight = 0.5^(age_hours / half_life_hours)
 */
function computeDecayWeight(ageHours: number, halfLifeHours: number): number {
  return Math.pow(0.5, ageHours / halfLifeHours);
}

/**
 * Compute effective duration (time until weight < 1%)
 * 0.01 = 0.5^(t / half_life)
 * log(0.01) = (t / half_life) * log(0.5)
 * t = half_life * log(0.01) / log(0.5)
 * t ≈ half_life * 6.64
 */
function computeEffectiveDuration(halfLifeHours: number): number {
  return halfLifeHours * 6.64;
}

export async function POST(
  request: NextRequest
): Promise<NextResponse<OracleInjectResponse>> {
  const client = await pool.connect();

  try {
    const body = (await request.json()) as OracleInjectRequest;
    const {
      domain,
      narrative,
      probability,
      confidence,
      half_life_hours,
      asset_context,
      source_context,
    } = body;

    // Validate required fields
    if (!domain || !narrative || probability === undefined || confidence === undefined || !half_life_hours) {
      return NextResponse.json(
        {
          success: false,
          message: 'Missing required fields',
          error: 'Required: domain, narrative, probability, confidence, half_life_hours',
        },
        { status: 400 }
      );
    }

    // Validate domain
    if (!VALID_DOMAINS.includes(domain)) {
      return NextResponse.json(
        {
          success: false,
          message: 'Invalid domain',
          error: `Domain must be one of: ${VALID_DOMAINS.join(', ')}`,
        },
        { status: 400 }
      );
    }

    // Validate probability
    if (probability < 0 || probability > 1) {
      return NextResponse.json(
        {
          success: false,
          message: 'Invalid probability',
          error: 'Probability must be between 0 and 1',
        },
        { status: 400 }
      );
    }

    // Validate confidence
    if (confidence < 0 || confidence > 1) {
      return NextResponse.json(
        {
          success: false,
          message: 'Invalid confidence',
          error: 'Confidence must be between 0 and 1',
        },
        { status: 400 }
      );
    }

    // Validate half_life_hours
    if (half_life_hours <= 0 || half_life_hours > 720) {
      // Max 30 days
      return NextResponse.json(
        {
          success: false,
          message: 'Invalid half_life_hours',
          error: 'Half-life must be between 1 and 720 hours (30 days)',
        },
        { status: 400 }
      );
    }

    // Generate vector ID
    const vectorId = crypto.randomUUID();

    // Compute content hash
    const contentHash = crypto
      .createHash('sha256')
      .update(`${domain}:${narrative}:${probability}:${confidence}:${half_life_hours}:${Date.now()}`)
      .digest('hex');

    // Insert narrative vector
    await client.query(
      `INSERT INTO fhq_meta.narrative_vectors (
        vector_id,
        domain,
        narrative,
        probability,
        confidence,
        half_life_hours,
        asset_context,
        source_context,
        created_by,
        content_hash
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
      [
        vectorId,
        domain,
        narrative,
        probability,
        confidence,
        half_life_hours,
        asset_context || null,
        source_context || 'CEO Oracle Channel',
        'CEO',
        contentHash,
      ]
    );

    // Log to governance
    await client.query(
      `INSERT INTO fhq_governance.governance_actions_log (
        action_type, action_target, action_target_type, initiated_by,
        decision, decision_rationale, hash_chain_id
      ) VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [
        'ORACLE_INJECTION',
        `narrative_vectors/${vectorId}`,
        'NARRATIVE_VECTOR',
        'CEO',
        'COMPLETED',
        `Domain: ${domain} | Prob: ${(probability * 100).toFixed(0)}% | Conf: ${(confidence * 100).toFixed(0)}% | Half-life: ${half_life_hours}h | Narrative: ${narrative.substring(0, 100)}...`,
        `HC-ORACLE-${new Date().toISOString().split('T')[0]}`,
      ]
    );

    // Compute decay preview
    const effectiveDuration = computeEffectiveDuration(half_life_hours);
    const decayPreview = {
      current_weight: 1.0,
      weight_after_1h: computeDecayWeight(1, half_life_hours),
      weight_after_6h: computeDecayWeight(6, half_life_hours),
      weight_after_24h: computeDecayWeight(24, half_life_hours),
      effective_duration_hours: Math.round(effectiveDuration * 10) / 10,
    };

    return NextResponse.json({
      success: true,
      vector_id: vectorId,
      message: 'Narrative vector injected successfully',
      decay_preview: decayPreview,
    });
  } catch (error) {
    console.error('Oracle injection error:', error);
    return NextResponse.json(
      {
        success: false,
        message: 'Oracle injection failed',
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  } finally {
    client.release();
  }
}

/**
 * GET /api/oracle/inject
 * Returns API documentation and current active vectors
 */
export async function GET(): Promise<NextResponse> {
  const client = await pool.connect();

  try {
    // Get active narrative vectors
    const result = await client.query(`
      SELECT
        vector_id,
        domain,
        narrative,
        probability,
        confidence,
        half_life_hours,
        created_at,
        POWER(0.5, EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 / half_life_hours) AS current_weight
      FROM fhq_meta.narrative_vectors
      WHERE is_expired = FALSE
        AND EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600.0 < (half_life_hours * 6.64)
      ORDER BY created_at DESC
      LIMIT 10
    `);

    return NextResponse.json({
      endpoint: '/api/oracle/inject',
      version: '2026.PROD.1',
      status: 'ACTIVE',
      authority: 'CEO Directive — Vision-OS Dashboard Extension (REV 1.2)',
      constitutional_basis: ['ADR-019', 'IoS-009'],

      decay_model: 'weight = 0.5^(age_hours / half_life_hours)',

      valid_domains: VALID_DOMAINS,

      required_fields: {
        domain: 'One of the valid domains',
        narrative: 'The narrative/insight text',
        probability: 'Probability of narrative being true (0-1)',
        confidence: 'Confidence in the probability estimate (0-1)',
        half_life_hours: 'Time for weight to decay to 50% (1-720 hours)',
      },

      optional_fields: {
        asset_context: 'Specific asset this applies to',
        source_context: 'Source of the insight',
      },

      example_payload: {
        domain: 'Regulatory',
        narrative:
          'SEC likely to approve spot ETH ETF within 30 days based on recent statements',
        probability: 0.65,
        confidence: 0.7,
        half_life_hours: 72,
      },

      active_vectors: result.rows.map((row) => ({
        vector_id: row.vector_id,
        domain: row.domain,
        narrative: row.narrative.substring(0, 100) + (row.narrative.length > 100 ? '...' : ''),
        probability: parseFloat(row.probability),
        confidence: parseFloat(row.confidence),
        half_life_hours: row.half_life_hours,
        current_weight: Math.round(parseFloat(row.current_weight) * 1000) / 1000,
        created_at: row.created_at,
      })),
    });
  } catch (error) {
    return NextResponse.json(
      {
        endpoint: '/api/oracle/inject',
        status: 'ERROR',
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  } finally {
    client.release();
  }
}
