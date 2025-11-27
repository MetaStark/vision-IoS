/**
 * Vision-IoS Dashboard Local Database Schema
 * Mirrors FHQ schemas for local development (ADR-005)
 *
 * This schema provides:
 * - fhq_meta equivalent tables (ADR registry, agent keys, audit logs)
 * - fhq_data equivalent tables (price data, tickers)
 * - fhq_finn equivalent tables (events, CDS metrics, briefings)
 * - fhq_validation equivalent tables (gate status)
 * - fhq_governance equivalent tables (governance state)
 * - vision_* schemas for application layer
 */

import { sqliteTable, text, integer, real, blob } from 'drizzle-orm/sqlite-core';
import { sql } from 'drizzle-orm';

// ============================================================================
// FHQ_META SCHEMA - ADR Registry & Governance Metadata
// ============================================================================

export const adrRegistry = sqliteTable('adr_registry', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  adrNumber: text('adr_number').notNull().unique(),
  title: text('title').notNull(),
  status: text('status').notNull(), // 'Draft', 'Approved', 'Deprecated'
  tier: text('tier').notNull(), // 'Constitutional', 'Operational', 'Informational'
  scope: text('scope'),
  author: text('author').notNull(),
  purpose: text('purpose'),
  authorityChain: text('authority_chain'),
  contentHash: text('content_hash'),
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`),
  updatedAt: text('updated_at').default(sql`CURRENT_TIMESTAMP`),
  approvedBy: text('approved_by'),
  approvedAt: text('approved_at'),
});

export const agentKeys = sqliteTable('agent_keys', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  agentId: text('agent_id').notNull().unique(), // LARS, STIG, LINE, FINN, VEGA
  agentName: text('agent_name').notNull(),
  publicKey: text('public_key').notNull(),
  keyType: text('key_type').default('Ed25519'),
  isActive: integer('is_active', { mode: 'boolean' }).default(true),
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`),
  lastUsedAt: text('last_used_at'),
});

export const auditLog = sqliteTable('audit_log', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  eventType: text('event_type').notNull(),
  eventCategory: text('event_category').notNull(), // 'ClassA', 'ClassB', 'ClassC'
  schemaName: text('schema_name'),
  tableName: text('table_name'),
  recordId: text('record_id'),
  changeDescription: text('change_description'),
  changedBy: text('changed_by').notNull(),
  changedAt: text('changed_at').default(sql`CURRENT_TIMESTAMP`),
  previousValue: text('previous_value'),
  newValue: text('new_value'),
  signature: text('signature'),
});

export const dashboardConfig = sqliteTable('dashboard_config', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  configKey: text('config_key').notNull().unique(),
  configValue: text('config_value').notNull(),
  configType: text('config_type').default('string'), // 'string', 'number', 'boolean', 'json'
  description: text('description'),
  updatedAt: text('updated_at').default(sql`CURRENT_TIMESTAMP`),
  updatedBy: text('updated_by'),
});

// ============================================================================
// FHQ_DATA SCHEMA - Market Data
// ============================================================================

