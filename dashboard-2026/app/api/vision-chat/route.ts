/**
 * VisionChat API Endpoint
 * POST /api/vision-chat
 *
 * Authority: CEO Directive — Vision-OS Dashboard Extension (REV 1.2)
 * Authority: CEO DIRECTIVE — Schema Hallucination Fix (2025-12-07)
 * Constitutional Basis: ADR-019, IoS-009
 *
 * This endpoint provides Claude 3.5 Sonnet inquiry channel with:
 * - ceo_read_only SQL connectivity
 * - SQL preview window
 * - Analytics rendering
 * - Governance logging
 * - SCHEMA INJECTION: Canonical DDL fetched from database (anti-hallucination)
 *
 * SAFETY: Read-only. No modifications permitted.
 */

import { NextRequest, NextResponse } from 'next/server';
import { Pool } from 'pg';
import Anthropic from '@anthropic-ai/sdk';

// Database connection using ceo_read_only role conceptually
const pool = new Pool({
  host: process.env.PGHOST || '127.0.0.1',
  port: parseInt(process.env.PGPORT || '54322'),
  database: process.env.PGDATABASE || 'postgres',
  user: process.env.PGUSER || 'postgres',
  password: process.env.PGPASSWORD || 'postgres',
});

// Anthropic client
const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

