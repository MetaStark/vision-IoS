# FjordHQ Canonical Runtime Data Map

Dette dokumentet beskriver hvilke databaser og tabeller som faktisk brukes av runtime-motoren i FjordHQ.  
Formålet er å unngå forvirring mellom legacy-tabeller, research-tabeller og runtime-tabeller.

Denne filen oppdateres når runtime-arkitekturen endres.

---

# 1. PRICE INGEST LAYER

## Live market prices
Source: Binance WebSocket

Table
fhq_core.market_prices_live

Writer
market_streamer_v2.py

Purpose
Real-time price ingest for execution og runtime monitoring.

---

## Daily bar ingest
Source: yfinance

Table
fhq_market.prices

Writer
ios001_daily_ingest.py

Purpose
Daglige OHLCV bars brukt for:

- regime classification
- feature generation
- backtesting

---

# 2. FEATURE ENGINE

## Technical indicators

Tables
fhq_research.indicator_momentum  
fhq_research.indicator_trend  
fhq_research.indicator_volatility  
fhq_research.indicator_volume  
fhq_research.indicator_ichimoku  

Writer
calc_indicators_v1.py  
indicator_calculation_daemon

Input
fhq_market.prices

Purpose
Genererer tekniske features for forskning og signalgenerering.

---

# 3. REGIME ENGINE

## Daily regime classification

Table
fhq_perception.regime_daily

Writer
ios003_daily_regime_update_v4.py

Input
fhq_market.prices

Purpose
Klassifiserer markedsregime (Bull / Bear / Neutral).

---

## Sovereign regime state

Table
fhq_perception.sovereign_regime_state_v4

Writer
ios003_daily_regime_update_v4.py

Purpose
Makro-basert regime state brukt av CRIO-motoren.

---

## Micro regime classification

Table
fhq_learning.micro_regime_classifications

Writer
micro_regime_classifier.py

Purpose
Finere regimeanalyse for intradag-signalering.

---

# 4. EXECUTION ENGINE

## Shadow trades

Table
fhq_execution.shadow_trades

Purpose
Simulerte handler brukt til:

- signal testing
- performance tracking
- learning loop

Execution mode
PAPER_PROD

---

# 5. OUTCOME ENGINE

Outcome tracking skjer via:

Tables
fhq_execution.shadow_trades  
fhq_learning.outcomes

Purpose
Måle resultat av signaler og handler.

---

# 6. LEARNING ENGINE

Learning loop oppdaterer:

Tables
fhq_learning.hypothesis_canon  
fhq_learning.calibration  
fhq_alpha.alpha_signals

Purpose
Oppdatere modellkonfidens og signalstyrke.

---

# 7. NOTES

Dette dokumentet representerer **runtime truth**.

Tabeller utenfor denne listen kan være:

- research
- legacy
- staging
- eksperimentelle

De skal ikke brukes av runtime uten eksplisitt beslutning.