export const tickers = sqliteTable('tickers', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  ticker: text('ticker').notNull().unique(), // BTC-USD, ETH-USD, etc.
  name: text('name').notNull(),
  assetClass: text('asset_class').notNull(), // 'crypto', 'equity', 'index'
  exchange: text('exchange'),
  isActive: integer('is_active', { mode: 'boolean' }).default(true),
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`),
});

export const priceSeries = sqliteTable('price_series', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  ticker: text('ticker').notNull(),
  timestamp: text('timestamp').notNull(),
  resolution: text('resolution').notNull(), // '1h', '1d'
  open: real('open').notNull(),
  high: real('high').notNull(),
  low: real('low').notNull(),
  close: real('close').notNull(),
  volume: real('volume'),
  ingestedAt: text('ingested_at').default(sql`CURRENT_TIMESTAMP`),
  ingestedBy: text('ingested_by').default('LINE'),
});

export const indicators = sqliteTable('indicators', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  ticker: text('ticker').notNull(),
  timestamp: text('timestamp').notNull(),
  indicatorType: text('indicator_type').notNull(), // 'RSI', 'MACD', 'EMA', etc.
  value: real('value').notNull(),
  parameters: text('parameters'), // JSON string of indicator parameters
  calculatedAt: text('calculated_at').default(sql`CURRENT_TIMESTAMP`),
});

// ============================================================================
// FHQ_FINN SCHEMA - Intelligence & Events
// ============================================================================

export const serperEvents = sqliteTable('serper_events', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  eventId: text('event_id').notNull().unique(),
  eventType: text('event_type').notNull(), // 'news', 'sentiment', 'anomaly'
  title: text('title').notNull(),
  description: text('description'),
  source: text('source'),
  sourceUrl: text('source_url'),
  relevanceScore: real('relevance_score'),
  sentimentScore: real('sentiment_score'),
  tickers: text('tickers'), // JSON array of related tickers
  publishedAt: text('published_at'),
  ingestedAt: text('ingested_at').default(sql`CURRENT_TIMESTAMP`),
});

export const cdsMetrics = sqliteTable('cds_metrics', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  metricId: text('metric_id').notNull().unique(),
  cdsScore: real('cds_score').notNull(),
  cdsTier: text('cds_tier').notNull(), // 'low', 'medium', 'high'
  conflictCount: integer('conflict_count'),
  narrativeSummary: text('narrative_summary'),
  topConflicts: text('top_conflicts'), // JSON array
  calculatedAt: text('calculated_at').default(sql`CURRENT_TIMESTAMP`),
  calculatedBy: text('calculated_by').default('FINN'),
});

export const dailyBriefings = sqliteTable('daily_briefings', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  briefingId: text('briefing_id').notNull().unique(),
  briefingDate: text('briefing_date').notNull(),
  marketSummary: text('market_summary').notNull(),
  keyEvents: text('key_events'), // JSON array
  riskAssessment: text('risk_assessment'),
  recommendations: text('recommendations'),
  generatedAt: text('generated_at').default(sql`CURRENT_TIMESTAMP`),
  generatedBy: text('generated_by').default('FINN'),
});

export const signalEvents = sqliteTable('signal_events', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  signalId: text('signal_id').notNull().unique(),
  signalType: text('signal_type').notNull(), // 'buy', 'sell', 'hold', 'alert'
  ticker: text('ticker').notNull(),
  strength: real('strength').notNull(),
  confidence: real('confidence').notNull(),
  rationale: text('rationale'),
  sourceAgent: text('source_agent').notNull(), // FINN, LARS
  generatedAt: text('generated_at').default(sql`CURRENT_TIMESTAMP`),
  expiresAt: text('expires_at'),
  isActive: integer('is_active', { mode: 'boolean' }).default(true),
});

// ============================================================================
// FHQ_VALIDATION SCHEMA - Gates & Quality
// ============================================================================

export const gateStatus = sqliteTable('gate_status', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  gateId: text('gate_id').notNull().unique(),
  gateName: text('gate_name').notNull(), // 'G0', 'G1', 'G2', 'G3', 'G4'
  status: text('status').notNull(), // 'PASS', 'FAIL', 'PENDING', 'BLOCKED'
  lastCheckedAt: text('last_checked_at').default(sql`CURRENT_TIMESTAMP`),
  checkedBy: text('checked_by'),
  failureReason: text('failure_reason'),
  metadata: text('metadata'), // JSON
});

export const dataFreshness = sqliteTable('data_freshness', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  ticker: text('ticker').notNull(),
  resolution: text('resolution').notNull(),
  lastDataPoint: text('last_data_point'),
  freshnessMinutes: integer('freshness_minutes'),
  status: text('status').notNull(), // 'FRESH', 'STALE', 'CRITICAL'
  checkedAt: text('checked_at').default(sql`CURRENT_TIMESTAMP`),
});

export const qualityScorecard = sqliteTable('quality_scorecard', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  scorecardId: text('scorecard_id').notNull().unique(),
  overallScore: real('overall_score').notNull(),
  qualityTier: text('quality_tier').notNull(), // 'A', 'B', 'C', 'D', 'F'
  dimensionScores: text('dimension_scores'), // JSON: completeness, accuracy, timeliness, etc.
  issues: text('issues'), // JSON array of issues
  evaluatedAt: text('evaluated_at').default(sql`CURRENT_TIMESTAMP`),
  evaluatedBy: text('evaluated_by'),
});

// ============================================================================
// FHQ_GOVERNANCE SCHEMA - Governance State
// ============================================================================

export const governanceState = sqliteTable('governance_state', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  currentPhase: text('current_phase').notNull(),
  productionMode: integer('production_mode', { mode: 'boolean' }).default(false),
  architectureFreeze: integer('architecture_freeze', { mode: 'boolean' }).default(false),
  baselineVersion: text('baseline_version'),
  baselineCommit: text('baseline_commit'),
  approvedBy: text('approved_by'),
  approvedAt: text('approved_at'),
  updatedAt: text('updated_at').default(sql`CURRENT_TIMESTAMP`),
  updatedBy: text('updated_by'),
});

export const economicSafety = sqliteTable('economic_safety', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  metricName: text('metric_name').notNull().unique(),
  currentValue: real('current_value').notNull(),
  ceiling: real('ceiling'),
  floor: real('floor'),
  unit: text('unit'), // 'USD', 'percentage', 'count'
  status: text('status').notNull(), // 'SAFE', 'WARNING', 'CRITICAL'
  lastUpdatedAt: text('last_updated_at').default(sql`CURRENT_TIMESTAMP`),
  updatedBy: text('updated_by'),
});

// ============================================================================
// VISION_* SCHEMAS - Application Layer
// ============================================================================

export const iosModuleRegistry = sqliteTable('ios_module_registry', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  moduleId: text('module_id').notNull().unique(), // 'IoS-001', 'IoS-002', etc.
  moduleName: text('module_name').notNull(),
  description: text('description'),
  status: text('status').notNull(), // 'Active', 'Inactive', 'Deprecated'
  version: text('version'),
  dataLineage: text('data_lineage'), // JSON array of source tables/views
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`),
  updatedAt: text('updated_at').default(sql`CURRENT_TIMESTAMP`),
});

