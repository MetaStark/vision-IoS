-- ============================================================
-- Migration 147: Phase 3 Causal Discovery Schema (STIG-2025-001)
-- ============================================================
-- Authority: STIG (CTO)
-- ADR Reference: STIG-2025-001 Directive Phase 3
-- Classification: Cognitive Alpha Infrastructure
--
-- Components:
--   1. VarClus Clustering Tables
--   2. PCMCI Causal Edge Tables (Macro + Micro)
--   3. Thompson Bandit State
--   4. RL Decision & Reward Ledger
-- ============================================================

BEGIN;

DO $$
BEGIN
    RAISE NOTICE '[147] Starting Phase 3 Causal Discovery Migration';
    RAISE NOTICE '[147] Authority: STIG-2025-001 Directive';
END $$;

-- ============================================================
-- 1. VARCLUS CLUSTERING TABLES
-- ============================================================

-- Asset Clusters (VarClus output)
CREATE TABLE IF NOT EXISTS fhq_alpha.asset_clusters (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL,
    cluster_id          INTEGER NOT NULL,
    cluster_name        TEXT,                   -- Human readable name e.g. "Tech Leaders"
    membership_score    DOUBLE PRECISION,       -- How strongly asset belongs to cluster
    features_used       JSONB DEFAULT '{}',     -- Features used for clustering
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asset_id)                            -- One cluster per asset
);

CREATE INDEX IF NOT EXISTS idx_asset_clusters_cluster
    ON fhq_alpha.asset_clusters(cluster_id);
CREATE INDEX IF NOT EXISTS idx_asset_clusters_asset
    ON fhq_alpha.asset_clusters(asset_id);

COMMENT ON TABLE fhq_alpha.asset_clusters IS
    'VarClus hierarchical clustering: 500 assets → 30 clusters per STIG-2025-001.';

-- Cluster Centroids (for PCMCI input)
CREATE TABLE IF NOT EXISTS fhq_alpha.cluster_centroids (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id          INTEGER NOT NULL,
    cluster_name        TEXT,
    centroid_return     DOUBLE PRECISION,
    centroid_volatility DOUBLE PRECISION,
    centroid_volume     DOUBLE PRECISION,
    member_count        INTEGER,
    representative_asset TEXT,                  -- Most central asset
    calculated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cluster_centroids_cluster
    ON fhq_alpha.cluster_centroids(cluster_id);
CREATE INDEX IF NOT EXISTS idx_cluster_centroids_calculated
    ON fhq_alpha.cluster_centroids(calculated_at DESC);

COMMENT ON TABLE fhq_alpha.cluster_centroids IS
    'Cluster centroids for macro-level PCMCI causal discovery.';

-- Clustering Run History
CREATE TABLE IF NOT EXISTS fhq_alpha.clustering_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              TEXT NOT NULL UNIQUE,
    n_assets            INTEGER,
    n_clusters          INTEGER,
    linkage_method      TEXT DEFAULT 'ward',
    lookback_days       INTEGER,
    silhouette_score    DOUBLE PRECISION,
    calinski_score      DOUBLE PRECISION,
    status              TEXT DEFAULT 'COMPLETED',
    metadata            JSONB DEFAULT '{}',
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

COMMENT ON TABLE fhq_alpha.clustering_runs IS
    'Audit trail for VarClus clustering executions.';

-- ============================================================
-- 2. PCMCI CAUSAL EDGE TABLES
-- ============================================================

-- Macro Causal Edges (Cluster-to-Cluster)
CREATE TABLE IF NOT EXISTS fhq_alpha.macro_causal_edges (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_cluster_id   INTEGER NOT NULL,
    target_cluster_id   INTEGER NOT NULL,
    lag                 INTEGER NOT NULL,       -- Time lag in bars
    edge_strength       DOUBLE PRECISION,       -- PCMCI partial correlation
    p_value             DOUBLE PRECISION,
    direction           TEXT,                   -- LEADING, LAGGING, CONCURRENT
    discovery_run_id    TEXT,
    discovered_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_cluster_id, target_cluster_id, lag)
);

CREATE INDEX IF NOT EXISTS idx_macro_edges_source
    ON fhq_alpha.macro_causal_edges(source_cluster_id);
CREATE INDEX IF NOT EXISTS idx_macro_edges_target
    ON fhq_alpha.macro_causal_edges(target_cluster_id);
CREATE INDEX IF NOT EXISTS idx_macro_edges_strength
    ON fhq_alpha.macro_causal_edges(edge_strength DESC);

COMMENT ON TABLE fhq_alpha.macro_causal_edges IS
    'PCMCI causal edges between cluster centroids. O(30²) complexity.';

