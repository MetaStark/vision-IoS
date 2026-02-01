  // ============================================
  // FjordHQ Vision-IoS Database Schema
  // CEO-DIR-2026-046 | Generated: 2026-01-13
  // Total: 955 tables across 34 schemas
  // ============================================

  // ============================================
  // GOVERNANCE LAYER (fhq_governance - 196 tables)
  // ============================================

  Table fhq_meta.adr_registry {
    adr_id varchar [pk, note: 'ADR identifier (e.g., ADR-001)']
    adr_title text [note: 'Full title']
    adr_status varchar [note: 'APPROVED, DRAFT, DEPRECATED']
    adr_type varchar [note: 'CONSTITUTIONAL, ARCHITECTURAL']
    governance_tier text [note: 'Tier-1, Tier-2, Tier-3']
    vega_attested boolean [note: 'VEGA approval status']
    sha256_hash char(64) [note: 'Content hash']
    created_at timestamptz

    indexes {
      adr_id [unique]
      adr_status
    }
  }

  Table fhq_meta.ios_registry {
    ios_id text [pk, note: 'IoS identifier (e.g., IoS-001)']
    title text
    status text [note: 'ACTIVE, G0_SUBMITTED, DORMANT']
    owner_role text [note: 'STIG, FINN, LINE, LARS']
    governance_state text
    canonical boolean [note: 'Part of canonical stack']
    hash_chain_id uuid
    created_at timestamptz
    activated_at timestamptz
  }

  Table fhq_governance.agent_mandates {
    mandate_id uuid [pk]
    agent_name text [unique, note: 'LARS, STIG, FINN, LINE, VEGA, CSEO, CDMO, CRIO, CEIO, CFAO']
    mandate_type text [note: 'executive, subexecutive, constitutional']
    authority_type text [note: 'STRATEGIC, INFRASTRUCTURE, METHODOLOGICAL, EXECUTION, GOVERNANCE, OPERATIONAL, DATASET, MODEL']
    parent_agent text [note: 'Hierarchy parent']
    mandate_document jsonb
    created_at timestamptz
  }

  Table fhq_governance.agent_heartbeats {
    heartbeat_id int [pk, increment]
    agent_id varchar [note: 'Agent identifier']
    component varchar [note: 'ORCHESTRATOR, GOVERNANCE, RESEARCH, EXECUTION, DATA, GRAPH, EVIDENCE']
    current_task varchar
    health_score numeric [note: '0.0 to 1.0']
    events_processed int
    errors_count int
    last_heartbeat timestamptz
    liveness_basis text [note: 'Evidence of liveness']
    created_at timestamptz

    indexes {
      agent_id
      last_heartbeat
    }
  }

  Table fhq_governance.agent_contracts {
    contract_id uuid [pk]
    source_agent text
    target_agent text
    trigger_event text
    expected_action text
    sla_seconds int [note: 'SLA in seconds']
    metadata jsonb
    created_at timestamp
  }

  Table fhq_governance.defcon_state {
    state_id uuid [pk]
    defcon_level varchar [note: 'GREEN, YELLOW, ORANGE, RED, BLACK']
    triggered_at timestamptz
    triggered_by varchar [note: 'Agent that triggered']
    trigger_reason text
    auto_expire_at timestamptz
    is_current boolean [note: 'Active state flag']
    created_at timestamptz

    indexes {
      is_current
      defcon_level
    }
  }

  Table fhq_governance.defcon_transitions {
    transition_id uuid [pk]
    from_level varchar
    to_level varchar
    triggered_by varchar
    reason text
    transition_at timestamptz
  }

  Table fhq_governance.data_blackout_state {
    blackout_id uuid [pk]
    is_active boolean
    trigger_reason text
    triggered_by varchar
    triggered_at timestamptz
    cleared_by varchar
    cleared_at timestamptz
    vega_attestation_id varchar
    stale_assets text[]
    created_at timestamptz
  }

  Table fhq_governance.task_registry {
    task_id uuid [pk]
    task_name varchar [unique]
    task_type varchar [note: 'VISION_FUNCTION, DAEMON, SENTINEL']
    agent_id varchar
    task_description text
    task_config jsonb
    enabled boolean
    status text
    created_at timestamp
    updated_at timestamptz

    indexes {
      task_name
      enabled
      agent_id
    }
  }

  Table fhq_governance.governance_actions_log {
    action_id uuid [pk]
    action_type varchar [note: 'CNRP_*, VISION_ORCHESTRATOR_*, IOS003_*']
    action_target varchar
    action_target_type varchar
    initiated_by varchar
    initiated_at timestamptz
    decision varchar [note: 'SUCCESS, EXECUTED, ATTENTION_REQUIRED, COMPLETED_WITH_FAILURES']
    decision_rationale text
    metadata jsonb
    hash_chain_id varchar
    signature text [note: 'Ed25519 signature']
    vega_reviewed boolean
    vega_override boolean
    agent_id varchar
    timestamp timestamptz

    indexes {
      action_type
      initiated_at
      agent_id
    }
  }

  Table fhq_governance.execution_state {
    state_id int [pk]
    cycle_id varchar
    hash_chain_id varchar
    state_data jsonb
    created_at timestamptz
    cognitive_fasting boolean
    fasting_reason text
    revalidation_required boolean
    last_cnrp_completion timestamptz
    last_lids_block_at timestamptz
    last_lids_block_type varchar
    lids_blocks_today int
    lids_passes_today int
    defcon_level varchar
    last_updated_at timestamptz
    last_updated_by varchar
    last_update_reason text
    paper_trading_eligible boolean
    learning_eligible boolean
    state_version int
  }

  // ============================================
  // PERCEPTION LAYER (fhq_perception - 21 tables)
  // ============================================

  Table fhq_perception.regime_daily {
    id uuid [pk]
    asset_id text [note: 'Canonical asset ID (e.g., BTC-USD, AAPL)']
    timestamp date [note: 'Regime date']
    regime_classification text [note: 'BULL, BEAR, NEUTRAL, STRONG_BULL, STRONG_BEAR, RANGE_UP, RANGE_DOWN, PARABOLIC, BROKEN']
    regime_stability_flag boolean
    regime_confidence numeric [note: '0.0 to 1.0']
    consecutive_confirms int
    prior_regime text
    regime_change_date date
    anomaly_flag boolean
    anomaly_type text
    anomaly_severity text
    engine_version text
    perception_model_version text
    formula_hash text
    lineage_hash text [note: 'BCBS-239 lineage']
    hash_prev text [note: 'Previous hash in chain']
    hash_self text [note: 'Current hash']
    created_at timestamptz
    technical_regime text
    changepoint_probability numeric
    run_length int
    hmm_version text

    indexes {
      (asset_id, timestamp) [unique]
      timestamp
      regime_classification
    }
  }

  // ============================================
  // RESEARCH LAYER (fhq_research - 178 tables)
  // ============================================

  Table fhq_research.regime_predictions_v2 {
    prediction_id uuid [pk]
    asset_id text
    timestamp date
    model_id uuid
    perception_model_version text
    regime_raw int [note: '0-8 regime state']
    regime_label text
    confidence_score numeric
    created_at timestamptz
    lineage_hash text
    hash_prev text
    hash_self text

    indexes {
      (asset_id, timestamp)
      timestamp
    }
  }

  Table fhq_research.forecast_skill_registry {
    skill_id uuid [pk]
    strategy_id text
    fss_score numeric [note: 'FjordHQ Skill Score']
    sharpe_ratio numeric
    max_drawdown numeric
    calculated_at timestamptz
  }

  // ============================================
  // MARKET DATA (fhq_market - 7 tables)
  // ============================================

  Table fhq_market.prices {
    id uuid [pk]
    asset_id uuid
    canonical_id text [note: 'Canonical asset ID']
    timestamp timestamp
    open float
    high float
    low float
    close float [note: 'Execution truth']
    adj_close float [note: 'Signal truth']
    volume float
    source text [note: 'yfinance, alpaca, coingecko']

    indexes {
      (canonical_id, timestamp) [unique]
      timestamp
    }
  }

  // ============================================
  // META LAYER (fhq_meta - 144 tables)
  // ============================================

  Table fhq_meta.assets {
    asset_id uuid [pk]
    canonical_id text [unique, note: 'e.g., BTC-USD, AAPL']
    asset_class text [note: 'crypto, equity, fx, index, commodity']
    exchange_id text
    liquidity_tier text [note: 'TIER_1, TIER_2, TIER_3']
    is_active boolean
    created_at timestamptz

    indexes {
      canonical_id [unique]
      asset_class
      is_active
    }
  }

  Table fhq_meta.exchanges {
    exchange_id text [pk, note: 'e.g., XCRY, XNYS, XNAS']
    exchange_name text
    mic_code text
    timezone text
    is_active boolean
  }

  // ============================================
  // VERIFICATION LAYER (vision_verification - 19 tables)
  // ============================================

  Table vision_verification.summary_evidence_ledger {
    evidence_id uuid [pk]
    summary_id varchar
    summary_type varchar [note: 'EVIDENCE_UNIFICATION_SYNC, REGIME_UPDATE, NIGHTLY_INSIGHT']
    generating_agent varchar [note: 'STIG, FINN, VEGA']
    raw_query text [note: 'Exact SQL executed']
    query_result_hash varchar(64) [note: 'SHA-256 of results']
    query_result_snapshot jsonb [note: 'Actual query results']
    summary_content jsonb
    summary_hash varchar(64)
    created_at timestamptz
    execution_context jsonb
    evidence_signature varchar [note: 'Ed25519 signature']
    signature_verified boolean
    governance_action_id uuid
    attestation_id uuid
    is_deterministic boolean
    determinism_violations jsonb
    canonical_json_hash varchar

    indexes {
      summary_type
      generating_agent
      created_at
    }
  }

  // ============================================
  // SIGNALS LAYER (vision_signals - 15 tables)
  // ============================================

  Table vision_signals.alpha_signals {
    signal_id uuid [pk]
    asset_id text
    signal_type varchar [note: 'BUY, SELL, HOLD']
    signal_strength numeric
    confidence numeric
    regime_context text
    quad_hash varchar [note: 'MIT Quad hash']
    lineage_hash varchar
    created_at timestamptz
    expires_at timestamptz

    indexes {
      asset_id
      created_at
      signal_type
    }
  }

  // ============================================
  // EXECUTION LAYER (fhq_execution - 39 tables)
  // ============================================

  Table fhq_execution.orders {
    order_id uuid [pk]
    asset_id text
    order_type varchar [note: 'MARKET, LIMIT']
    side varchar [note: 'BUY, SELL']
    quantity numeric
    price numeric
    status varchar [note: 'PENDING, FILLED, CANCELLED']
    signal_id uuid
    created_at timestamptz
    executed_at timestamptz
  }

  // ============================================
  // POSITIONS LAYER (fhq_positions - 16 tables)
  // ============================================

  Table fhq_positions.portfolio_weights {
    weight_id uuid [pk]
    asset_id text
    target_weight numeric
    actual_weight numeric
    regime_context text
    rebalance_date date
    created_at timestamptz
  }

  // ============================================
  // MACRO LAYER (fhq_macro - 16 tables)
  // ============================================

  Table fhq_macro.feature_registry {
    feature_id uuid [pk]
    feature_name text [note: 'e.g., GLOBAL_M2_USD, US_10Y_REAL']
    cluster text [note: 'LIQUIDITY, CREDIT, VOLATILITY, FACTOR']
    source text [note: 'FRED, BLOOMBERG, YAHOO']
    frequency text
    is_stationary boolean
    created_at timestamptz
  }

  Table fhq_macro.canonical_series {
    series_id uuid [pk]
    feature_id uuid
    observation_date date
    value numeric
    lineage_hash text
    created_at timestamptz

    indexes {
      (feature_id, observation_date) [unique]
    }
  }

  // ============================================
  // GRAPH LAYER (fhq_graph - 10 tables)
  // ============================================

  Table fhq_graph.nodes {
    node_id uuid [pk]
    node_type text [note: 'MACRO, REGIME, ASSET']
    node_name text
    node_data jsonb
    created_at timestamptz
  }

  Table fhq_graph.edges {
    edge_id uuid [pk]
    source_node_id uuid
    target_node_id uuid
    edge_type text [note: 'LEADS, INHIBITS, AMPLIFIES, COUPLES, BREAKS']
    edge_strength numeric
    p_value numeric
    is_significant boolean
    created_at timestamptz
  }

  // ============================================
  // RELATIONSHIPS
  // ============================================

  // Agent Hierarchy
  Ref: fhq_governance.agent_mandates.parent_agent > fhq_governance.agent_mandates.agent_name

  // Agent to Heartbeat
  Ref: fhq_governance.agent_heartbeats.agent_id > fhq_governance.agent_mandates.agent_name

  // Task to Agent
  Ref: fhq_governance.task_registry.agent_id > fhq_governance.agent_mandates.agent_name

  // Governance Action to Agent
  Ref: fhq_governance.governance_actions_log.agent_id > fhq_governance.agent_mandates.agent_name

  // Regime to Asset
  Ref: fhq_perception.regime_daily.asset_id > fhq_meta.assets.canonical_id

  // Price to Asset
  Ref: fhq_market.prices.canonical_id > fhq_meta.assets.canonical_id

  // Asset to Exchange
  Ref: fhq_meta.assets.exchange_id > fhq_meta.exchanges.exchange_id

  // Macro series to feature
  Ref: fhq_macro.canonical_series.feature_id > fhq_macro.feature_registry.feature_id

  // Graph edges to nodes
  Ref: fhq_graph.edges.source_node_id > fhq_graph.nodes.node_id
  Ref: fhq_graph.edges.target_node_id > fhq_graph.nodes.node_id

  // Evidence to governance action
  Ref: vision_verification.summary_evidence_ledger.governance_action_id > fhq_governance.governance_actions_log.action_id

  // Signal to order
  Ref: fhq_execution.orders.signal_id > vision_signals.alpha_signals.signal_id

  // ============================================
  // TABLE GROUPS
  // ============================================

  TableGroup governance {
    fhq_meta.adr_registry
    fhq_meta.ios_registry
    fhq_governance.agent_mandates
    fhq_governance.agent_heartbeats
    fhq_governance.defcon_state
    fhq_governance.data_blackout_state
    fhq_governance.task_registry
    fhq_governance.governance_actions_log
    fhq_governance.execution_state
  }

  TableGroup perception {
    fhq_perception.regime_daily
    fhq_research.regime_predictions_v2
  }

  TableGroup data {
    fhq_meta.assets
    fhq_meta.exchanges
    fhq_market.prices
    fhq_macro.feature_registry
    fhq_macro.canonical_series
  }

  TableGroup signals {
    vision_signals.alpha_signals
    vision_verification.summary_evidence_ledger
  }

  TableGroup execution {
    fhq_execution.orders
    fhq_positions.portfolio_weights
  }

  TableGroup graph {
    fhq_graph.nodes
    fhq_graph.edges
  }