// ============================================================================
// CANONICAL TABLE MAP (CEO DIRECTIVE — Schema Hallucination Fix)
// These are the VERIFIED column names. NEVER guess or hallucinate columns.
// Standard timestamp: created_at (NOT created_date, NOT creation_date)
// ============================================================================
const CANONICAL_TABLE_MAP = `
## CANONICAL TABLE MAP — VERIFIED COLUMN NAMES

### fhq_meta.ios_registry
- ios_id (TEXT, PK)
- title (TEXT)
- version (TEXT)
- status (TEXT: 'DRAFT'|'ACTIVE'|'DEPRECATED')
- description (TEXT)
- owner_agent (TEXT)
- created_at (TIMESTAMPTZ) ← CANONICAL TIMESTAMP
- updated_at (TIMESTAMPTZ)

### fhq_meta.adr_registry
- adr_id (TEXT, PK)
- adr_title (TEXT)
- adr_status (TEXT)
- effective_date (DATE)
- supersedes (TEXT)
- created_at (TIMESTAMPTZ) ← CANONICAL TIMESTAMP

### fhq_meta.narrative_vectors
- vector_id (UUID, PK)
- domain (TEXT)
- narrative (TEXT)
- probability (NUMERIC)
- confidence (NUMERIC)
- half_life_hours (INTEGER)
- is_expired (BOOLEAN)
- created_by (TEXT)
- created_at (TIMESTAMPTZ) ← CANONICAL TIMESTAMP

### fhq_governance.shared_state_snapshots
- snapshot_id (UUID, PK)
- state_vector_hash (TEXT)
- defcon_level (TEXT)
- btc_regime_label (TEXT) ← NOT "current_regime"
- is_valid (BOOLEAN)
- created_at (TIMESTAMPTZ)

### fhq_governance.governance_actions_log
- action_id (UUID, PK)
- action_type (TEXT)
- action_target (TEXT)
- action_target_type (TEXT)
- initiated_by (TEXT)
- initiated_at (TIMESTAMPTZ) ← NOTE: uses initiated_at, not created_at
- decision (TEXT) ← VALID: 'APPROVED'|'REJECTED'|'DEFERRED'|'ESCALATED'|'IN_PROGRESS'|'COMPLETED'|'COMPLETED_WITH_FAILURES'|'FAILED'
- decision_rationale (TEXT)
- vega_reviewed (BOOLEAN)
- vega_override (BOOLEAN)
- vega_notes (TEXT)
- hash_chain_id (TEXT)
- signature_id (UUID)

### fhq_data.price_history
- price_id (SERIAL, PK)
- asset_id (TEXT)
- price_date (DATE)
- open_price (NUMERIC)
- high_price (NUMERIC)
- low_price (NUMERIC)
- close_price (NUMERIC)
- volume (BIGINT)
- created_at (TIMESTAMPTZ)

### fhq_research.regime_predictions [DEPRECATED - DO NOT USE]
- prediction_id (UUID, PK)
- asset_id (TEXT)
- prediction_date (DATE)
- regime_label (TEXT)
- confidence (NUMERIC)
- model_version (TEXT)
- created_at (TIMESTAMPTZ)
WARNING: This table is DEPRECATED per ADR-013. Use fhq_perception.regime_daily instead.

## CANONICAL PERCEPTION LAYER (IoS-003) - PRIMARY SOURCE FOR REGIME DATA

### fhq_perception.regime_daily [PRIMARY REGIME SOURCE]
- id (UUID, PK)
- asset_id (TEXT)
- timestamp (DATE)
- regime_classification (TEXT) <- USE THIS for regime queries
- regime_stability_flag (BOOLEAN)
- regime_confidence (NUMERIC)
- consecutive_confirms (INTEGER)
- prior_regime (TEXT)
- regime_change_date (DATE)
- anomaly_flag (BOOLEAN)
- anomaly_type (TEXT)
- anomaly_severity (TEXT)
- engine_version (TEXT)
- perception_model_version (TEXT)
- formula_hash (TEXT)
- lineage_hash (TEXT)
- hash_prev (TEXT)
- hash_self (TEXT)
- created_at (TIMESTAMPTZ)

### fhq_perception.state_vectors
- id (UUID, PK)
- asset_id (TEXT)
- timestamp (DATE)
- trend_score (NUMERIC)
- momentum_score (NUMERIC)
- volatility_score (NUMERIC)
- confidence_score (NUMERIC)
- final_score (NUMERIC)
- trend_weight (NUMERIC)
- momentum_weight (NUMERIC)
- volatility_weight (NUMERIC)
- component_scores (JSONB)
- semantic_context_summary (TEXT)
- regime_classification (TEXT)
- regime_daily_id (UUID, FK)
- engine_version (TEXT)
- perception_model_version (TEXT)
- formula_hash (TEXT)
- lineage_hash (TEXT)
- created_at (TIMESTAMPTZ)

### fhq_perception.anomaly_log
- id (UUID, PK)
- asset_id (TEXT)
- timestamp (TIMESTAMPTZ)
- detection_date (DATE)
- anomaly_type (TEXT)
- severity (TEXT)
- description (TEXT)
- trigger_values (JSONB)
- threshold_breached (TEXT)
- deviation_magnitude (NUMERIC)
- z_score (NUMERIC)
- affected_indicators (TEXT[])
- perception_impact (TEXT)
- regime_impact (TEXT)
- resolution_status (TEXT)
- resolved_at (TIMESTAMPTZ)
- resolved_by (TEXT)
- defcon_triggered (BOOLEAN)
- defcon_level (TEXT)
- created_at (TIMESTAMPTZ)

### fhq_governance.oracle_staging
- submission_id (UUID, PK)
- domain (TEXT)
- narrative (TEXT)
- probability (NUMERIC)
- confidence (NUMERIC)
- half_life_hours (INTEGER)
- submitted_by (TEXT)
- submitted_at (TIMESTAMPTZ)
- review_status (TEXT)
- reviewed_by (TEXT)
- reviewed_at (TIMESTAMPTZ)
`;

