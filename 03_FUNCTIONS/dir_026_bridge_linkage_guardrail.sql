-- CEO-DIR-2026-BRIDGE-LINKAGE-GUARDRAIL-026
-- Guardrail for outcome_pack_link to enforce BRIDGE-only linkage
-- Author: STIG (EC-003)
-- Date: 2026-02-16

-- Create trigger function to enforce BRIDGE-only linkage
CREATE OR REPLACE FUNCTION fhq_learning.trg_enforce_bridge_only_linkage()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if the outcome belongs to a BRIDGE experiment
    IF NOT EXISTS (
        SELECT 1 FROM fhq_learning.experiment_registry er
        JOIN fhq_learning.outcome_ledger ol ON er.experiment_id = ol.experiment_id
        WHERE ol.outcome_id = NEW.outcome_id
          AND er.parameters->>'experiment_class' = 'BRIDGE_THROUGHPUT'
    ) THEN
        RAISE EXCEPTION 'outcome_pack_link only allowed for BRIDGE experiments. Outcome % belongs to non-BRIDGE experiment.', NEW.outcome_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on outcome_pack_link
DROP TRIGGER IF EXISTS trg_bridge_only_linkage ON fhq_learning.outcome_pack_link;
CREATE TRIGGER trg_bridge_only_linkage
    BEFORE INSERT ON fhq_learning.outcome_pack_link
    FOR EACH ROW
    EXECUTE FUNCTION fhq_learning.trg_enforce_bridge_only_linkage();

COMMENT ON FUNCTION fhq_learning.trg_enforce_bridge_only_linkage() IS 'Enforces BRIDGE-only constraint on outcome_pack_link (CEO-DIR-2026-BRIDGE-LINKAGE-GUARDRAIL-026)';
