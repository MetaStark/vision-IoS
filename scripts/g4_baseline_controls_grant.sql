-- ============================================================================
-- G4-BESLUTNING — KREVER VEGA-ORDRE FOER KJOERING. IKKE KJOER AUTOMATISK.
-- ============================================================================
-- Grunnlag (court-proof): fhq_runtime.run_registry.writes_to for
-- RUN-STEP08-BASELINE-V5-CADENCE erklaerer {fhq_governance.baseline_controls_v5}
-- som skrivemaal. Registeret autoriserer skrive-intensjonen; denne GRANTen
-- ratifiserer privilegiet slik at jobben faktisk kan skrive det den er
-- registrert for aa skrive.
--
-- STIGs innstilling: INSERT + UPDATE, IKKE DELETE. En baseline-kontroll skal
-- kunne opprettes og oppdateres av jobben, aldri slettes.
--
-- Kjoeres av CEO/VEGA som supabase_admin ETTER eksplisitt G4-godkjenning:
--   psql -h 127.0.0.1 -p 54322 -U supabase_admin -d postgres -f g4_baseline_controls_grant.sql
-- Reverseres med:
--   REVOKE INSERT, UPDATE ON TABLE fhq_governance.baseline_controls_v5 FROM fhq_executive_task;
-- ============================================================================
BEGIN;
GRANT USAGE ON SCHEMA fhq_governance TO fhq_executive_task;
GRANT SELECT, INSERT, UPDATE ON TABLE fhq_governance.baseline_controls_v5 TO fhq_executive_task;
-- Sekvens for baseline_controls_v5 dersom den har en serie-noekkel (ufarlig hvis fravaerende):
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.sequences
             WHERE sequence_schema='fhq_governance' AND sequence_name='baseline_controls_v5_id_seq') THEN
    EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE fhq_governance.baseline_controls_v5_id_seq TO fhq_executive_task';
  END IF;
END $$;
COMMIT;
-- Akseptansetest (vent to tikk): RUN-STEP08-BASELINE-V5-CADENCE skal slutte aa feile paa rettigheter.
--   SELECT status, COUNT(*) FROM fhq_runtime.run_attempts
--   WHERE run_id = 'RUN-STEP08-BASELINE-V5-CADENCE' AND started_at >= NOW() - INTERVAL '15 minutes'
--   GROUP BY 1;