// Base system prompt with Executive Interface persona (CEO DIRECTIVE)
const BASE_SYSTEM_PROMPT = `You are the FjordHQ Executive Interface — the CEO's direct query channel into the FjordHQ Market System.

## IDENTITY & ROLE
You are NOT a general AI assistant. You are a specialized Executive Interface providing:
- Direct read-only access to the FjordHQ database via ceo_read_only role
- Accurate, data-driven intelligence from canonical database tables
- SQL query execution with full transparency
- Governance-compliant reporting per ADR-019

## CRITICAL ANTI-HALLUCINATION RULES
1. ONLY reference tables and columns that EXIST in the canonical schema below
2. NEVER guess column names — use ONLY the verified names provided
3. Standard timestamp column is "created_at" — NOT "created_date", NOT "creation_date"
4. If unsure about a column, query information_schema.columns first
5. When writing SQL, ALWAYS use the exact column names from the canonical map

## ADR-013 CANONICAL ROUTING RULES (MANDATORY)
REGIME DATA ROUTING:
- PRIMARY SOURCE: fhq_perception.regime_daily (IoS-003 output)
- SECONDARY: fhq_perception.state_vectors (for detailed scores)
- ANOMALIES: fhq_perception.anomaly_log

DEPRECATED - DO NOT USE FOR REGIME QUERIES:
- fhq_research.regime_predictions (legacy, non-canonical)

ROUTING ENFORCEMENT:
- All regime queries MUST use fhq_perception.regime_daily
- For current regime: SELECT regime_classification FROM fhq_perception.regime_daily WHERE asset_id = 'BTC-USD' ORDER BY timestamp DESC LIMIT 1
- For regime history: Query fhq_perception.regime_daily with date range
- NEVER use fhq_research for operative/production regime questions

NON-CANONICAL DATA WARNING:
- If data is older than 30 days, flag as potentially stale
- If querying deprecated tables, warn: "NON-CANONICAL DATA SOURCE DETECTED - ADR-013 violation"

## IoS-001 CANONICAL ASSET IDENTIFIER MAP (MANDATORY)
The ONLY valid asset_id values in the FjordHQ system are:
- **BTC-USD** (Bitcoin) - NOT 'BTC', NOT 'BTCUSD'
- **ETH-USD** (Ethereum) - NOT 'ETH', NOT 'ETHUSD'
- **SOL-USD** (Solana) - NOT 'SOL', NOT 'SOLUSD'
- **EURUSD** (Euro/Dollar forex pair)

**CRITICAL:** When querying regime data, you MUST use the exact canonical format:
- CORRECT: WHERE asset_id = 'BTC-USD'
- WRONG: WHERE asset_id = 'BTC' (will return zero rows and trigger hallucination)

If you receive zero rows, DO NOT generate fallback data. Report the zero-result condition.

## CONSTRAINTS
- READ-ONLY: Only SELECT queries permitted
- NO DDL: Cannot create, alter, or drop objects
- NO DML: Cannot INSERT, UPDATE, or DELETE
- GOVERNANCE: All queries logged per ADR-002

## RESPONSE FORMAT
- Be concise and data-driven
- Show SQL queries in \`\`\`sql blocks for transparency
- Format results as markdown tables
- Highlight actionable findings

## AVAILABLE SCHEMAS
- fhq_perception: [PRIMARY FOR REGIME] regime_daily, state_vectors, anomaly_log (IoS-003)
- fhq_meta: Asset registry, IoS registry, ADR registry, narrative vectors
- fhq_data: Price history, technical indicators, macro indicators
- fhq_research: [DEPRECATED FOR REGIME] forecasts, signals (NOT for regime queries)
- fhq_governance: Governance actions, state snapshots, oracle staging
- fhq_monitoring: System health metrics
`;

/**
 * Fetch canonical schema context from database
 * Per CEO DIRECTIVE: Never guess column structure
 */