-- Micro Causal Edges (Asset-to-Asset within linked clusters)
CREATE TABLE IF NOT EXISTS fhq_alpha.micro_causal_edges (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_asset        TEXT NOT NULL,
    target_asset        TEXT NOT NULL,
    source_cluster_id   INTEGER,
    target_cluster_id   INTEGER,
    lag                 INTEGER NOT NULL,
    edge_strength       DOUBLE PRECISION,
    p_value             DOUBLE PRECISION,
    direction           TEXT,
    macro_edge_id       UUID REFERENCES fhq_alpha.macro_causal_edges(id),
    discovery_run_id    TEXT,
    discovered_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_asset, target_asset, lag)
);

CREATE INDEX IF NOT EXISTS idx_micro_edges_source
    ON fhq_alpha.micro_causal_edges(source_asset);
CREATE INDEX IF NOT EXISTS idx_micro_edges_target
    ON fhq_alpha.micro_causal_edges(target_asset);
CREATE INDEX IF NOT EXISTS idx_micro_edges_strength
    ON fhq_alpha.micro_causal_edges(edge_strength DESC);

COMMENT ON TABLE fhq_alpha.micro_causal_edges IS
    'PCMCI causal edges between assets within macro-linked clusters.';

-- PCMCI Discovery Runs
CREATE TABLE IF NOT EXISTS fhq_alpha.pcmci_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              TEXT NOT NULL UNIQUE,
    run_type            TEXT,                   -- MACRO, MICRO
    n_variables         INTEGER,
    tau_max             INTEGER,
    pc_alpha            DOUBLE PRECISION,
    edges_discovered    INTEGER,
    compute_seconds     DOUBLE PRECISION,
    status              TEXT DEFAULT 'COMPLETED',
    metadata            JSONB DEFAULT '{}',
    started_at          TIMESTAMPTZ DEFAULT NOW(),
    completed_at        TIMESTAMPTZ
);

COMMENT ON TABLE fhq_alpha.pcmci_runs IS
    'Audit trail for PCMCI causal discovery executions.';

-- ============================================================
-- 3. THOMPSON BANDIT STATE
-- ============================================================

-- Per-Asset Bandit State
CREATE TABLE IF NOT EXISTS fhq_alpha.bandit_state (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL,
    regime              TEXT NOT NULL,
    action              TEXT NOT NULL,          -- SIZE_HALF, DELAY_1, etc.
    alpha               INTEGER DEFAULT 1,      -- Beta prior successes
    beta                INTEGER DEFAULT 1,      -- Beta prior failures
    total_pulls         INTEGER DEFAULT 0,
    last_updated        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(asset_id, regime, action)
);

CREATE INDEX IF NOT EXISTS idx_bandit_state_asset
    ON fhq_alpha.bandit_state(asset_id);
CREATE INDEX IF NOT EXISTS idx_bandit_state_regime
    ON fhq_alpha.bandit_state(regime);

COMMENT ON TABLE fhq_alpha.bandit_state IS
    'Thompson Sampling Beta priors per (asset, regime, action) triple.';

-- Bandit Action History
CREATE TABLE IF NOT EXISTS fhq_alpha.bandit_actions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL,
    regime              TEXT NOT NULL,
    sizing_action       TEXT,
    timing_action       TEXT,
    sampled_probability DOUBLE PRECISION,
    selected_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bandit_actions_asset
    ON fhq_alpha.bandit_actions(asset_id);
CREATE INDEX IF NOT EXISTS idx_bandit_actions_selected
    ON fhq_alpha.bandit_actions(selected_at DESC);

COMMENT ON TABLE fhq_alpha.bandit_actions IS
    'Thompson Sampling action selection audit trail.';

-- ============================================================
-- 4. RL DECISION & REWARD LEDGER
-- ============================================================

-- RL Decisions (per-asset)
CREATE TABLE IF NOT EXISTS fhq_alpha.rl_decisions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL,
    sizing_action       TEXT,
    timing_action       TEXT,
    sizing_multiplier   DOUBLE PRECISION,
    delay_bars          INTEGER,
    confidence          DOUBLE PRECISION,
    causal_parents      JSONB DEFAULT '[]',
    state_dim           INTEGER,
    regime              TEXT,
    generated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rl_decisions_asset
    ON fhq_alpha.rl_decisions(asset_id);
CREATE INDEX IF NOT EXISTS idx_rl_decisions_generated
    ON fhq_alpha.rl_decisions(generated_at DESC);

COMMENT ON TABLE fhq_alpha.rl_decisions IS
    'Causal RL decisions with state dimensionality from causal parents only.';

