/**
 * Database Seed Script for Vision-IoS Dashboard
 * Populates initial data including ADR-005 registration
 */

import Database from 'better-sqlite3';
import { drizzle } from 'drizzle-orm/better-sqlite3';
import * as schema from './schema';
import { sql } from 'drizzle-orm';
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';

// Ensure db directory exists
const dbDir = path.join(process.cwd(), 'db');
if (!fs.existsSync(dbDir)) {
  fs.mkdirSync(dbDir, { recursive: true });
}

// Database file path
const dbPath = path.join(dbDir, 'vision-ios.db');

// Create SQLite connection
const sqlite = new Database(dbPath);
sqlite.pragma('journal_mode = WAL');

// Create Drizzle instance
const db = drizzle(sqlite, { schema });

// Helper to generate content hash
function generateHash(content: string): string {
  return crypto.createHash('sha256').update(content).digest('hex').substring(0, 16);
}

async function seed() {
  console.log('Starting database seed...');

  // Create tables
  console.log('Creating tables...');

  // ADR Registry
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS adr_registry (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      adr_number TEXT NOT NULL UNIQUE,
      title TEXT NOT NULL,
      status TEXT NOT NULL,
      tier TEXT NOT NULL,
      scope TEXT,
      author TEXT NOT NULL,
      purpose TEXT,
      authority_chain TEXT,
      content_hash TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      approved_by TEXT,
      approved_at TEXT
    )
  `);

  // Agent Keys
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS agent_keys (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      agent_id TEXT NOT NULL UNIQUE,
      agent_name TEXT NOT NULL,
      public_key TEXT NOT NULL,
      key_type TEXT DEFAULT 'Ed25519',
      is_active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      last_used_at TEXT
    )
  `);

  // Audit Log
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_type TEXT NOT NULL,
      event_category TEXT NOT NULL,
      schema_name TEXT,
      table_name TEXT,
      record_id TEXT,
      change_description TEXT,
      changed_by TEXT NOT NULL,
      changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
      previous_value TEXT,
      new_value TEXT,
      signature TEXT
    )
  `);

  // Dashboard Config
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS dashboard_config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      config_key TEXT NOT NULL UNIQUE,
      config_value TEXT NOT NULL,
      config_type TEXT DEFAULT 'string',
      description TEXT,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_by TEXT
    )
  `);

  // Tickers
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS tickers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      asset_class TEXT NOT NULL,
      exchange TEXT,
      is_active INTEGER DEFAULT 1,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Price Series
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS price_series (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      resolution TEXT NOT NULL,
      open REAL NOT NULL,
      high REAL NOT NULL,
      low REAL NOT NULL,
      close REAL NOT NULL,
      volume REAL,
      ingested_at TEXT DEFAULT CURRENT_TIMESTAMP,
      ingested_by TEXT DEFAULT 'LINE'
    )
  `);

  // Indicators
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS indicators (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      indicator_type TEXT NOT NULL,
      value REAL NOT NULL,
      parameters TEXT,
      calculated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Serper Events
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS serper_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id TEXT NOT NULL UNIQUE,
      event_type TEXT NOT NULL,
      title TEXT NOT NULL,
      description TEXT,
      source TEXT,
      source_url TEXT,
      relevance_score REAL,
      sentiment_score REAL,
      tickers TEXT,
      published_at TEXT,
      ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // CDS Metrics
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS cds_metrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      metric_id TEXT NOT NULL UNIQUE,
      cds_score REAL NOT NULL,
      cds_tier TEXT NOT NULL,
      conflict_count INTEGER,
      narrative_summary TEXT,
      top_conflicts TEXT,
      calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      calculated_by TEXT DEFAULT 'FINN'
    )
  `);

  // Daily Briefings
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS daily_briefings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      briefing_id TEXT NOT NULL UNIQUE,
      briefing_date TEXT NOT NULL,
      market_summary TEXT NOT NULL,
      key_events TEXT,
      risk_assessment TEXT,
      recommendations TEXT,
      generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      generated_by TEXT DEFAULT 'FINN'
    )
  `);

  // Signal Events
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS signal_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      signal_id TEXT NOT NULL UNIQUE,
      signal_type TEXT NOT NULL,
      ticker TEXT NOT NULL,
      strength REAL NOT NULL,
      confidence REAL NOT NULL,
      rationale TEXT,
      source_agent TEXT NOT NULL,
      generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      expires_at TEXT,
      is_active INTEGER DEFAULT 1
    )
  `);

  // Gate Status
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS gate_status (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      gate_id TEXT NOT NULL UNIQUE,
      gate_name TEXT NOT NULL,
      status TEXT NOT NULL,
      last_checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
      checked_by TEXT,
      failure_reason TEXT,
      metadata TEXT
    )
  `);

  // Data Freshness
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS data_freshness (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker TEXT NOT NULL,
      resolution TEXT NOT NULL,
      last_data_point TEXT,
      freshness_minutes INTEGER,
      status TEXT NOT NULL,
      checked_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Quality Scorecard
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS quality_scorecard (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      scorecard_id TEXT NOT NULL UNIQUE,
      overall_score REAL NOT NULL,
      quality_tier TEXT NOT NULL,
      dimension_scores TEXT,
      issues TEXT,
      evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      evaluated_by TEXT
    )
  `);

  // Governance State
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS governance_state (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      current_phase TEXT NOT NULL,
      production_mode INTEGER DEFAULT 0,
      architecture_freeze INTEGER DEFAULT 0,
      baseline_version TEXT,
      baseline_commit TEXT,
      approved_by TEXT,
      approved_at TEXT,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_by TEXT
    )
  `);

  // Economic Safety
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS economic_safety (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      metric_name TEXT NOT NULL UNIQUE,
      current_value REAL NOT NULL,
      ceiling REAL,
      floor REAL,
      unit TEXT,
      status TEXT NOT NULL,
      last_updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_by TEXT
    )
  `);

  // IoS Module Registry
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS ios_module_registry (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      module_id TEXT NOT NULL UNIQUE,
      module_name TEXT NOT NULL,
      description TEXT,
      status TEXT NOT NULL,
      version TEXT,
      data_lineage TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  // Orchestrator Tasks
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS orchestrator_tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      task_id TEXT NOT NULL UNIQUE,
      task_type TEXT NOT NULL,
      target_agent TEXT NOT NULL,
      action TEXT NOT NULL,
      parameters TEXT,
      requested_by TEXT NOT NULL,
      status TEXT NOT NULL,
      result TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      started_at TEXT,
      completed_at TEXT,
      idempotency_key TEXT
    )
  `);

  // Agent Chat History
  sqlite.exec(`
    CREATE TABLE IF NOT EXISTS agent_chat_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      chat_id TEXT NOT NULL,
      message_id TEXT NOT NULL UNIQUE,
      role TEXT NOT NULL,
      target_agent TEXT,
      content TEXT NOT NULL,
      task_type TEXT,
      linked_task_id TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  console.log('Tables created.');

  // Seed ADR Registry
  console.log('Seeding ADR Registry...');

  const adrs = [
    {
      adr_number: 'ADR-001',
      title: 'System Charter & Constitutional Framework',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'All FjordHQ systems and agents',
      author: 'LARS',
      purpose: 'Establish constitutional structure and domain ownership',
      authority_chain: 'ROOT',
      content_hash: generateHash('ADR-001-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-002',
      title: 'Audit Charter & Reconciliation',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'All data operations and governance events',
      author: 'LARS',
      purpose: 'Define audit logging, dual-ledger compliance, and reconciliation',
      authority_chain: 'ADR-001',
      content_hash: generateHash('ADR-002-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-003',
      title: 'Institutional Standards and Compliance Framework',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'All FjordHQ operations',
      author: 'LARS',
      purpose: 'BCBS-239, ISO 8000-110, ISO-42001, GIPS-2020, DORA compliance',
      authority_chain: 'ADR-001 → ADR-002',
      content_hash: generateHash('ADR-003-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-004',
      title: 'Change Gates Framework',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'All governance and configuration changes',
      author: 'LARS',
      purpose: 'Define G0-G4 change gates for governance control',
      authority_chain: 'ADR-001 → ADR-002 → ADR-003',
      content_hash: generateHash('ADR-004-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-005',
      title: 'Human Interaction & Application Layer Charter',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'CEO, Vision-IoS Dashboard, Orchestrator, VEGA, all agents',
      author: 'LARS',
      purpose: 'Define the only authorized human interface to FjordHQ – the Vision-IoS Dashboard',
      authority_chain: 'ADR-001 → ADR-002 → ADR-003 → ADR-004 → ADR-006 → ADR-007 → ADR-008 → ADR-009 → ADR-010 → ADR-011 → ADR-012',
      content_hash: generateHash('ADR-005-human-interaction-layer'),
      approved_by: 'CEO',
      approved_at: new Date().toISOString(),
    },
    {
      adr_number: 'ADR-006',
      title: 'VEGA Governance Charter',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'VEGA governance engine operations',
      author: 'LARS',
      purpose: 'Define VEGA as the governance enforcement engine',
      authority_chain: 'ADR-001 → ADR-002 → ADR-003 → ADR-004',
      content_hash: generateHash('ADR-006-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-007',
      title: 'Orchestrator Architecture',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'Orchestrator and multi-agent coordination',
      author: 'LARS',
      purpose: 'Define orchestrator task routing and agent coordination',
      authority_chain: 'ADR-001 → ADR-006',
      content_hash: generateHash('ADR-007-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-15T00:00:00Z',
    },
    {
      adr_number: 'ADR-008',
      title: 'Cryptographic Key Management',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'All agent keys and signatures',
      author: 'STIG',
      purpose: 'Define Ed25519 key management and rotation',
      authority_chain: 'ADR-001 → ADR-002',
      content_hash: generateHash('ADR-008-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-009',
      title: 'Agent Suspension Workflow',
      status: 'Approved',
      tier: 'Operational',
      scope: 'All agents',
      author: 'VEGA',
      purpose: 'Define governance approval workflow for agent suspension',
      authority_chain: 'ADR-006',
      content_hash: generateHash('ADR-009-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-010',
      title: 'State Reconciliation Methodology',
      status: 'Approved',
      tier: 'Operational',
      scope: 'All state management',
      author: 'STIG',
      purpose: 'Define state reconciliation and discrepancy scoring',
      authority_chain: 'ADR-002 → ADR-006',
      content_hash: generateHash('ADR-010-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-01T00:00:00Z',
    },
    {
      adr_number: 'ADR-011',
      title: 'Production Fortress & VEGA Test Suite',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'Production environment and testing',
      author: 'STIG',
      purpose: 'Define production fortress architecture and test requirements',
      authority_chain: 'ADR-006',
      content_hash: generateHash('ADR-011-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-15T00:00:00Z',
    },
    {
      adr_number: 'ADR-012',
      title: 'Economic Safety Architecture',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'Cost ceilings, rate limits, economic safety',
      author: 'VEGA',
      purpose: 'Define economic safety constraints and execution budgets',
      authority_chain: 'ADR-006',
      content_hash: generateHash('ADR-012-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-15T00:00:00Z',
    },
    {
      adr_number: 'ADR-013',
      title: 'FHQ-IoS Kernel Specification',
      status: 'Approved',
      tier: 'Constitutional',
      scope: 'Kernel vs Application layer separation',
      author: 'LARS',
      purpose: 'Define kernel specification and VEGA attestation architecture',
      authority_chain: 'ADR-001',
      content_hash: generateHash('ADR-013-content'),
      approved_by: 'CEO',
      approved_at: '2025-11-15T00:00:00Z',
    },
  ];

  const insertAdr = sqlite.prepare(`
    INSERT OR REPLACE INTO adr_registry
    (adr_number, title, status, tier, scope, author, purpose, authority_chain, content_hash, approved_by, approved_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  for (const adr of adrs) {
    insertAdr.run(
      adr.adr_number,
      adr.title,
      adr.status,
      adr.tier,
      adr.scope,
      adr.author,
      adr.purpose,
      adr.authority_chain,
      adr.content_hash,
      adr.approved_by,
      adr.approved_at
    );
  }
  console.log(`Seeded ${adrs.length} ADRs.`);

  // Seed Agent Keys
  console.log('Seeding Agent Keys...');
  const agents = [
    { agent_id: 'LARS', agent_name: 'Logic, Analytics & Research Strategy', public_key: 'ed25519:lars_pub_key_placeholder' },
    { agent_id: 'STIG', agent_name: 'Schema, Technical & Infrastructure Guardian', public_key: 'ed25519:stig_pub_key_placeholder' },
    { agent_id: 'LINE', agent_name: 'Lineage & Ingestion Engine', public_key: 'ed25519:line_pub_key_placeholder' },
    { agent_id: 'FINN', agent_name: 'Financial Intelligence & Narrative Navigator', public_key: 'ed25519:finn_pub_key_placeholder' },
    { agent_id: 'VEGA', agent_name: 'Governance Engine', public_key: 'ed25519:vega_pub_key_placeholder' },
  ];

  const insertAgent = sqlite.prepare(`
    INSERT OR REPLACE INTO agent_keys (agent_id, agent_name, public_key)
    VALUES (?, ?, ?)
  `);

  for (const agent of agents) {
    insertAgent.run(agent.agent_id, agent.agent_name, agent.public_key);
  }
  console.log(`Seeded ${agents.length} agents.`);

  // Seed Tickers
  console.log('Seeding Tickers...');
  const tickersList = [
    { ticker: 'BTC-USD', name: 'Bitcoin', asset_class: 'crypto', exchange: 'Binance' },
    { ticker: 'ETH-USD', name: 'Ethereum', asset_class: 'crypto', exchange: 'Binance' },
    { ticker: 'GSPC', name: 'S&P 500', asset_class: 'index', exchange: 'NYSE' },
    { ticker: 'DXY', name: 'US Dollar Index', asset_class: 'index', exchange: 'ICE' },
    { ticker: 'SOL-USD', name: 'Solana', asset_class: 'crypto', exchange: 'Binance' },
  ];

  const insertTicker = sqlite.prepare(`
    INSERT OR REPLACE INTO tickers (ticker, name, asset_class, exchange)
    VALUES (?, ?, ?, ?)
  `);

  for (const t of tickersList) {
    insertTicker.run(t.ticker, t.name, t.asset_class, t.exchange);
  }
  console.log(`Seeded ${tickersList.length} tickers.`);

  // Seed Gate Status
  console.log('Seeding Gate Status...');
  const gates = [
    { gate_id: 'G0', gate_name: 'Syntax & Format', status: 'PASS', checked_by: 'STIG' },
    { gate_id: 'G1', gate_name: 'Technical Validation', status: 'PASS', checked_by: 'STIG' },
    { gate_id: 'G2', gate_name: 'Governance Validation', status: 'PASS', checked_by: 'LARS' },
    { gate_id: 'G3', gate_name: 'Audit Verification', status: 'PASS', checked_by: 'VEGA' },
    { gate_id: 'G4', gate_name: 'CEO Approval', status: 'PASS', checked_by: 'CEO' },
  ];

  const insertGate = sqlite.prepare(`
    INSERT OR REPLACE INTO gate_status (gate_id, gate_name, status, checked_by)
    VALUES (?, ?, ?, ?)
  `);

  for (const gate of gates) {
    insertGate.run(gate.gate_id, gate.gate_name, gate.status, gate.checked_by);
  }
  console.log(`Seeded ${gates.length} gates.`);

  // Seed Governance State
  console.log('Seeding Governance State...');
  sqlite.exec(`
    INSERT OR REPLACE INTO governance_state
    (id, current_phase, production_mode, architecture_freeze, baseline_version, baseline_commit, approved_by, approved_at, updated_by)
    VALUES (1, 'PHASE_2_PRODUCTION_READY', 1, 1, 'v1.0', '4e9abd3', 'LARS', '${new Date().toISOString()}', 'LARS')
  `);
  console.log('Seeded governance state.');

  // Seed Economic Safety
  console.log('Seeding Economic Safety...');
  const economicMetrics = [
    { metric_name: 'daily_llm_cost', current_value: 2.45, ceiling: 10.0, unit: 'USD', status: 'SAFE', updated_by: 'VEGA' },
    { metric_name: 'cost_per_summary', current_value: 0.048, ceiling: 0.05, unit: 'USD', status: 'SAFE', updated_by: 'VEGA' },
    { metric_name: 'api_rate_limit', current_value: 45, ceiling: 100, unit: 'requests/min', status: 'SAFE', updated_by: 'VEGA' },
    { metric_name: 'execution_budget_used', current_value: 24.5, ceiling: 100, unit: 'percentage', status: 'SAFE', updated_by: 'VEGA' },
  ];

  const insertEconomic = sqlite.prepare(`
    INSERT OR REPLACE INTO economic_safety (metric_name, current_value, ceiling, unit, status, updated_by)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  for (const metric of economicMetrics) {
    insertEconomic.run(metric.metric_name, metric.current_value, metric.ceiling, metric.unit, metric.status, metric.updated_by);
  }
  console.log(`Seeded ${economicMetrics.length} economic safety metrics.`);

  // Seed Data Freshness
  console.log('Seeding Data Freshness...');
  const freshnessData = [
    { ticker: 'BTC-USD', resolution: '1h', last_data_point: new Date().toISOString(), freshness_minutes: 5, status: 'FRESH' },
    { ticker: 'BTC-USD', resolution: '1d', last_data_point: new Date().toISOString(), freshness_minutes: 120, status: 'FRESH' },
    { ticker: 'ETH-USD', resolution: '1h', last_data_point: new Date().toISOString(), freshness_minutes: 8, status: 'FRESH' },
    { ticker: 'GSPC', resolution: '1d', last_data_point: new Date().toISOString(), freshness_minutes: 360, status: 'STALE' },
  ];

  const insertFreshness = sqlite.prepare(`
    INSERT OR REPLACE INTO data_freshness (ticker, resolution, last_data_point, freshness_minutes, status)
    VALUES (?, ?, ?, ?, ?)
  `);

  for (const f of freshnessData) {
    insertFreshness.run(f.ticker, f.resolution, f.last_data_point, f.freshness_minutes, f.status);
  }
  console.log(`Seeded ${freshnessData.length} freshness records.`);

  // Seed CDS Metrics
  console.log('Seeding CDS Metrics...');
  const cdsData = {
    metric_id: `cds-${Date.now()}`,
    cds_score: 0.723,
    cds_tier: 'high',
    conflict_count: 5,
    narrative_summary: 'Fed rate pause signals dovish stance while Bitcoin rallies to new highs. Market exhibits cognitive dissonance between policy expectations and price action.',
    top_conflicts: JSON.stringify([
      { topic: 'Fed Policy vs BTC Price', severity: 0.85 },
      { topic: 'Inflation Data vs Market Rally', severity: 0.72 },
      { topic: 'Recession Fears vs Risk-On Behavior', severity: 0.68 },
    ]),
    calculated_by: 'FINN',
  };

  sqlite.prepare(`
    INSERT OR REPLACE INTO cds_metrics (metric_id, cds_score, cds_tier, conflict_count, narrative_summary, top_conflicts, calculated_by)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(cdsData.metric_id, cdsData.cds_score, cdsData.cds_tier, cdsData.conflict_count, cdsData.narrative_summary, cdsData.top_conflicts, cdsData.calculated_by);
  console.log('Seeded CDS metrics.');

  // Seed IoS Module Registry
  console.log('Seeding IoS Module Registry...');
  const iosModules = [
    {
      module_id: 'IoS-001',
      module_name: 'Market Pulse',
      description: 'High-level market state, cross-asset freshness, and volatility snapshot',
      status: 'Active',
      version: '1.0.0',
      data_lineage: JSON.stringify(['fhq_data.price_series', 'fhq_validation.data_freshness']),
    },
    {
      module_id: 'IoS-002',
      module_name: 'Alpha Drift Monitor',
      description: 'Monitors strategy performance, drift vs. baselines, and alpha stability',
      status: 'Active',
      version: '1.0.0',
      data_lineage: JSON.stringify(['vision_signals.alpha_signals', 'vision_signals.signal_baseline']),
    },
    {
      module_id: 'IoS-003',
      module_name: 'FINN Intelligence v3',
      description: 'External narrative, serper events, CDS metrics, narrative shift risk',
      status: 'Active',
      version: '3.0.0',
      data_lineage: JSON.stringify(['fhq_finn.serper_events', 'fhq_finn.cds_metrics', 'fhq_finn.daily_briefings']),
    },
    {
      module_id: 'IoS-006',
      module_name: 'Research Workspace',
      description: 'Agent chat interface for CEO interaction with LARS, FINN, STIG, LINE, VEGA',
      status: 'Active',
      version: '1.0.0',
      data_lineage: JSON.stringify(['orchestrator_tasks', 'agent_chat_history']),
    },
  ];

  const insertModule = sqlite.prepare(`
    INSERT OR REPLACE INTO ios_module_registry (module_id, module_name, description, status, version, data_lineage)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  for (const m of iosModules) {
    insertModule.run(m.module_id, m.module_name, m.description, m.status, m.version, m.data_lineage);
  }
  console.log(`Seeded ${iosModules.length} IoS modules.`);

  // Seed Sample Price Data
  console.log('Seeding sample price data...');
  const now = new Date();
  const priceData = [];

  // Generate last 30 days of daily BTC data
  for (let i = 30; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const basePrice = 95000 + Math.random() * 5000;
    priceData.push({
      ticker: 'BTC-USD',
      timestamp: date.toISOString().split('T')[0],
      resolution: '1d',
      open: basePrice,
      high: basePrice * (1 + Math.random() * 0.03),
      low: basePrice * (1 - Math.random() * 0.03),
      close: basePrice * (1 + (Math.random() - 0.5) * 0.02),
      volume: 10000 + Math.random() * 5000,
    });
  }

  const insertPrice = sqlite.prepare(`
    INSERT INTO price_series (ticker, timestamp, resolution, open, high, low, close, volume)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  for (const p of priceData) {
    insertPrice.run(p.ticker, p.timestamp, p.resolution, p.open, p.high, p.low, p.close, p.volume);
  }
  console.log(`Seeded ${priceData.length} price records.`);

  // Log ADR-005 registration in audit log
  console.log('Logging ADR-005 registration in audit log...');
  sqlite.prepare(`
    INSERT INTO audit_log (event_type, event_category, schema_name, table_name, record_id, change_description, changed_by)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(
    'ADR_REGISTRATION',
    'ClassA',
    'fhq_meta',
    'adr_registry',
    'ADR-005',
    'Registered ADR-005: Human Interaction & Application Layer Charter - Establishes Vision-IoS Dashboard as the only authorized human interface to FjordHQ',
    'VEGA'
  );
  console.log('ADR-005 registration logged.');

  // Seed Dashboard Config
  console.log('Seeding Dashboard Config...');
  const configs = [
    { config_key: 'refresh_interval_ms', config_value: '60000', config_type: 'number', description: 'Data refresh interval in milliseconds' },
    { config_key: 'default_ticker', config_value: 'BTC-USD', config_type: 'string', description: 'Default ticker for market data' },
    { config_key: 'theme', config_value: 'dark', config_type: 'string', description: 'Dashboard theme' },
    { config_key: 'show_lineage', config_value: 'true', config_type: 'boolean', description: 'Show data lineage indicators' },
    { config_key: 'cds_threshold_high', config_value: '0.7', config_type: 'number', description: 'CDS score threshold for high risk' },
    { config_key: 'freshness_threshold_minutes', config_value: '60', config_type: 'number', description: 'Data freshness threshold in minutes' },
  ];

  const insertConfig = sqlite.prepare(`
    INSERT OR REPLACE INTO dashboard_config (config_key, config_value, config_type, description, updated_by)
    VALUES (?, ?, ?, ?, ?)
  `);

  for (const c of configs) {
    insertConfig.run(c.config_key, c.config_value, c.config_type, c.description, 'SYSTEM');
  }
  console.log(`Seeded ${configs.length} config entries.`);

  console.log('\nDatabase seed completed successfully!');
  console.log(`Database location: ${dbPath}`);

  sqlite.close();
}

seed().catch(console.error);