async function fetchSchemaContext(): Promise<string> {
  try {
    const client = await pool.connect();
    try {
      const result = await client.query(`
        SELECT
          table_schema || '.' || table_name AS full_table,
          string_agg(column_name || ' (' || data_type || ')', ', ' ORDER BY ordinal_position) AS columns
        FROM information_schema.columns
        WHERE table_schema IN ('fhq_meta', 'fhq_governance', 'fhq_data', 'fhq_research', 'fhq_monitoring', 'fhq_perception')
          AND table_name IN (
            'ios_registry', 'adr_registry', 'narrative_vectors', 'asset_registry',
            'shared_state_snapshots', 'governance_actions_log', 'oracle_staging',
            'price_history', 'regime_predictions', 'technical_indicators',
            'regime_daily', 'state_vectors', 'anomaly_log'
          )
        GROUP BY table_schema, table_name
        ORDER BY table_schema, table_name
      `);

      if (result.rows.length === 0) {
        return '## Dynamic Schema: No tables found in query';
      }

      let schemaContext = '\n## LIVE DATABASE SCHEMA (from information_schema)\n';
      for (const row of result.rows) {
        schemaContext += `\n### ${row.full_table}\nColumns: ${row.columns}\n`;
      }
      return schemaContext;
    } finally {
      client.release();
    }
  } catch (error) {
    console.error('Schema fetch error:', error);
    return '## Dynamic Schema: Fetch failed, using canonical map only';
  }
}

/**
 * Build complete system prompt with schema injection
 */
async function buildSystemPrompt(): Promise<string> {
  const dynamicSchema = await fetchSchemaContext();
  return `${BASE_SYSTEM_PROMPT}

${CANONICAL_TABLE_MAP}

${dynamicSchema}

Remember: You are the FjordHQ Executive Interface. Provide accurate, verifiable intelligence using ONLY the columns documented above.`;
}

// Allowed SQL patterns (safety check)
const FORBIDDEN_PATTERNS = [
  /\bINSERT\b/i,
  /\bUPDATE\b/i,
  /\bDELETE\b/i,
  /\bDROP\b/i,
  /\bCREATE\b/i,
  /\bALTER\b/i,
  /\bTRUNCATE\b/i,
  /\bGRANT\b/i,
  /\bREVOKE\b/i,
  /\bEXECUTE\b/i,
  /\bCALL\b/i,
];

// ADR-013 Canonical Routing: Deprecated tables for regime queries
const DEPRECATED_REGIME_TABLES = [
  'fhq_research.regime_predictions',
  'regime_predictions',
];

// ============================================================================
// IoS-001 CANONICAL ASSET IDENTIFIER MAP (G1 PATCH - Canonical Pointer Drift Fix)
// These are the ONLY valid asset_id values in the FjordHQ system.
// ANY query using non-canonical identifiers (e.g., 'BTC' instead of 'BTC-USD')
// MUST be rejected as an ADR-013 violation.
// ============================================================================
const CANONICAL_ASSET_IDS = [
  'BTC-USD',
  'ETH-USD',
  'SOL-USD',
  'EURUSD',
];

// Invalid asset ID patterns that commonly cause hallucination
const INVALID_ASSET_PATTERNS = [
  /\basset_id\s*=\s*'BTC'/i,
  /\basset_id\s*=\s*'ETH'/i,
  /\basset_id\s*=\s*'SOL'/i,
  /\basset_id\s*=\s*'EUR'/i,
  /\basset_id\s*=\s*'USD'/i,
  /\basset_id\s*=\s*'BTCUSD'/i,
  /\basset_id\s*=\s*'ETHUSD'/i,
];

/**
 * Check for ADR-013 violations - non-canonical data source usage
 * Per CEO DIRECTIVE: Flag deprecated tables for regime queries
 * Per G1 PATCH: Also check for invalid asset identifiers (IoS-001 compliance)
 */
