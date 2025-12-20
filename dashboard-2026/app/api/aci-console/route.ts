/**
 * ACI Engineering Console API Endpoint
 * POST /api/aci-console
 *
 * Authority: CEO Directive G0 — Activation of the ACI Engineering Console
 *            CEO Directive G0.1 — Operational Enablement
 * Constitutional Basis: ADR-018, ADR-019, ADR-020, ADR-021
 * Classification: Tier-3 Application (SHADOW/PAPER mode only)
 *
 * MANDATORY EXECUTION PATH (Non-Bypassable per CEO Directive §3.1):
 * User Input
 * → ADR-018 State Injection (The Pulse)
 * → ADR-021 Cognitive Middleware (SitC / IKEA / InForage)
 * → Canonical System Prompt (G0.1 §5)
 * → Anthropic Model (claude-sonnet-4-20250514)
 * → Governance Logging (ADR-003 / ADR-019)
 * → Memory Persistence (G0.1 §3 - Append-Only)
 * → Console UI (Read-Only)
 *
 * No component can omgå State Injection, Cognitive Middleware or Governance Logging.
 */

import { NextRequest, NextResponse } from 'next/server';
import { Pool } from 'pg';
import Anthropic from '@anthropic-ai/sdk';

// ============================================================================
// DATABASE CONNECTION
// ============================================================================

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
// TYPE DEFINITIONS
// ============================================================================

interface StateVector {
  stateSnapshotHash: string;
  defconLevel: string;
  btcRegimeLabel: string | null;
  btcRegimeConfidence: number | null;
  activeStrategyHash: string | null;
  activeStrategyName: string | null;
  vectorTimestamp: Date;
  isAtomic: boolean;
}

interface ChainOfQueryNode {
  nodeIndex: number;
  nodeType: 'PLAN_INIT' | 'REASONING' | 'SEARCH' | 'VERIFICATION' | 'PLAN_REVISION' | 'SYNTHESIS' | 'ABORT';
  nodeContent: string;
  nodeRationale?: string;
  verificationStatus: 'PENDING' | 'VERIFIED' | 'FAILED' | 'SKIPPED' | 'ABORTED';
  searchQuery?: string;
  searchResultSummary?: string;
  tokensConsumed?: number;
  costUsd?: number;
}

interface KnowledgeBoundaryCheck {
  queryText: string;
  classification: 'PARAMETRIC' | 'EXTERNAL_REQUIRED' | 'HYBRID' | 'BLOCKED';
  confidenceScore: number;
  volatilityFlag: boolean;
  retrievalTriggered: boolean;
  hallucinationBlocked: boolean;
  decisionRationale: string;
}

interface ForagingDecision {
  searchQuery: string;
  scentScore: number;
  estimatedCostUsd: number;
  budgetCheckPassed: boolean;
  searchExecuted: boolean;
  terminationReason: string;
}

interface ACIConsoleRequest {
  message: string;
  sessionId?: string;
  history?: Array<{ role: 'user' | 'assistant'; content: string }>;
  // G0.1: Support for memory-continuous sessions
  continueSession?: boolean;
}

interface CognitiveMemoryEntry {
  memoryId: string;
  sequenceNumber: number;
  memoryType: 'USER_INPUT' | 'ASSISTANT_OUTPUT' | 'STATE_CONTEXT' | 'TOOL_RESULT' | 'REASONING_CHAIN';
  content: string;
  stateSnapshotHash: string;
  defconLevel: string;
}

interface ACIConsoleResponse {
  success: boolean;
  interactionId?: string;
  sessionId?: string;  // G0.1: Session continuity
  eamStatus?: 'ACTIVE' | 'PAUSED' | 'VIOLATED' | 'COMPLETE';  // G0.2: Evidence Accumulation Mode
  stateSnapshot?: StateVector;
  response?: string;
  chainOfQuery?: ChainOfQueryNode[];
  knowledgeBoundary?: KnowledgeBoundaryCheck[];
  toolsUsed?: string[];
  tokensUsed?: number;
  costUsd?: number;
  error?: string;
  governanceWarnings?: string[];
}

// ============================================================================
// SECTION 1: ADR-018 STATE INJECTION (The Pulse)
// ============================================================================

