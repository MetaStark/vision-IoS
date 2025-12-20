-- ============================================================================
-- MIGRATION 110: IoS-002 Adj Close Column (Dual Price Ontology)
-- ============================================================================
-- Purpose: Add adj_close column to prices table for IoS-002 compliance
-- Rationale: GIPS-aligned Dual Price Ontology requires two price semantics:
--   - close: Execution Truth (actual trade price for IoS-004, P&L)
--   - adj_close: Signal Truth (total return adjusted for IoS-002, IoS-003)
--
-- For Crypto/FX: adj_close = close (no corporate actions)
-- For Equities: adj_close = adjusted for splits/dividends
-- ============================================================================

BEGIN;

-- Add adj_close column to prices table
ALTER TABLE fhq_market.prices
ADD COLUMN IF NOT EXISTS adj_close DOUBLE PRECISION;

-- Add comment for documentation
COMMENT ON COLUMN fhq_market.prices.adj_close IS
    'IoS-002 Signal Truth: Adjusted close price for total return calculations. '
    'Used by IoS-002 (indicators), IoS-003 (regime). For Crypto/FX equals close. '
    'For equities adjusted for splits and dividends per GIPS standards.';

-- Set adj_close = close for existing rows (conservative default)
UPDATE fhq_market.prices
SET adj_close = close
WHERE adj_close IS NULL;

-- Add constraint to ensure adj_close is positive when provided
ALTER TABLE fhq_market.prices
ADD CONSTRAINT prices_adj_close_positive
CHECK (adj_close IS NULL OR adj_close > 0);

-- Log migration to governance
INSERT INTO fhq_governance.governance_actions_log (
    action_type,
    action_target,
    action_target_type,
    initiated_by,
    decision,
    decision_rationale,
    hash_chain_id
) VALUES (
    'SCHEMA_MIGRATION',
    'fhq_market.prices.adj_close',
    'COLUMN',
    'STIG',
    'APPROVED',
    'Added adj_close column for IoS-002 Dual Price Ontology compliance (GIPS-aligned: close=Execution Truth, adj_close=Signal Truth)',
    encode(sha256(('M110:' || NOW()::TEXT)::BYTEA), 'hex')
);

COMMIT;

-- Verification
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'fhq_market'
  AND table_name = 'prices'
  AND column_name = 'adj_close';