function checkCanonicalRouting(sql: string): { isViolation: boolean; warning: string | null; blockExecution: boolean } {
  const sqlLower = sql.toLowerCase();

  // G1 PATCH: Check for invalid asset identifiers (IoS-001 violation)
  for (const pattern of INVALID_ASSET_PATTERNS) {
    if (pattern.test(sql)) {
      return {
        isViolation: true,
        blockExecution: true,
        warning: `**IoS-001 VIOLATION: Invalid asset_id detected.**\n\nYour query uses a non-canonical asset identifier.\n\n**Valid asset_id values (IoS-001 canonical registry):**\n- BTC-USD\n- ETH-USD\n- SOL-USD\n- EURUSD\n\n**IMPORTANT:** Use 'BTC-USD' not 'BTC'. Use 'ETH-USD' not 'ETH'.\n\nQuery blocked to prevent hallucination fallback.`
      };
    }
  }

  // Check if querying deprecated regime tables
  for (const table of DEPRECATED_REGIME_TABLES) {
    if (sqlLower.includes(table.toLowerCase())) {
      // Check if this appears to be a regime-related query
      const regimeKeywords = ['regime', 'classification', 'prediction'];
      const isRegimeQuery = regimeKeywords.some(kw => sqlLower.includes(kw));

      if (isRegimeQuery) {
        return {
          isViolation: true,
          blockExecution: true,
          warning: `**ADR-013 VIOLATION: fhq_research is ARCHIVE and NOT canonical.**\n\nQueried: \`${table}\` (DEPRECATED)\nCanonical source: \`fhq_perception.regime_daily\`\n\nPer ADR-013, all regime queries must use the Perception Layer (IoS-003 output).`
        };
      }
    }
  }

  return { isViolation: false, warning: null, blockExecution: false };
}

function isSafeQuery(sql: string): boolean {
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (pattern.test(sql)) {
      return false;
    }
  }
  return true;
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface VisionChatRequest {
  message: string;
  history?: ChatMessage[];
}

interface VisionChatResponse {
  success: boolean;
  response?: string;
  sql_executed?: string[];
  error?: string;
}

// Execute SQL with safety checks, ADR-013 canonical routing, and zero-result backstop
async function executeSafeQuery(sql: string): Promise<{ rows: any[]; error?: string; adr013Warning?: string; zeroResultWarning?: string }> {
  if (!isSafeQuery(sql)) {
    return { rows: [], error: 'SAFETY VIOLATION: Only SELECT queries are permitted.' };
  }

  // Check ADR-013 canonical routing compliance (G1 PATCH)
  const routingCheck = checkCanonicalRouting(sql);

  // G1 PATCH: Block execution if canonical routing violation detected
  if (routingCheck.blockExecution) {
    return {
      rows: [],
      error: routingCheck.warning || 'Query blocked due to canonical routing violation.',
      adr013Warning: routingCheck.warning || undefined
    };
  }

  try {
    const client = await pool.connect();
    try {
      const result = await client.query(sql);

      // G1 PATCH: Zero-result backstop - prevent LLM fallback hallucination
      if (result.rows.length === 0) {
        // Check if this looks like a regime query that should have data
        const isRegimeQuery = sql.toLowerCase().includes('regime') ||
                             sql.toLowerCase().includes('fhq_perception');

        if (isRegimeQuery) {
          return {
            rows: [],
            zeroResultWarning: `**NO_CANONICAL_ROWS_FOUND**\n\nThe query returned zero rows. This may indicate:\n- Invalid query predicate (check asset_id format)\n- Data not yet available for requested date range\n- Table is empty\n\n**DO NOT generate fallback or estimated data.** Report the zero-result condition to the user.`,
            adr013Warning: routingCheck.warning || undefined
          };
        }
      }

      return {
        rows: result.rows,
        adr013Warning: routingCheck.warning || undefined
      };
    } finally {
      client.release();
    }
  } catch (error) {
    return { rows: [], error: error instanceof Error ? error.message : 'Query failed' };
  }
}

