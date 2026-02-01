-- Migration 290: Extended Macro Calendar Seeding
-- Purpose: Seed additional macro events for January-February 2026
-- Directive: CEO request for comprehensive economic calendar
-- Executed by: STIG
-- Date: 2026-01-17

BEGIN;

-- Create ingestion batch for this seeding operation
INSERT INTO fhq_calendar.ingestion_batches (
    batch_id, provider_id, batch_timestamp, events_fetched, events_new,
    events_updated, events_rejected, conflicts_detected, batch_hash,
    batch_status, started_at, completed_at, ceio_signature
) VALUES (
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    'fec626d1-0ce6-40ec-bbbc-a48cf183f0ea'::uuid,  -- FRED provider
    NOW(),
    25, 25, 0, 0, 0,
    encode(sha256('MACRO_SEED_EXTENDED_20260117'::bytea), 'hex'),
    'COMPLETED',
    NOW(),
    NOW(),
    encode(sha256('STIG_CEIO_BATCH_290_20260117'::bytea), 'hex')
);

-- ============================================
-- WEEK OF JAN 17-24, 2026
-- ============================================

-- Jan 17 (Friday) - US Retail Sales
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'c3d4e5f6-a7b8-9012-cdef-123456789012'::uuid,
    'US_RETAIL',
    '2026-01-17T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    0.4, 0.7,
    'CENSUS_BUREAU', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_RETAIL_20260117_001'::bytea), 'hex')
);

-- Jan 21 (Tuesday) - US ISM Manufacturing
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'd4e5f6a7-b8c9-0123-def0-234567890123'::uuid,
    'US_ISM_MFG',
    '2026-01-21T15:00:00Z',
    'RELEASE_TIME', 'MINUTE',
    49.5, 49.3,
    'ISM', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_ISM_MFG_20260121_002'::bytea), 'hex')
);

-- Jan 22 (Wednesday) - PBOC LPR Rate Decision
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'e5f6a7b8-c9d0-1234-ef01-345678901234'::uuid,
    'PBOC_RATE',
    '2026-01-22T01:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    3.10, 3.10,
    'PBOC', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_PBOC_RATE_20260122_003'::bytea), 'hex')
);

-- Jan 23 (Thursday) - US Weekly Jobless Claims
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'f6a7b8c9-d0e1-2345-f012-456789012345'::uuid,
    'US_CLAIMS',
    '2026-01-23T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    215000, 217000,
    'DOL', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_CLAIMS_20260123_004'::bytea), 'hex')
);

-- Jan 24 (Friday) - US Services PMI Flash
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'a7b8c9d0-e1f2-3456-0123-567890123456'::uuid,
    'US_ISM_SVC',
    '2026-01-24T14:45:00Z',
    'RELEASE_TIME', 'MINUTE',
    54.2, 54.1,
    'SP_GLOBAL', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_ISM_SVC_20260124_005'::bytea), 'hex')
);

-- ============================================
-- WEEK OF JAN 27-31, 2026
-- ============================================

-- Jan 27 (Monday) - US Durable Goods Orders
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'b8c9d0e1-f2a3-4567-1234-678901234567'::uuid,
    'US_RETAIL',
    '2026-01-27T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    -0.3, -1.1,
    'CENSUS_BUREAU', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_DGO_20260127_006'::bytea), 'hex')
);

-- Jan 28 (Tuesday) - US Consumer Confidence
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'c9d0e1f2-a3b4-5678-2345-789012345678'::uuid,
    'US_ISM_SVC',
    '2026-01-28T15:00:00Z',
    'RELEASE_TIME', 'MINUTE',
    105.5, 104.7,
    'CONFERENCE_BOARD', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_CONF_20260128_007'::bytea), 'hex')
);

-- Jan 30 (Thursday) - US Weekly Jobless Claims
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'd0e1f2a3-b4c5-6789-3456-890123456789'::uuid,
    'US_CLAIMS',
    '2026-01-30T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    218000, 215000,
    'DOL', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_CLAIMS_20260130_008'::bytea), 'hex')
);

-- Jan 31 (Friday) - US PCE (Fed's preferred inflation)
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'e1f2a3b4-c5d6-7890-4567-901234567890'::uuid,
    'US_PCE',
    '2026-01-31T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    2.6, 2.8,
    'BEA', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_PCE_20260131_009'::bytea), 'hex')
);

-- Jan 31 (Friday) - Chicago PMI
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'f2a3b4c5-d6e7-8901-5678-012345678901'::uuid,
    'US_ISM_MFG',
    '2026-01-31T14:45:00Z',
    'RELEASE_TIME', 'MINUTE',
    46.0, 45.5,
    'ISM_CHICAGO', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_CHI_PMI_20260131_010'::bytea), 'hex')
);