export const orchestratorTasks = sqliteTable('orchestrator_tasks', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  taskId: text('task_id').notNull().unique(),
  taskType: text('task_type').notNull(), // 'research', 'analysis', 'operational', 'governance'
  targetAgent: text('target_agent').notNull(), // LARS, FINN, STIG, LINE, VEGA
  action: text('action').notNull(),
  parameters: text('parameters'), // JSON
  requestedBy: text('requested_by').notNull(), // 'CEO', 'System'
  status: text('status').notNull(), // 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'
  result: text('result'), // JSON
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`),
  startedAt: text('started_at'),
  completedAt: text('completed_at'),
  idempotencyKey: text('idempotency_key'),
});

export const agentChatHistory = sqliteTable('agent_chat_history', {
  id: integer('id').primaryKey({ autoIncrement: true }),
  chatId: text('chat_id').notNull(),
  messageId: text('message_id').notNull().unique(),
  role: text('role').notNull(), // 'CEO', 'LARS', 'FINN', etc.
  targetAgent: text('target_agent'),
  content: text('content').notNull(),
  taskType: text('task_type'), // 'research', 'analysis', 'operational', 'governance'
  linkedTaskId: text('linked_task_id'),
  createdAt: text('created_at').default(sql`CURRENT_TIMESTAMP`),
});

// Type exports for TypeScript
export type AdrRegistry = typeof adrRegistry.$inferSelect;
export type NewAdrRegistry = typeof adrRegistry.$inferInsert;
export type AgentKey = typeof agentKeys.$inferSelect;
export type AuditLog = typeof auditLog.$inferSelect;
export type Ticker = typeof tickers.$inferSelect;
export type PriceSeries = typeof priceSeries.$inferSelect;
export type SerperEvent = typeof serperEvents.$inferSelect;
export type CdsMetric = typeof cdsMetrics.$inferSelect;
export type GateStatus = typeof gateStatus.$inferSelect;
export type DataFreshness = typeof dataFreshness.$inferSelect;
export type GovernanceState = typeof governanceState.$inferSelect;
export type EconomicSafety = typeof economicSafety.$inferSelect;
export type IosModuleRegistry = typeof iosModuleRegistry.$inferSelect;
export type OrchestratorTask = typeof orchestratorTasks.$inferSelect;