-- RL Rewards (feedback for bandit update)
CREATE TABLE IF NOT EXISTS fhq_alpha.rl_rewards (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id            TEXT NOT NULL,
    action_taken        TEXT,
    pnl                 DOUBLE PRECISION,
    risk_adjusted_return DOUBLE PRECISION,
    holding_period      INTEGER,
    regime_at_entry     TEXT,
    regime_at_exit      TEXT,
    causal_alignment    DOUBLE PRECISION,       -- Did parents predict correctly?
    decision_id         UUID REFERENCES fhq_alpha.rl_decisions(id),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rl_rewards_asset
    ON fhq_alpha.rl_rewards(asset_id);
CREATE INDEX IF NOT EXISTS idx_rl_rewards_created
    ON fhq_alpha.rl_rewards(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rl_rewards_pnl
    ON fhq_alpha.rl_rewards(pnl DESC);

COMMENT ON TABLE fhq_alpha.rl_rewards IS
    'RL reward signals for Thompson Sampling bandit updates.';

-- ============================================================
-- 5. HELPER VIEWS
-- ============================================================

-- Causal Parent Summary View
CREATE OR REPLACE VIEW fhq_alpha.v_causal_parents AS
SELECT
    mce.target_asset AS asset,
    mce.source_asset AS causal_parent,
    mce.lag,
    mce.edge_strength,
    mce.direction,
    ac_source.cluster_name AS parent_cluster,
    ac_target.cluster_name AS asset_cluster
FROM fhq_alpha.micro_causal_edges mce
LEFT JOIN fhq_alpha.asset_clusters ac_source ON ac_source.asset_id = mce.source_asset
LEFT JOIN fhq_alpha.asset_clusters ac_target ON ac_target.asset_id = mce.target_asset
WHERE mce.edge_strength > 0.1
ORDER BY mce.target_asset, mce.edge_strength DESC;

COMMENT ON VIEW fhq_alpha.v_causal_parents IS
    'Convenient view of causal parents per asset with cluster context.';

-- RL Performance Summary View
CREATE OR REPLACE VIEW fhq_alpha.v_rl_performance AS
SELECT
    r.asset_id,
    COUNT(*) AS total_trades,
    SUM(r.pnl) AS total_pnl,
    AVG(r.pnl) AS avg_pnl,
    AVG(r.risk_adjusted_return) AS avg_risk_adj_return,
    AVG(r.causal_alignment) AS avg_causal_alignment,
    COUNT(*) FILTER (WHERE r.pnl > 0) AS winning_trades,
    COUNT(*) FILTER (WHERE r.pnl <= 0) AS losing_trades,
    ROUND(100.0 * COUNT(*) FILTER (WHERE r.pnl > 0) / NULLIF(COUNT(*), 0), 2) AS win_rate_pct
FROM fhq_alpha.rl_rewards r
GROUP BY r.asset_id
ORDER BY total_pnl DESC;

COMMENT ON VIEW fhq_alpha.v_rl_performance IS
    'RL performance summary per asset with win rate and causal alignment.';

-- Cluster Causal Flow View
CREATE OR REPLACE VIEW fhq_alpha.v_cluster_causal_flow AS
SELECT
    cc_source.cluster_name AS source_cluster,
    cc_target.cluster_name AS target_cluster,
    mce.lag,
    mce.edge_strength,
    mce.direction,
    cc_source.member_count AS source_members,
    cc_target.member_count AS target_members
FROM fhq_alpha.macro_causal_edges mce
JOIN fhq_alpha.cluster_centroids cc_source
    ON cc_source.cluster_id = mce.source_cluster_id
JOIN fhq_alpha.cluster_centroids cc_target
    ON cc_target.cluster_id = mce.target_cluster_id
WHERE mce.edge_strength > 0.1
ORDER BY mce.edge_strength DESC;

COMMENT ON VIEW fhq_alpha.v_cluster_causal_flow IS
    'Macro causal flow between clusters with member counts.';

COMMIT;

-- ============================================================
-- VERIFICATION
-- ============================================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM information_schema.tables
    WHERE table_schema = 'fhq_alpha'
      AND table_name IN (
          'asset_clusters',
          'cluster_centroids',
          'clustering_runs',
          'macro_causal_edges',
          'micro_causal_edges',
          'pcmci_runs',
          'bandit_state',
          'bandit_actions',
          'rl_decisions',
          'rl_rewards'
      );

    IF v_count >= 10 THEN
        RAISE NOTICE '[147] SUCCESS: Phase 3 Causal Discovery tables created (% tables)', v_count;
    ELSE
        RAISE WARNING '[147] INCOMPLETE: Only % tables found', v_count;
    END IF;
END $$;

-- Show table summary
SELECT
    table_schema,
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns c
     WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'fhq_alpha'
  AND table_name IN (
      'asset_clusters',
      'cluster_centroids',
      'clustering_runs',
      'macro_causal_edges',
      'micro_causal_edges',
      'pcmci_runs',
      'bandit_state',
      'bandit_actions',
      'rl_decisions',
      'rl_rewards'
  )
ORDER BY table_name;