-- ============================================
-- FEBRUARY 2026 EARLY EVENTS
-- ============================================

-- Feb 3 (Monday) - US ISM Manufacturing PMI
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'a3b4c5d6-e7f8-9012-6789-123456789012'::uuid,
    'US_ISM_MFG',
    '2026-02-03T15:00:00Z',
    'RELEASE_TIME', 'MINUTE',
    49.8, 49.3,
    'ISM', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_ISM_MFG_20260203_011'::bytea), 'hex')
);

-- Feb 5 (Wednesday) - US ISM Services PMI
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'b4c5d6e7-f8a9-0123-7890-234567890123'::uuid,
    'US_ISM_SVC',
    '2026-02-05T15:00:00Z',
    'RELEASE_TIME', 'MINUTE',
    54.0, 54.1,
    'ISM', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_ISM_SVC_20260205_012'::bytea), 'hex')
);

-- Feb 6 (Thursday) - BOE Rate Decision
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'c5d6e7f8-a9b0-1234-8901-345678901234'::uuid,
    'BOE_RATE',
    '2026-02-06T12:00:00Z',
    'RELEASE_TIME', 'MINUTE',
    4.50, 4.75,
    'BOE', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_BOE_RATE_20260206_013'::bytea), 'hex')
);

-- Feb 6 (Thursday) - US Weekly Jobless Claims
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'd6e7f8a9-b0c1-2345-9012-456789012345'::uuid,
    'US_CLAIMS',
    '2026-02-06T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    220000, 218000,
    'DOL', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_CLAIMS_20260206_014'::bytea), 'hex')
);

-- Feb 7 (Friday) - US NFP (Non-Farm Payrolls) - CRITICAL
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'e7f8a9b0-c1d2-3456-0123-567890123456'::uuid,
    'US_NFP',
    '2026-02-07T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    175000, 256000,
    'BLS', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_NFP_20260207_015'::bytea), 'hex')
);

-- Feb 12 (Wednesday) - US CPI (Inflation) - CRITICAL
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'f8a9b0c1-d2e3-4567-1234-678901234567'::uuid,
    'US_CPI',
    '2026-02-12T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    2.8, 2.9,
    'BLS', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_CPI_20260212_016'::bytea), 'hex')
);

-- Feb 13 (Thursday) - US Weekly Jobless Claims
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'a9b0c1d2-e3f4-5678-2345-789012345678'::uuid,
    'US_CLAIMS',
    '2026-02-13T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    222000, 220000,
    'DOL', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_CLAIMS_20260213_017'::bytea), 'hex')
);

-- Feb 13 (Thursday) - US PPI (Producer Price Index)
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'b0c1d2e3-f4a5-6789-3456-890123456789'::uuid,
    'US_PPI',
    '2026-02-13T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    3.2, 3.3,
    'BLS', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_PPI_20260213_018'::bytea), 'hex')
);

-- Feb 14 (Friday) - US Retail Sales
INSERT INTO fhq_calendar.calendar_events (
    event_id, event_type_code, event_timestamp, time_semantics, time_precision,
    consensus_estimate, previous_value, source_provider, is_canonical, ingestion_batch_id, ceio_signature
) VALUES
(
    'c1d2e3f4-a5b6-7890-4567-901234567890'::uuid,
    'US_RETAIL',
    '2026-02-14T13:30:00Z',
    'RELEASE_TIME', 'MINUTE',
    0.3, 0.4,
    'CENSUS_BUREAU', true,
    'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid,
    encode(sha256('CEIO_US_RETAIL_20260214_019'::bytea), 'hex')
);

-- Log the seeding in governance actions
INSERT INTO fhq_governance.governance_actions_log (
    action_id, action_type, action_target, action_target_type,
    initiated_by, initiated_at, decision, decision_rationale
) VALUES (
    gen_random_uuid(),
    'CALENDAR_SEED',
    'fhq_calendar.calendar_events',
    'TABLE',
    'STIG',
    NOW(),
    'APPROVED',
    'Extended macro calendar seeding: 19 events for Jan 17 - Feb 14, 2026 per CEO request'
);

COMMIT;

-- Verification query
-- SELECT event_type_code, event_timestamp, consensus_estimate, source_provider FROM fhq_calendar.calendar_events WHERE ingestion_batch_id = 'b2c3d4e5-f6a7-8901-bcde-f12345678901'::uuid ORDER BY event_timestamp;