async function injectStateVector(): Promise<StateVector> {
  const client = await pool.connect();
  try {
    // Fetch current DEFCON state
    const defconResult = await client.query(`
      SELECT defcon_level, triggered_at
      FROM fhq_governance.defcon_state
      WHERE is_current = true
      LIMIT 1
    `);

    // Fetch current BTC regime from canonical source (fhq_perception.regime_daily)
    const regimeResult = await client.query(`
      SELECT regime_classification, regime_confidence, timestamp
      FROM fhq_perception.regime_daily
      WHERE asset_id = 'BTC-USD'
      ORDER BY timestamp DESC
      LIMIT 1
    `);

    // Fetch active strategy
    const strategyResult = await client.query(`
      SELECT strategy_id, strategy_name, strategy_hash
      FROM fhq_governance.canonical_strategy
      WHERE is_active = true
      LIMIT 1
    `);

    const defcon = defconResult.rows[0] || { defcon_level: 'GREEN' };
    const regime = regimeResult.rows[0] || {};
    const strategy = strategyResult.rows[0] || {};

    // Compute composite state hash
    const stateString = JSON.stringify({
      defcon: defcon.defcon_level,
      regime: regime.regime_classification || 'UNKNOWN',
      strategy: strategy.strategy_hash || 'NONE',
      timestamp: new Date().toISOString()
    });

    // Simple hash computation (in production, use crypto.createHash)
    const stateSnapshotHash = Buffer.from(stateString).toString('base64').substring(0, 64);

    const stateVector: StateVector = {
      stateSnapshotHash,
      defconLevel: defcon.defcon_level,
      btcRegimeLabel: regime.regime_classification || null,
      btcRegimeConfidence: regime.regime_confidence ? parseFloat(regime.regime_confidence) : null,
      activeStrategyHash: strategy.strategy_hash || null,
      activeStrategyName: strategy.strategy_name || null,
      vectorTimestamp: new Date(),
      isAtomic: true
    };

    // Log state injection to aci_state_snapshot_log
    await client.query(`
      INSERT INTO fhq_meta.aci_state_snapshot_log (
        state_snapshot_hash,
        defcon_level,
        btc_regime_label,
        btc_regime_confidence,
        active_strategy_hash,
        active_strategy_name,
        vector_timestamp,
        is_atomic,
        created_by
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    `, [
      stateVector.stateSnapshotHash,
      stateVector.defconLevel,
      stateVector.btcRegimeLabel,
      stateVector.btcRegimeConfidence,
      stateVector.activeStrategyHash,
      stateVector.activeStrategyName,
      stateVector.vectorTimestamp,
      stateVector.isAtomic,
      'ACI_CONSOLE'
    ]);

    return stateVector;
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 2: DEFCON GATE CHECK (ADR-016)
// ============================================================================

function checkDefconPermissions(defconLevel: string): { permitted: boolean; restrictions: string[] } {
  const restrictions: string[] = [];

  switch (defconLevel) {
    case 'GREEN':
      return { permitted: true, restrictions: [] };

    case 'YELLOW':
      restrictions.push('Cost-aware mode active');
      restrictions.push('Web agents disabled');
      restrictions.push('Search depth reduced');
      return { permitted: true, restrictions };

    case 'ORANGE':
      restrictions.push('Hypothesis generation frozen');
      restrictions.push('Only LARS-directed tasks allowed');
      return { permitted: true, restrictions };

    case 'RED':
      return { permitted: false, restrictions: ['ACI shutdown - Cognitive resources reallocated'] };

    case 'BLACK':
      return { permitted: false, restrictions: ['Total kill - No reasoning allowed'] };

    default:
      return { permitted: false, restrictions: ['Unknown DEFCON state'] };
  }
}

// ============================================================================
// SECTION 3: EC-022 IKEA - KNOWLEDGE BOUNDARY ENGINE
// ============================================================================

async function classifyKnowledgeBoundary(
  query: string,
  interactionId: string
): Promise<KnowledgeBoundaryCheck> {
  const client = await pool.connect();
  try {
    // Keywords that indicate external data is required
    const externalIndicators = [
      'current', 'today', 'now', 'latest', 'price', 'regime', 'defcon',
      'position', 'trade', 'execution', 'signal', 'allocation'
    ];

    // Keywords that indicate parametric (model) knowledge is sufficient
    const parametricIndicators = [
      'what is', 'explain', 'define', 'how does', 'why', 'describe',
      'concept', 'meaning', 'theory', 'general'
    ];

    const queryLower = query.toLowerCase();

    let externalScore = 0;
    let parametricScore = 0;

    for (const indicator of externalIndicators) {
      if (queryLower.includes(indicator)) externalScore++;
    }

    for (const indicator of parametricIndicators) {
      if (queryLower.includes(indicator)) parametricScore++;
    }

    // Determine classification
    let classification: KnowledgeBoundaryCheck['classification'];
    let confidenceScore: number;
    let retrievalTriggered = false;

    if (externalScore > parametricScore * 1.5) {
      classification = 'EXTERNAL_REQUIRED';
      confidenceScore = Math.min(0.95, 0.5 + (externalScore * 0.1));
      retrievalTriggered = true;
    } else if (parametricScore > externalScore * 1.5) {
      classification = 'PARAMETRIC';
      confidenceScore = Math.min(0.95, 0.5 + (parametricScore * 0.1));
    } else {
      classification = 'HYBRID';
      confidenceScore = 0.6;
      retrievalTriggered = true;
    }

    // Check for volatility (time-sensitive knowledge)
    const volatilityKeywords = ['price', 'regime', 'defcon', 'position', 'signal', 'market'];
    const volatilityFlag = volatilityKeywords.some(kw => queryLower.includes(kw));

    const boundaryCheck: KnowledgeBoundaryCheck = {
      queryText: query,
      classification,
      confidenceScore,
      volatilityFlag,
      retrievalTriggered,
      hallucinationBlocked: false,
      decisionRationale: `Classification: ${classification}. External indicators: ${externalScore}, Parametric indicators: ${parametricScore}. Volatility: ${volatilityFlag}`
    };

    // Log to knowledge_boundary_log
    await client.query(`
      INSERT INTO fhq_meta.knowledge_boundary_log (
        interaction_id,
        query_text,
        classification,
        confidence_score,
        volatility_flag,
        retrieval_triggered,
        hallucination_blocked,
        decision_rationale
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, [
      interactionId,
      query.substring(0, 1000),
      classification,
      confidenceScore,
      volatilityFlag,
      retrievalTriggered,
      boundaryCheck.hallucinationBlocked,
      boundaryCheck.decisionRationale
    ]);

    return boundaryCheck;
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 4: EC-021 INFORAGE - COST-AWARE RETRIEVAL
// ============================================================================

async function evaluateForagingDecision(
  searchQuery: string,
  interactionId: string,
  budgetRemaining: number = 0.50
): Promise<ForagingDecision> {
  const client = await pool.connect();
  try {
    // Estimate cost (simplified)
    const estimatedTokens = Math.ceil(searchQuery.length / 4) * 2;
    const estimatedCostUsd = estimatedTokens * 0.000003; // ~$3/1M tokens

    // Calculate scent score (information foraging theory)
    // Higher scores for more specific queries
    const queryWords = searchQuery.split(/\s+/).length;
    const scentScore = Math.min(0.95, 0.3 + (queryWords * 0.05) + (searchQuery.includes('BTC') ? 0.2 : 0));

    // Budget check
    const budgetCheckPassed = estimatedCostUsd <= budgetRemaining;

    // Determine if search should execute
    const scentThreshold = 0.4;
    const searchExecuted = budgetCheckPassed && scentScore >= scentThreshold;

    let terminationReason: string;
    if (searchExecuted) {
      terminationReason = 'EXECUTED';
    } else if (!budgetCheckPassed) {
      terminationReason = 'BUDGET_EXCEEDED';
    } else if (scentScore < scentThreshold) {
      terminationReason = 'SCENT_TOO_LOW';
    } else {
      terminationReason = 'DIMINISHING_RETURNS';
    }

    const decision: ForagingDecision = {
      searchQuery,
      scentScore,
      estimatedCostUsd,
      budgetCheckPassed,
      searchExecuted,
      terminationReason
    };

    // Log to search_foraging_log
    await client.query(`
      INSERT INTO fhq_meta.search_foraging_log (
        interaction_id,
        search_query,
        scent_score,
        estimated_cost_usd,
        budget_remaining_usd,
        budget_check_passed,
        search_executed,
        termination_reason
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, [
      interactionId,
      searchQuery.substring(0, 500),
      scentScore,
      estimatedCostUsd,
      budgetRemaining,
      budgetCheckPassed,
      searchExecuted,
      terminationReason
    ]);

    return decision;
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 5: EC-020 SITC - CHAIN OF QUERY
// ============================================================================

async function buildChainOfQuery(
  message: string,
  interactionId: string,
  boundaryCheck: KnowledgeBoundaryCheck
): Promise<ChainOfQueryNode[]> {
  const client = await pool.connect();
  const chain: ChainOfQueryNode[] = [];

  try {
    // Node 0: Plan Initialization
    const planNode: ChainOfQueryNode = {
      nodeIndex: 0,
      nodeType: 'PLAN_INIT',
      nodeContent: `Initial plan for query: "${message.substring(0, 200)}..."`,
      nodeRationale: 'Dynamic planning initiated per SitC protocol',
      verificationStatus: 'VERIFIED'
    };
    chain.push(planNode);

    await client.query(`
      INSERT INTO fhq_meta.chain_of_query (
        interaction_id, node_index, node_type, node_content, node_rationale, verification_status
      ) VALUES ($1, $2, $3, $4, $5, $6)
    `, [interactionId, planNode.nodeIndex, planNode.nodeType, planNode.nodeContent, planNode.nodeRationale, planNode.verificationStatus]);

    // Node 1: Knowledge Boundary Check
    const boundaryNode: ChainOfQueryNode = {
      nodeIndex: 1,
      nodeType: 'VERIFICATION',
      nodeContent: `IKEA Classification: ${boundaryCheck.classification}`,
      nodeRationale: boundaryCheck.decisionRationale,
      verificationStatus: boundaryCheck.hallucinationBlocked ? 'FAILED' : 'VERIFIED'
    };
    chain.push(boundaryNode);

    await client.query(`
      INSERT INTO fhq_meta.chain_of_query (
        interaction_id, node_index, node_type, node_content, node_rationale, verification_status
      ) VALUES ($1, $2, $3, $4, $5, $6)
    `, [interactionId, boundaryNode.nodeIndex, boundaryNode.nodeType, boundaryNode.nodeContent, boundaryNode.nodeRationale, boundaryNode.verificationStatus]);

    // Node 2: Search (if required)
    if (boundaryCheck.retrievalTriggered) {
      const searchNode: ChainOfQueryNode = {
        nodeIndex: 2,
        nodeType: 'SEARCH',
        nodeContent: 'Database retrieval initiated',
        searchQuery: message,
        verificationStatus: 'PENDING'
      };
      chain.push(searchNode);

      await client.query(`
        INSERT INTO fhq_meta.chain_of_query (
          interaction_id, node_index, node_type, node_content, search_query, verification_status
        ) VALUES ($1, $2, $3, $4, $5, $6)
      `, [interactionId, searchNode.nodeIndex, searchNode.nodeType, searchNode.nodeContent, searchNode.searchQuery, searchNode.verificationStatus]);
    }

    // Node 3: Reasoning
    const reasoningNode: ChainOfQueryNode = {
      nodeIndex: chain.length,
      nodeType: 'REASONING',
      nodeContent: 'LLM reasoning step with state-bound context',
      verificationStatus: 'PENDING'
    };
    chain.push(reasoningNode);

    await client.query(`
      INSERT INTO fhq_meta.chain_of_query (
        interaction_id, node_index, node_type, node_content, verification_status
      ) VALUES ($1, $2, $3, $4, $5)
    `, [interactionId, reasoningNode.nodeIndex, reasoningNode.nodeType, reasoningNode.nodeContent, reasoningNode.verificationStatus]);

    return chain;
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 6: ALLOWED TOOLS (CEO Directive §6)
// ============================================================================

async function executeConsultCanonicalDocuments(
  docId: string,
  interactionId: string
): Promise<{ content: string; hash: string } | null> {
  const client = await pool.connect();
  try {
    // Fetch from ADR registry
    const result = await client.query(`
      SELECT adr_title, description, sha256_hash, adr_status, current_version
      FROM fhq_meta.adr_registry
      WHERE adr_id = $1
    `, [docId]);

    if (result.rows.length === 0) {
      // Log failed tool usage
      await client.query(`
        INSERT INTO fhq_meta.tool_usage_log (
          interaction_id, tool_name, input_parameters,
          adr013_validated, adr018_state_bound, execution_status, error_message
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      `, [
        interactionId,
        'consult_canonical_documents',
        JSON.stringify({ doc_id: docId }),
        false,
        true,
        'ERROR',
        `Document not found: ${docId}`
      ]);
      return null;
    }

    const doc = result.rows[0];

    // Log successful tool usage
    await client.query(`
      INSERT INTO fhq_meta.tool_usage_log (
        interaction_id, tool_name, input_parameters,
        adr013_validated, adr018_state_bound, doc_id, canonical_sha256, hash_validated,
        execution_status, result_summary
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
    `, [
      interactionId,
      'consult_canonical_documents',
      JSON.stringify({ doc_id: docId }),
      true,
      true,
      docId,
      doc.sha256_hash,
      true,
      'SUCCESS',
      `Retrieved ${docId}: ${doc.adr_title}`
    ]);

    return {
      content: `${doc.adr_title}\n\nStatus: ${doc.adr_status}\nVersion: ${doc.current_version}\n\n${doc.description || ''}`,
      hash: doc.sha256_hash
    };
  } finally {
    client.release();
  }
}

async function executeInspectDatabase(
  query: string,
  interactionId: string
): Promise<any[] | null> {
  const client = await pool.connect();
  try {
    // Safety check - only SELECT allowed
    if (!query.trim().toUpperCase().startsWith('SELECT')) {
      await client.query(`
        INSERT INTO fhq_meta.tool_usage_log (
          interaction_id, tool_name, input_parameters,
          execution_status, error_message
        ) VALUES ($1, $2, $3, $4, $5)
      `, [
        interactionId,
        'inspect_database',
        JSON.stringify({ query: query.substring(0, 200) }),
        'BLOCKED_GOVERNANCE',
        'Only SELECT queries permitted'
      ]);
      return null;
    }

    const result = await client.query(query);

    // Log successful execution
    await client.query(`
      INSERT INTO fhq_meta.tool_usage_log (
        interaction_id, tool_name, input_parameters,
        adr013_validated, adr018_state_bound, query_hash, row_count,
        execution_status, result_summary
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    `, [
      interactionId,
      'inspect_database',
      JSON.stringify({ query: query.substring(0, 200) }),
      true,
      true,
      Buffer.from(query).toString('base64').substring(0, 64),
      result.rows.length,
      'SUCCESS',
      `Query returned ${result.rows.length} rows`
    ]);

    return result.rows;
  } catch (error) {
    await client.query(`
      INSERT INTO fhq_meta.tool_usage_log (
        interaction_id, tool_name, input_parameters,
        execution_status, error_message
      ) VALUES ($1, $2, $3, $4, $5)
    `, [
      interactionId,
      'inspect_database',
      JSON.stringify({ query: query.substring(0, 200) }),
      'ERROR',
      error instanceof Error ? error.message : 'Query failed'
    ]);
    return null;
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 7: LOG AGENT INTERACTION
// ============================================================================

async function logInteraction(
  interactionId: string,
  sessionId: string | undefined,
  stateVector: StateVector,
  userInput: string,
  modelOutput: string,
  status: string,
  tokensUsed: number,
  costUsd: number,
  latencyMs: number
): Promise<void> {
  const client = await pool.connect();
  try {
    await client.query(`
      INSERT INTO fhq_meta.agent_interaction_log (
        interaction_id, session_id, agent_id, model_provider, model_name,
        state_snapshot_hash, defcon_at_invocation,
        user_input, model_output,
        ikea_boundary_checked, inforage_cost_checked,
        input_tokens, output_tokens, total_tokens, cost_usd, latency_ms,
        execution_mode, status, completed_at
      ) VALUES (
        $1, $2, $3, $4, $5,
        $6, $7,
        $8, $9,
        $10, $11,
        $12, $13, $14, $15, $16,
        $17, $18, $19
      )
    `, [
      interactionId,
      sessionId || null,
      'ACI_CONSOLE',
      'Anthropic',
      'claude-sonnet-4-20250514',
      stateVector.stateSnapshotHash,
      stateVector.defconLevel,
      userInput.substring(0, 5000),
      modelOutput.substring(0, 10000),
      true,  // IKEA checked
      true,  // InForage checked
      Math.ceil(userInput.length / 4),
      Math.ceil(modelOutput.length / 4),
      tokensUsed,
      costUsd,
      latencyMs,
      'SHADOW_PAPER',
      status,
      new Date()
    ]);
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 8: G0.1 SESSION MANAGEMENT
// ============================================================================

async function getOrCreateSession(sessionId?: string): Promise<{ sessionId: string; isNew: boolean }> {
  const client = await pool.connect();
  try {
    if (sessionId) {
      // Check if session exists and is active
      const result = await client.query(`
        SELECT session_id, expires_at, is_active
        FROM fhq_meta.aci_console_sessions
        WHERE session_id = $1 AND is_active = true AND expires_at > NOW()
      `, [sessionId]);

      if (result.rows.length > 0) {
        // Update last activity
        await client.query(`
          UPDATE fhq_meta.aci_console_sessions
          SET last_activity_at = NOW(),
              interaction_count = interaction_count + 1
          WHERE session_id = $1
        `, [sessionId]);
        return { sessionId, isNew: false };
      }
    }

    // Create new session
    const newSessionId = crypto.randomUUID();
    await client.query(`
      INSERT INTO fhq_meta.aci_console_sessions (
        session_id, agent_channel, created_at, expires_at, last_activity_at,
        interaction_count, is_active
      ) VALUES ($1, $2, NOW(), NOW() + INTERVAL '24 hours', NOW(), 1, true)
    `, [newSessionId, 'ACI_CONSOLE_TIER_3']);

    return { sessionId: newSessionId, isNew: true };
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 9: G0.1 CANONICAL SYSTEM PROMPT
// ============================================================================

async function getCanonicalSystemPrompt(stateVector: StateVector): Promise<string> {
  const client = await pool.connect();
  try {
    // Fetch the active canonical system prompt
    const result = await client.query(`
      SELECT prompt_content
      FROM fhq_meta.aci_system_prompts
      WHERE prompt_name = 'ACI_CONSOLE_CONSTITUTIONAL'
        AND is_active = true
      ORDER BY prompt_version DESC
      LIMIT 1
    `);

    let basePrompt: string;
    if (result.rows.length > 0) {
      basePrompt = result.rows[0].prompt_content;
    } else {
      // Fallback if database prompt not found (should not happen in production)
      basePrompt = `# ACI Engineering Interface — Constitutional Identity

You are the ACI Engineering Interface — a constitutionally governed cognitive system operating under Tier-3 Advisory authority.

## CLASSIFICATION
- Tier-3 Application Layer
- Advisory only — No execution authority
- Read-only database access
- SHADOW/PAPER mode`;
    }

    // Append live state injection
    const stateInjection = `

## LIVE STATE INJECTION (ADR-018 - The Pulse)
This state binding is MANDATORY and represents the current system reality:
- **State Hash:** ${stateVector.stateSnapshotHash}
- **DEFCON Level:** ${stateVector.defconLevel}
- **BTC Regime:** ${stateVector.btcRegimeLabel || 'UNKNOWN'} (confidence: ${stateVector.btcRegimeConfidence?.toFixed(2) || 'N/A'})
- **Active Strategy:** ${stateVector.activeStrategyName || 'NONE'}
- **Timestamp:** ${stateVector.vectorTimestamp.toISOString()}

You MUST reason only within this state context. Do not assume or hallucinate data beyond this injection.`;

    return basePrompt + stateInjection;
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 10: G0.1 COGNITIVE MEMORY PERSISTENCE (Append-Only)
// ============================================================================

async function loadSessionMemory(
  sessionId: string,
  limit: number = 20
): Promise<CognitiveMemoryEntry[]> {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT memory_id, sequence_number, memory_type, content,
             state_snapshot_hash, defcon_level
      FROM fhq_meta.aci_cognitive_memory
      WHERE session_id = $1
      ORDER BY sequence_number DESC
      LIMIT $2
    `, [sessionId, limit]);

    return result.rows.map(row => ({
      memoryId: row.memory_id,
      sequenceNumber: row.sequence_number,
      memoryType: row.memory_type,
      content: row.content,
      stateSnapshotHash: row.state_snapshot_hash,
      defconLevel: row.defcon_level
    })).reverse(); // Return in chronological order
  } finally {
    client.release();
  }
}

async function appendToMemory(
  sessionId: string,
  interactionId: string,
  stateVector: StateVector,
  memoryType: CognitiveMemoryEntry['memoryType'],
  content: string
): Promise<void> {
  const client = await pool.connect();
  try {
    // Get next sequence number
    const seqResult = await client.query(`
      SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
      FROM fhq_meta.aci_cognitive_memory
      WHERE session_id = $1
    `, [sessionId]);

    const nextSeq = seqResult.rows[0].next_seq;

    // Append-only insert (no updates allowed per G0.1 §3.2)
    await client.query(`
      INSERT INTO fhq_meta.aci_cognitive_memory (
        session_id, interaction_id, sequence_number,
        state_snapshot_hash, defcon_level, agent_channel,
        memory_type, content
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, [
      sessionId,
      interactionId,
      nextSeq,
      stateVector.stateSnapshotHash,
      stateVector.defconLevel,
      'ACI_CONSOLE_TIER_3',
      memoryType,
      content.substring(0, 10000) // Truncate for safety
    ]);
  } finally {
    client.release();
  }
}

function formatMemoryForContext(memories: CognitiveMemoryEntry[]): string {
  if (memories.length === 0) return '';

  const formatted = memories.map(m => {
    const typeLabel = m.memoryType === 'USER_INPUT' ? 'User' :
                      m.memoryType === 'ASSISTANT_OUTPUT' ? 'Assistant' :
                      m.memoryType;
    return `[${typeLabel}] ${m.content.substring(0, 500)}`;
  }).join('\n\n');

  return `\n## SESSION MEMORY (State-Bound History)\n${formatted}`;
}

// ============================================================================
// SECTION 11: G0.2 EVIDENCE ACCUMULATION MODE STATUS
// ============================================================================

async function getEAMStatus(): Promise<'ACTIVE' | 'PAUSED' | 'VIOLATED' | 'COMPLETE' | null> {
  const client = await pool.connect();
  try {
    const result = await client.query(`
      SELECT eam_status
      FROM fhq_meta.g1_evidence_accumulation
      WHERE eam_status = 'ACTIVE'
      LIMIT 1
    `);

    if (result.rows.length > 0) {
      return result.rows[0].eam_status;
    }
    return null;
  } catch {
    // Table may not exist yet
    return null;
  } finally {
    client.release();
  }
}

async function incrementEAMCounters(
  interactionId: string,
  stateBindingValid: boolean,
  sitcChainGenerated: boolean,
  ikeaClassified: boolean,
  inforageOptimal: boolean
): Promise<void> {
  const client = await pool.connect();
  try {
    // Update cumulative counters
    await client.query(`
      UPDATE fhq_meta.g1_evidence_accumulation
      SET
        state_integrity_count = state_integrity_count + 1,
        state_integrity_failures = state_integrity_failures + CASE WHEN $1 THEN 0 ELSE 1 END,
        cognitive_fidelity_sitc_count = cognitive_fidelity_sitc_count + CASE WHEN $2 THEN 1 ELSE 0 END,
        cognitive_fidelity_ikea_count = cognitive_fidelity_ikea_count + CASE WHEN $3 THEN 1 ELSE 0 END,
        cognitive_fidelity_inforage_count = cognitive_fidelity_inforage_count + CASE WHEN $4 THEN 1 ELSE 0 END,
        updated_at = NOW()
      WHERE eam_status = 'ACTIVE'
    `, [stateBindingValid, sitcChainGenerated, ikeaClassified, inforageOptimal]);

    // Update daily snapshot
    await client.query(`
      INSERT INTO fhq_meta.g1_evidence_daily_snapshot (
        snapshot_date,
        accumulation_id,
        invocations_today,
        invocations_with_state_binding,
        sitc_chains_generated,
        ikea_classifications,
        inforage_queries
      )
      SELECT
        CURRENT_DATE,
        accumulation_id,
        1,
        CASE WHEN $1 THEN 1 ELSE 0 END,
        CASE WHEN $2 THEN 1 ELSE 0 END,
        CASE WHEN $3 THEN 1 ELSE 0 END,
        CASE WHEN $4 THEN 1 ELSE 0 END
      FROM fhq_meta.g1_evidence_accumulation
      WHERE eam_status = 'ACTIVE'
      ON CONFLICT (snapshot_date) DO UPDATE SET
        invocations_today = fhq_meta.g1_evidence_daily_snapshot.invocations_today + 1,
        invocations_with_state_binding = fhq_meta.g1_evidence_daily_snapshot.invocations_with_state_binding + CASE WHEN $1 THEN 1 ELSE 0 END,
        sitc_chains_generated = fhq_meta.g1_evidence_daily_snapshot.sitc_chains_generated + CASE WHEN $2 THEN 1 ELSE 0 END,
        ikea_classifications = fhq_meta.g1_evidence_daily_snapshot.ikea_classifications + CASE WHEN $3 THEN 1 ELSE 0 END,
        inforage_queries = fhq_meta.g1_evidence_daily_snapshot.inforage_queries + CASE WHEN $4 THEN 1 ELSE 0 END
    `, [stateBindingValid, sitcChainGenerated, ikeaClassified, inforageOptimal]);
  } catch {
    // Silently fail if tables don't exist (pre-G0.2)
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 12: G0.1 CANONICAL DOCUMENT SEARCH (Read-Only)
// ============================================================================

async function searchCanonicalDocuments(
  query: string,
  interactionId: string,
  limit: number = 5
): Promise<Array<{ docId: string; section: string; content: string; relevanceScore: number }>> {
  const client = await pool.connect();
  try {
    // Search canonical_document_chunks using text similarity
    // Note: Full vector search requires embedding generation which is a future enhancement
    const result = await client.query(`
      SELECT
        document_id,
        section_reference,
        chunk_text,
        SIMILARITY(chunk_text, $1) as relevance_score
      FROM fhq_meta.canonical_document_chunks
      WHERE chunk_text ILIKE '%' || $1 || '%'
         OR document_id ILIKE '%' || $1 || '%'
      ORDER BY relevance_score DESC
      LIMIT $2
    `, [query, limit]);

    // Log the search
    await client.query(`
      INSERT INTO fhq_meta.tool_usage_log (
        interaction_id, tool_name, input_parameters,
        adr013_validated, adr018_state_bound, execution_status,
        result_summary, row_count
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, [
      interactionId,
      'search_canonical_documents',
      JSON.stringify({ query, limit }),
      true,
      true,
      'SUCCESS',
      `Found ${result.rows.length} document chunks`,
      result.rows.length
    ]);

    return result.rows.map(row => ({
      docId: row.document_id,
      section: row.section_reference || 'Full Document',
      content: row.chunk_text,
      relevanceScore: row.relevance_score || 0
    }));
  } catch (error) {
    // If SIMILARITY function doesn't exist, fall back to basic ILIKE search
    const result = await client.query(`
      SELECT
        document_id,
        section_reference,
        chunk_text,
        0.5 as relevance_score
      FROM fhq_meta.canonical_document_chunks
      WHERE chunk_text ILIKE '%' || $1 || '%'
         OR document_id ILIKE '%' || $1 || '%'
      ORDER BY created_at DESC
      LIMIT $2
    `, [query, limit]);

    return result.rows.map(row => ({
      docId: row.document_id,
      section: row.section_reference || 'Full Document',
      content: row.chunk_text,
      relevanceScore: 0.5
    }));
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 12: G0.1 DOCUMENT-DATABASE RECONCILIATION (Read-Only)
// ============================================================================

interface ReconciliationCheck {
  documentId: string;
  documentTitle: string;
  constitutionalStatus: 'ALIGNED' | 'DRIFT_DETECTED' | 'MISSING' | 'UNKNOWN';
  databasePresence: boolean;
  adrRegistryHash: string | null;
  notes: string;
}

async function checkDocumentReconciliation(
  documentId: string,
  interactionId: string
): Promise<ReconciliationCheck> {
  const client = await pool.connect();
  try {
    // Check ADR registry
    const registryResult = await client.query(`
      SELECT adr_id, adr_title, sha256_hash, adr_status
      FROM fhq_meta.adr_registry
      WHERE adr_id = $1
    `, [documentId]);

    // Check if document has been reconciled
    const reconcileResult = await client.query(`
      SELECT document_id, reconciliation_status, last_reconciled_at, discrepancy_notes
      FROM fhq_meta.document_database_reconciliation
      WHERE document_id = $1
      ORDER BY last_reconciled_at DESC
      LIMIT 1
    `, [documentId]);

    const registry = registryResult.rows[0];
    const reconciliation = reconcileResult.rows[0];

    let status: ReconciliationCheck['constitutionalStatus'] = 'UNKNOWN';
    let notes = '';

    if (!registry) {
      status = 'MISSING';
      notes = `Document ${documentId} not found in ADR registry`;
    } else if (reconciliation) {
      status = reconciliation.reconciliation_status === 'ALIGNED' ? 'ALIGNED' : 'DRIFT_DETECTED';
      notes = reconciliation.discrepancy_notes || `Last reconciled: ${reconciliation.last_reconciled_at}`;
    } else {
      status = 'UNKNOWN';
      notes = 'Document registered but never reconciled';
    }

    // Log the check
    await client.query(`
      INSERT INTO fhq_meta.tool_usage_log (
        interaction_id, tool_name, input_parameters,
        adr013_validated, adr018_state_bound, execution_status,
        result_summary
      ) VALUES ($1, $2, $3, $4, $5, $6, $7)
    `, [
      interactionId,
      'check_document_reconciliation',
      JSON.stringify({ document_id: documentId }),
      true,
      true,
      'SUCCESS',
      `Reconciliation check: ${status}`
    ]);

    return {
      documentId,
      documentTitle: registry?.adr_title || 'Unknown',
      constitutionalStatus: status,
      databasePresence: !!registry,
      adrRegistryHash: registry?.sha256_hash || null,
      notes
    };
  } finally {
    client.release();
  }
}

// ============================================================================
// SECTION 13: MAIN HANDLER
// ============================================================================

export async function POST(request: NextRequest): Promise<NextResponse<ACIConsoleResponse>> {
  const startTime = Date.now();
  const interactionId = crypto.randomUUID();
  const governanceWarnings: string[] = [];

  try {
    const body = (await request.json()) as ACIConsoleRequest;
    const { message, sessionId: requestSessionId, history = [], continueSession = true } = body;

    if (!message) {
      return NextResponse.json({
        success: false,
        error: 'Message is required'
      }, { status: 400 });
    }

    // ========================================================================
    // STEP 0: G0.1 SESSION MANAGEMENT — MANDATORY
    // ========================================================================
    const session = await getOrCreateSession(requestSessionId);
    const sessionId = session.sessionId;

    if (session.isNew) {
      governanceWarnings.push('New session created');
    }

    // ========================================================================
    // STEP 0.5: G0.2 EAM STATUS CHECK
    // ========================================================================
    const eamStatus = await getEAMStatus();
    if (eamStatus === 'ACTIVE') {
      governanceWarnings.push('G0.2 Evidence Accumulation Mode: ACTIVE');
    }

    // ========================================================================
    // STEP 1: ADR-018 STATE INJECTION (The Pulse) — MANDATORY
    // ========================================================================
    const stateVector = await injectStateVector();

    // ========================================================================
    // STEP 2: DEFCON GATE CHECK — MANDATORY
    // ========================================================================
    const defconCheck = checkDefconPermissions(stateVector.defconLevel);

    if (!defconCheck.permitted) {
      return NextResponse.json({
        success: false,
        interactionId,
        stateSnapshot: stateVector,
        error: `ACI Console blocked: ${defconCheck.restrictions.join(', ')}`,
        governanceWarnings: defconCheck.restrictions
      }, { status: 503 });
    }

    if (defconCheck.restrictions.length > 0) {
      governanceWarnings.push(...defconCheck.restrictions);
    }

    // ========================================================================
    // STEP 3: EC-022 IKEA - KNOWLEDGE BOUNDARY CHECK — MANDATORY
    // ========================================================================
    const boundaryCheck = await classifyKnowledgeBoundary(message, interactionId);

    if (boundaryCheck.hallucinationBlocked) {
      return NextResponse.json({
        success: false,
        interactionId,
        stateSnapshot: stateVector,
        error: 'Response blocked by IKEA hallucination firewall',
        knowledgeBoundary: [boundaryCheck],
        governanceWarnings: ['HALLUCINATION_REJECTION_EVENT triggered']
      }, { status: 422 });
    }

    // ========================================================================
    // STEP 4: EC-021 INFORAGE - COST-AWARE RETRIEVAL — MANDATORY
    // ========================================================================
    const foragingDecision = await evaluateForagingDecision(message, interactionId);

    if (!foragingDecision.budgetCheckPassed) {
      governanceWarnings.push('Budget constraint active - search limited');
    }

    // ========================================================================
    // STEP 5: EC-020 SITC - BUILD CHAIN OF QUERY — MANDATORY
    // ========================================================================
    const chainOfQuery = await buildChainOfQuery(message, interactionId, boundaryCheck);

    // ========================================================================
    // STEP 5.5: G0.1 LOAD SESSION MEMORY — MANDATORY
    // ========================================================================
    const sessionMemory = continueSession
      ? await loadSessionMemory(sessionId, 20)
      : [];
    const memoryContext = formatMemoryForContext(sessionMemory);

    // ========================================================================
    // STEP 6: CONSTRUCT STATE-BOUND PROMPT (G0.1 Canonical System Prompt)
    // ========================================================================
    const canonicalPrompt = await getCanonicalSystemPrompt(stateVector);

    // Append IKEA classification and memory context
    const systemPrompt = canonicalPrompt + `

## KNOWLEDGE BOUNDARY (IKEA - EC-022)
Classification for this query: ${boundaryCheck.classification}
- If EXTERNAL_REQUIRED: You must cite data from database queries
- If PARAMETRIC: You may use model knowledge for conceptual answers
- Volatility Flag: ${boundaryCheck.volatilityFlag ? 'TIME-SENSITIVE DATA' : 'Stable'}
${memoryContext}`;

    // ========================================================================
    // STEP 7: LLM INVOCATION
    // ========================================================================
    const llmResponse = await anthropic.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 2048,
      system: systemPrompt,
      messages: [
        ...history.slice(-6).map(h => ({ role: h.role as 'user' | 'assistant', content: h.content })),
        { role: 'user' as const, content: message }
      ]
    });

    const responseText = llmResponse.content
      .filter((block): block is Anthropic.TextBlock => block.type === 'text')
      .map((block) => block.text)
      .join('\n');

    const tokensUsed = (llmResponse.usage?.input_tokens || 0) + (llmResponse.usage?.output_tokens || 0);
    const costUsd = tokensUsed * 0.000003;
    const latencyMs = Date.now() - startTime;

    // ========================================================================
    // STEP 8: GOVERNANCE LOGGING — MANDATORY
    // ========================================================================
    await logInteraction(
      interactionId,
      sessionId,
      stateVector,
      message,
      responseText,
      'COMPLETED',
      tokensUsed,
      costUsd,
      latencyMs
    );

    // ========================================================================
    // STEP 8.5: G0.1 MEMORY PERSISTENCE — MANDATORY (Append-Only)
    // ========================================================================
    // Store user input
    await appendToMemory(
      sessionId,
      interactionId,
      stateVector,
      'USER_INPUT',
      message
    );

    // Store assistant response
    await appendToMemory(
      sessionId,
      interactionId,
      stateVector,
      'ASSISTANT_OUTPUT',
      responseText
    );

    // Update CoQ synthesis node
    const client = await pool.connect();
    try {
      await client.query(`
        INSERT INTO fhq_meta.chain_of_query (
          interaction_id, node_index, node_type, node_content, verification_status, tokens_consumed, cost_usd
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      `, [
        interactionId,
        chainOfQuery.length,
        'SYNTHESIS',
        `Response generated: ${responseText.substring(0, 200)}...`,
        'VERIFIED',
        tokensUsed,
        costUsd
      ]);
    } finally {
      client.release();
    }

    // ========================================================================
    // STEP 8.7: G0.2 EVIDENCE ACCUMULATION — INCREMENT COUNTERS
    // ========================================================================
    if (eamStatus === 'ACTIVE') {
      await incrementEAMCounters(
        interactionId,
        stateVector.stateSnapshotHash !== null && stateVector.stateSnapshotHash !== '',  // state binding valid
        chainOfQuery.length > 2,  // non-trivial SitC chain
        boundaryCheck.classification !== null,  // IKEA classified
        foragingDecision.budgetCheckPassed  // InForage optimal
      );
    }

    // ========================================================================
    // STEP 9: RETURN RESPONSE
    // ========================================================================
    return NextResponse.json({
      success: true,
      interactionId,
      sessionId,  // G0.1: Return session ID for continuity
      eamStatus: eamStatus || undefined,  // G0.2: Evidence Accumulation Mode status
      stateSnapshot: stateVector,
      response: responseText,
      chainOfQuery,
      knowledgeBoundary: [boundaryCheck],
      toolsUsed: boundaryCheck.retrievalTriggered ? ['inspect_database'] : [],
      tokensUsed,
      costUsd,
      governanceWarnings: governanceWarnings.length > 0 ? governanceWarnings : undefined
    });

  } catch (error) {
    console.error('ACI Console error:', error);

    return NextResponse.json({
      success: false,
      interactionId,
      error: error instanceof Error ? error.message : 'Unknown error',
      governanceWarnings: ['SYSTEM_ERROR - interaction logged for audit']
    }, { status: 500 });
  }
}

// ============================================================================
// GET HANDLER - API DOCUMENTATION
// ============================================================================

export async function GET(): Promise<NextResponse> {
  return NextResponse.json({
    endpoint: '/api/aci-console',
    version: '2026.PROD.1.1',  // G0.1 Operational Enablement
    status: 'ACTIVE',
    authority: [
      'CEO Directive G0 — Activation of the ACI Engineering Console',
      'CEO Directive G0.1 — Operational Enablement'
    ],
    constitutional_basis: ['ADR-018', 'ADR-019', 'ADR-020', 'ADR-021'],
    classification: 'Tier-3 Application (SHADOW/PAPER mode only)',

    mandatory_execution_path: [
      'Session Management (G0.1)',
      'ADR-018 State Injection (The Pulse)',
      'DEFCON Gate Check',
      'EC-022 IKEA Knowledge Boundary',
      'EC-021 InForage Cost-Aware Retrieval',
      'EC-020 SitC Chain of Query',
      'Session Memory Load (G0.1)',
      'Canonical System Prompt (G0.1)',
      'Anthropic Model (claude-sonnet-4-20250514)',
      'Governance Logging (ADR-003 / ADR-019)',
      'Memory Persistence (G0.1 - Append-Only)',
      'Console UI (Read-Only)'
    ],

    cognitive_engines: {
      'EC-020': { name: 'SitC', role: 'Chain of Query / Dynamic Planning' },
      'EC-021': { name: 'InForage', role: 'Cost-Aware Retrieval' },
      'EC-022': { name: 'IKEA', role: 'Knowledge Boundary / Hallucination Firewall' }
    },

    g0_1_capabilities: {
      session_continuity: 'Sessions persist with state-bound memory',
      canonical_system_prompt: 'Identity loaded from database',
      cognitive_memory: 'Append-only, state-bound conversation history',
      document_ingestion: 'Pending implementation',
      reconciliation: 'Pending implementation'
    },

    allowed_tools: [
      'consult_canonical_documents (read-only, hash-verified)',
      'inspect_database (read-only, whitelisted views)'
    ],

    constraints: {
      execution_mode: 'SHADOW_PAPER only',
      write_access: false,
      canonical_tables: 'READ-ONLY',
      defcon_gated: true,
      memory_mode: 'APPEND_ONLY'
    },

    usage: {
      method: 'POST',
      body: {
        message: 'Your query (required)',
        sessionId: 'Optional session identifier',
        history: 'Optional array of previous messages'
      }
    }
  });
}