// Log inquiry to governance
async function logInquiry(
  message: string,
  response: string,
  sqlExecuted: string[]
): Promise<void> {
  try {
    const client = await pool.connect();
    try {
      await client.query(
        `INSERT INTO fhq_governance.governance_actions_log (
          action_type, action_target, action_target_type, initiated_by,
          decision, decision_rationale, hash_chain_id
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [
          'VISION_CHAT_INQUIRY',
          'VisionChat',
          'CEO_INQUIRY',
          'CEO',
          'COMPLETED',
          `Inquiry: ${message.substring(0, 200)}... | SQL count: ${sqlExecuted.length}`,
          `HC-VCHAT-${new Date().toISOString().split('T')[0]}`,
        ]
      );
    } finally {
      client.release();
    }
  } catch (error) {
    console.error('Failed to log inquiry:', error);
  }
}

// ============================================================================
// G2 PATCH: SQL-FIRST EXECUTION PIPELINE (CEO DIRECTIVE)
// Authority: ADR-013, ADR-007, ISO 8000-110
//
// ORDER OF OPERATIONS — GOLD STANDARD:
// 1. Execute SQL query FIRST
// 2. Validate data integrity (lineage, schema, row count)
// 3. Construct canonical Data Transfer Object (DTO)
// 4. Pass ONLY the DTO to LLM
// 5. Generate narrative AFTER seeing real data
// 6. Return narrative + SQL evidence drawer
//
// The LLM must NEVER generate narrative text without the SQL data object.
// ============================================================================

// IoS-001 Asset Resolver: Convert user input to canonical asset ID
function resolveCanonicalAssetId(userInput: string): string | null {
  const normalized = userInput.toUpperCase().trim();

  const assetMap: Record<string, string> = {
    'BTC': 'BTC-USD',
    'BITCOIN': 'BTC-USD',
    'BTC-USD': 'BTC-USD',
    'BTCUSD': 'BTC-USD',
    'ETH': 'ETH-USD',
    'ETHEREUM': 'ETH-USD',
    'ETH-USD': 'ETH-USD',
    'ETHUSD': 'ETH-USD',
    'SOL': 'SOL-USD',
    'SOLANA': 'SOL-USD',
    'SOL-USD': 'SOL-USD',
    'SOLUSD': 'SOL-USD',
    'EUR': 'EURUSD',
    'EURUSD': 'EURUSD',
    'EUR/USD': 'EURUSD',
  };

  return assetMap[normalized] || null;
}

// Extract asset references from user message
function extractAssetReferences(message: string): string[] {
  const assetPatterns = /\b(BTC|ETH|SOL|EUR|BITCOIN|ETHEREUM|SOLANA|BTC-USD|ETH-USD|SOL-USD|EURUSD)\b/gi;
  const matches = message.match(assetPatterns) || [];
  const resolved = matches.map(m => resolveCanonicalAssetId(m)).filter((id): id is string => id !== null);
  return [...new Set(resolved)]; // Remove duplicates
}

// Canonical Data Transfer Object (DTO) for query results
interface CanonicalDTO {
  query_executed: string;
  row_count: number;
  columns: string[];
  rows: Record<string, unknown>[];
  execution_timestamp: string;
  data_freshness_days: number | null;
  warnings: string[];
  is_valid: boolean;
}

// Build DTO from query results (G2 PATCH)
function buildCanonicalDTO(sql: string, result: { rows: any[]; error?: string; adr013Warning?: string; zeroResultWarning?: string }): CanonicalDTO {
  const warnings: string[] = [];

  if (result.error) {
    warnings.push(`QUERY_ERROR: ${result.error}`);
  }
  if (result.adr013Warning) {
    warnings.push(result.adr013Warning);
  }
  if (result.zeroResultWarning) {
    warnings.push(result.zeroResultWarning);
  }

  // Calculate data freshness if we have timestamp columns
  let dataFreshnessDays: number | null = null;
  if (result.rows.length > 0) {
    const timestampCols = ['created_at', 'timestamp', 'initiated_at', 'submitted_at'];
    for (const col of timestampCols) {
      if (result.rows[0][col]) {
        const dataDate = new Date(result.rows[0][col]);
        const now = new Date();
        dataFreshnessDays = Math.floor((now.getTime() - dataDate.getTime()) / (1000 * 60 * 60 * 24));
        break;
      }
    }
  }

  return {
    query_executed: sql,
    row_count: result.rows.length,
    columns: result.rows.length > 0 ? Object.keys(result.rows[0]) : [],
    rows: result.rows.slice(0, 50), // Limit to 50 rows for LLM context
    execution_timestamp: new Date().toISOString(),
    data_freshness_days: dataFreshnessDays,
    warnings,
    is_valid: !result.error && result.rows.length > 0,
  };
}

// Phase 1 System Prompt: SQL Generation ONLY
const SQL_GENERATION_PROMPT = `You are the FjordHQ SQL Generator. Your ONLY task is to generate a SQL query.

RULES:
1. Output ONLY a SQL query in a \`\`\`sql block
2. Do NOT generate any narrative, summary, or interpretation
3. Do NOT guess what the data might contain
4. Use ONLY canonical asset IDs: BTC-USD, ETH-USD, SOL-USD, EURUSD
5. Query fhq_perception.regime_daily for regime data (NOT fhq_research)

Output format:
\`\`\`sql
SELECT ... FROM ... WHERE ...
\`\`\`

Nothing else. No explanations. No summaries.`;

// Phase 2 System Prompt: Narrative Generation from DTO
const NARRATIVE_GENERATION_PROMPT = `You are the FjordHQ Executive Interface generating a data-anchored narrative.

CRITICAL RULES (G2 PATCH - ADR-013 Compliance):
1. You will receive a CANONICAL DATA OBJECT containing query results
2. You must ONLY report values that exist in this data object
3. You must NEVER invent, guess, or hallucinate any values
4. If a field is missing or null, report it as "not available"
5. If row_count is 0, report "No data found" - do NOT generate fallback data
6. Every number, date, and label in your response MUST come from the data object

RESPONSE FORMAT:
- Start with a brief summary of what the data shows
- List key findings with exact values from the data
- Note any warnings present in the data object
- Include data freshness if available

If no canonical data was provided, respond ONLY with:
"No canonical data received. Cannot interpret."`;

export async function POST(request: NextRequest): Promise<NextResponse<VisionChatResponse>> {
  try {
    const body = (await request.json()) as VisionChatRequest;
    const { message, history = [] } = body;

    if (!message) {
      return NextResponse.json(
        { success: false, error: 'Message is required' },
        { status: 400 }
      );
    }

    // G2 PATCH: Extract and resolve asset references BEFORE SQL generation
    const resolvedAssets = extractAssetReferences(message);
    const assetContext = resolvedAssets.length > 0
      ? `\n\nCanonical asset IDs to use: ${resolvedAssets.join(', ')}`
      : '';

    // Build schema context for SQL generation
    const schemaContext = await fetchSchemaContext();

    // ========================================================================
    // PHASE 1: SQL GENERATION (LLM generates SQL only, no narrative)
    // ========================================================================
    const sqlGenMessages: { role: 'user' | 'assistant'; content: string }[] = [
      ...history.slice(-4), // Keep limited history for context
      { role: 'user' as const, content: `${message}${assetContext}` },
    ];

    const sqlGenResponse = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      system: `${SQL_GENERATION_PROMPT}\n\n${schemaContext}`,
      messages: sqlGenMessages,
    });

    const sqlGenText = sqlGenResponse.content
      .filter((block): block is Anthropic.TextBlock => block.type === 'text')
      .map((block) => block.text)
      .join('\n');

    // Extract SQL from response
    const sqlMatch = sqlGenText.match(/```sql\n([\s\S]*?)```/);
    const sqlExecuted: string[] = [];
    let canonicalDTO: CanonicalDTO | null = null;

    if (sqlMatch) {
      const sql = sqlMatch[1].trim();

      // ========================================================================
      // PHASE 2: SQL EXECUTION (execute query, build DTO)
      // ========================================================================
      const result = await executeSafeQuery(sql);
      sqlExecuted.push(sql);
      canonicalDTO = buildCanonicalDTO(sql, result);
    }

    // ========================================================================
    // PHASE 3: NARRATIVE GENERATION (LLM interprets DTO, not raw question)
    // ========================================================================
    let narrativePrompt: string;

    if (canonicalDTO && canonicalDTO.is_valid) {
      // Valid data - pass DTO to LLM for interpretation
      narrativePrompt = `CANONICAL DATA OBJECT (you MUST base your response on this data):

${JSON.stringify(canonicalDTO, null, 2)}

User question: ${message}

Generate a data-anchored narrative based ONLY on the values in the data object above.`;
    } else if (canonicalDTO && !canonicalDTO.is_valid) {
      // Invalid/empty data - report the issue
      narrativePrompt = `CANONICAL DATA OBJECT (query returned no valid data):

${JSON.stringify(canonicalDTO, null, 2)}

User question: ${message}

Report the data availability issue. Do NOT generate fallback or estimated data.`;
    } else {
      // No SQL needed - simple informational query
      narrativePrompt = `User question: ${message}

This appears to be an informational query that does not require database access. Provide a helpful response based on system documentation only. If database data is needed, indicate that a query should be run.`;
    }

    const narrativeResponse = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 2048,
      system: NARRATIVE_GENERATION_PROMPT,
      messages: [{ role: 'user' as const, content: narrativePrompt }],
    });

    const narrativeText = narrativeResponse.content
      .filter((block): block is Anthropic.TextBlock => block.type === 'text')
      .map((block) => block.text)
      .join('\n');

    // ========================================================================
    // PHASE 4: BUILD RESPONSE (narrative + evidence drawer)
    // ========================================================================
    let finalResponse = narrativeText;

    // Add SQL evidence drawer
    if (sqlExecuted.length > 0 && canonicalDTO) {
      finalResponse += `\n\n---\n**SQL Executed:**\n\`\`\`sql\n${sqlExecuted[0]}\n\`\`\``;

      if (canonicalDTO.row_count > 0) {
        // Format results as markdown table
        const keys = canonicalDTO.columns;
        const header = `| ${keys.join(' | ')} |`;
        const separator = `| ${keys.map(() => '---').join(' | ')} |`;
        const rows = canonicalDTO.rows
          .slice(0, 20)
          .map((row) => `| ${keys.map((k) => String(row[k] ?? '')).join(' | ')} |`)
          .join('\n');

        finalResponse += `\n\n**Query Results (${canonicalDTO.row_count} rows):**\n${header}\n${separator}\n${rows}`;

        if (canonicalDTO.row_count > 20) {
          finalResponse += `\n\n*Showing first 20 of ${canonicalDTO.row_count} rows*`;
        }
      }

      // Add warnings
      if (canonicalDTO.warnings.length > 0) {
        finalResponse += `\n\n**Warnings:**\n${canonicalDTO.warnings.map(w => `- ${w}`).join('\n')}`;
      }

      // Add data freshness
      if (canonicalDTO.data_freshness_days !== null) {
        finalResponse += `\n\n**Data Freshness:** ${canonicalDTO.data_freshness_days} days old`;
      }
    }

    // Log to governance
    await logInquiry(message, narrativeText, sqlExecuted);

    return NextResponse.json({
      success: true,
      response: finalResponse,
      sql_executed: sqlExecuted,
    });
  } catch (error) {
    console.error('VisionChat error:', error);
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/vision-chat
 * Returns API documentation
 */
export async function GET(): Promise<NextResponse> {
  return NextResponse.json({
    endpoint: '/api/vision-chat',
    version: '2026.PROD.1',
    status: 'ACTIVE',
    authority: 'CEO Directive — Vision-OS Dashboard Extension (REV 1.2)',
    constitutional_basis: ['ADR-019', 'IoS-009'],

    capabilities: [
      'Claude 3.5 Sonnet conversational interface',
      'ceo_read_only SQL connectivity',
      'SQL preview and execution',
      'Governance logging',
    ],

    constraints: [
      'READ-ONLY: Only SELECT queries permitted',
      'NO DDL/DML: Cannot modify database',
      'All inquiries logged to governance',
    ],

    usage: {
      method: 'POST',
      body: {
        message: 'Your question or request',
        history: '[Optional] Array of previous messages',
      },
    },
  });
}
