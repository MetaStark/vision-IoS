# IoS-013 Signal Overview – Data Mapping

**CEO-DIR-2026-024** | Dashboard Extension

---

## Datakilde

**Primær tabell:**
```
fhq_signal_context.weighted_signal_plan
```

---

## Kolonne-mapping

| Dashboard-kolonne | DB-felt | Type | Beskrivelse |
|-------------------|---------|------|-------------|
| **Asset** | `asset_id` | text | Ticker/canonical ID |
| **Calibration Status** | `calibration_status` | enum | CALIBRATED / NOT_CALIBRATED |
| **Signal** | `direction` | enum | LONG / SHORT / UNDEFINED |
| **Confidence** | `confidence_score` | numeric | 0.000 – 0.700 |
| **Regime** | `regime_context` | text | RISK_ON / RISK_OFF / NEUTRAL |
| **Forklaring** | `explainability_trace` | text | Parsed til CEO-lesbart format |

---

## System Status Beregning

```sql
SELECT
  COUNT(DISTINCT asset_id) as total_assets,
  COUNT(DISTINCT CASE WHEN calibration_status = 'CALIBRATED' THEN asset_id END) as calibrated_assets,
  MAX(created_at) as last_updated
FROM fhq_signal_context.weighted_signal_plan
WHERE computation_date = (SELECT MAX(computation_date) FROM fhq_signal_context.weighted_signal_plan)
```

**Status-logikk:**
- `ACTIVE`: Sist oppdatert < 24 timer
- `STALE`: Sist oppdatert 24-72 timer
- `DEGRADED`: Sist oppdatert > 72 timer

---

## Forklaringstekst Mapping

`explainability_trace` format:
```
base=0.250|regime=NEUTRAL*0.45|skill=0.42|causal=0.50|macro=+0.00|event=0.00|mult=0.094|weighted=0.024
```

**Parsing til CEO-lesbart:**

| Felt | Transformasjon |
|------|----------------|
| `regime=X` | "Regime X" |
| `skill=0.42` | < 0.3: "lav", 0.3-0.5: "moderat", > 0.5: "høy" |
| `causal=0.50` | < 0.4: "svak", 0.4-0.6: "moderat", > 0.6: "sterk" |
| `macro=0.00` | abs < 0.05: "nøytral", > 0: "positiv", < 0: "negativ" |
| `event=0.00` | > 0: "Event proximity aktiv" |
| `base=0.00` | = 0: "Baseline null - ingen signal aktivert" |

**Eksempel output:**
```
Regime NEUTRAL · Forecast skill moderat · Kausal validering moderat · Macro nøytral
```

---

## API Endpoint

```
GET /api/ios013/signals
```

**Response struktur:**
```json
{
  "system_status": {
    "status": "ACTIVE",
    "total_assets": 23,
    "calibrated_assets": 22,
    "last_updated": "2026-01-22T23:28:13.378Z"
  },
  "signals": [
    {
      "asset_id": "BTC-USD",
      "calibration_status": "NOT_CALIBRATED",
      "direction": "UNDEFINED",
      "confidence_score": 0.097,
      "regime_context": "NEUTRAL",
      "explainability_trace": "..."
    }
  ]
}
```

---

## Interaktivitet (kun to)

1. **Sortér på Confidence** (desc/asc toggle)
2. **Filtrer på Calibration Status = CALIBRATED**

---

## Filer

| Fil | Formål |
|-----|--------|
| `/app/ios-signals/page.tsx` | Dashboard page |
| `/app/api/ios013/signals/route.ts` | API endpoint |
| `/components/Navigation.tsx` | Meny-item lagt til |

---

**Godkjent:** CEO-DIR-2026-024
**Implementert:** 2026-01-23
**Agent:** STIG (EC-003)
