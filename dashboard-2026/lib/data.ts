/**
 * Data fetching utilities for Vision-IoS Dashboard
 * Server-side functions to query the local SQLite database
 */

import { db } from '@/db';
import {
  adrRegistry,
  gateStatus,
  dataFreshness,
  cdsMetrics,
  economicSafety,
  governanceState,
  priceSeries,
  serperEvents,
  signalEvents,
  dailyBriefings,
  tickers,
  iosModuleRegistry,
  dashboardConfig,
  auditLog,
  agentKeys,
} from '@/db/schema';
import { desc, eq, and, gte, sql } from 'drizzle-orm';

// ============================================================================
// System Health & Trust Banner Data
// ============================================================================

export async function getSystemHealth() {
  const [gates, freshness, cds, economic, governance] = await Promise.all([
    db.select().from(gateStatus).all(),
    db.select().from(dataFreshness).all(),
    db.select().from(cdsMetrics).orderBy(desc(cdsMetrics.calculatedAt)).limit(1).all(),
    db.select().from(economicSafety).all(),
    db.select().from(governanceState).limit(1).all(),
  ]);

  const allGatesPass = gates.every(g => g.status === 'PASS');
  const freshData = freshness.filter(f => f.status === 'FRESH').length;
  const staleData = freshness.filter(f => f.status !== 'FRESH').length;
  const latestCds = cds[0];
  const economicStatus = economic.every(e => e.status === 'SAFE') ? 'SAFE' : 'WARNING';

  return {
    gates: {
      all: gates,
      allPass: allGatesPass,
      summary: `${gates.filter(g => g.status === 'PASS').length}/${gates.length} gates passing`,
    },
    freshness: {
      all: freshness,
      fresh: freshData,
      stale: staleData,
      status: staleData === 0 ? 'FRESH' : staleData > freshData ? 'CRITICAL' : 'STALE',
    },
    cds: latestCds ? {
      score: latestCds.cdsScore,
      tier: latestCds.cdsTier,
      summary: latestCds.narrativeSummary,
      conflicts: latestCds.topConflicts ? JSON.parse(latestCds.topConflicts) : [],
    } : null,
    economic: {
      all: economic,
      status: economicStatus,
    },
    governance: governance[0] || null,
    overall: allGatesPass && staleData === 0 && economicStatus === 'SAFE' ? 'HEALTHY' : 'DEGRADED',
  };
}

// ============================================================================
// ADR Registry
// ============================================================================

export async function getAdrRegistry() {
  return db.select().from(adrRegistry).orderBy(adrRegistry.adrNumber).all();
}

export async function getAdrByNumber(adrNumber: string) {
  return db.select().from(adrRegistry).where(eq(adrRegistry.adrNumber, adrNumber)).get();
}

// ============================================================================
// Market Data
// ============================================================================

export async function getTickers() {
  return db.select().from(tickers).where(eq(tickers.isActive, true)).all();
}

export async function getPriceData(ticker: string, resolution: string = '1d', limit: number = 30) {
  return db.select()
    .from(priceSeries)
    .where(and(
      eq(priceSeries.ticker, ticker),
      eq(priceSeries.resolution, resolution)
    ))
    .orderBy(desc(priceSeries.timestamp))
    .limit(limit)
    .all();
}

export async function getLatestPrice(ticker: string) {
  return db.select()
    .from(priceSeries)
    .where(eq(priceSeries.ticker, ticker))
    .orderBy(desc(priceSeries.timestamp))
    .limit(1)
    .get();
}

export async function getDataFreshness(ticker?: string) {
  if (ticker) {
    return db.select().from(dataFreshness).where(eq(dataFreshness.ticker, ticker)).all();
  }
  return db.select().from(dataFreshness).all();
}

// ============================================================================
// FINN Intelligence
// ============================================================================

export async function getLatestCds() {
  return db.select()
    .from(cdsMetrics)
    .orderBy(desc(cdsMetrics.calculatedAt))
    .limit(1)
    .get();
}

export async function getSerperEvents(limit: number = 20) {
  return db.select()
    .from(serperEvents)
    .orderBy(desc(serperEvents.ingestedAt))
    .limit(limit)
    .all();
}

export async function getHighRelevanceEvents(minRelevance: number = 0.7, limit: number = 10) {
  return db.select()
    .from(serperEvents)
    .where(gte(serperEvents.relevanceScore, minRelevance))
    .orderBy(desc(serperEvents.relevanceScore))
    .limit(limit)
    .all();
}

export async function getLatestBriefing() {
  return db.select()
    .from(dailyBriefings)
    .orderBy(desc(dailyBriefings.briefingDate))
    .limit(1)
    .get();
}

export async function getSignals(limit: number = 20, activeOnly: boolean = true) {
  const query = activeOnly
    ? db.select().from(signalEvents).where(eq(signalEvents.isActive, true))
    : db.select().from(signalEvents);

  return query.orderBy(desc(signalEvents.generatedAt)).limit(limit).all();
}

// ============================================================================
// Governance
// ============================================================================

export async function getGovernanceState() {
  return db.select().from(governanceState).limit(1).get();
}

export async function getGateStatus() {
  return db.select().from(gateStatus).all();
}

export async function getEconomicSafety() {
  return db.select().from(economicSafety).all();
}

// ============================================================================
// IoS Modules
// ============================================================================

export async function getIosModules() {
  return db.select().from(iosModuleRegistry).all();
}

export async function getIosModule(moduleId: string) {
  return db.select().from(iosModuleRegistry).where(eq(iosModuleRegistry.moduleId, moduleId)).get();
}

// ============================================================================
// Dashboard Config
// ============================================================================

export async function getDashboardConfig() {
  const configs = await db.select().from(dashboardConfig).all();
  return configs.reduce((acc, c) => {
    let value: any = c.configValue;
    if (c.configType === 'number') value = parseFloat(c.configValue);
    if (c.configType === 'boolean') value = c.configValue === 'true';
    if (c.configType === 'json') value = JSON.parse(c.configValue);
    acc[c.configKey] = value;
    return acc;
  }, {} as Record<string, any>);
}

// ============================================================================
// Audit Log
// ============================================================================

export async function getRecentAuditLogs(limit: number = 50) {
  return db.select()
    .from(auditLog)
    .orderBy(desc(auditLog.changedAt))
    .limit(limit)
    .all();
}

// ============================================================================
// Agents
// ============================================================================

export async function getAgents() {
  return db.select().from(agentKeys).where(eq(agentKeys.isActive, true)).all();
}
