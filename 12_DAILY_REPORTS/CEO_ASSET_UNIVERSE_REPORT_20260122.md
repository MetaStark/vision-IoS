# FjordHQ Asset Universe Report

**Dato:** 2026-01-22
**Klassifisering:** CEO EXECUTIVE BRIEFING
**Generert av:** STIG (EC-003)
**Kilde:** PostgreSQL 17.6 @ 127.0.0.1:54322
**Hierarki-referanse:** IoS-001_2026_PRODUCTION (Canonical Asset & Context Registry)

---

## Executive Summary

| Metric | Verdi |
|--------|-------|
| **Totalt antall assets** | 517 |
| **Aktive assets** | 493 |
| **Assets med prisdata** | 499 |
| **Totalt prisrecords** | 1,226,501 |
| **Regioner dekket** | 4 (Global, North America, Europe, Nordic) |
| **Børser** | 9 |
| **Asset-klasser** | 4 (Crypto, FX, Equity, ETF) |

---

## 1. IoS-001 Hierarki Oversikt

```
IoS-001 Canonical Asset Registry
├── GLOBAL
│   ├── XCRY (Cryptocurrency) ── 46 aktive
│   └── XFOR (Foreign Exchange) ── 24 aktive
├── NORTH AMERICA
│   ├── XNYS (New York Stock Exchange) ── 171 aktive
│   ├── XNAS (NASDAQ) ── 89 aktive
│   └── ARCX (NYSE Arca ETFs) ── 18 aktive
└── EUROPE
    ├── XOSL (Oslo Børs) ── 38 aktive
    ├── XETR (Deutsche Börse XETRA) ── 39 aktive
    ├── XPAR (Euronext Paris) ── 37 aktive
    └── XLON (London Stock Exchange) ── 31 aktive
```

---

## 2. Asset-fordeling per Region og Børs

### 2.1 Sammendrag per Børs

| Børs (MIC) | Region | Land | Asset Class | Totalt | Aktive | Valuta |
|------------|--------|------|-------------|--------|--------|--------|
| **XCRY** | GLOBAL | - | CRYPTO | 50 | 46 | USD |
| **XFOR** | GLOBAL | - | FX | 25 | 24 | Multi |
| **XNYS** | North America | US | EQUITY | 173 | 171 | USD |
| **XNAS** | North America | US | EQUITY | 92 | 89 | USD |
| **ARCX** | North America | US | ETF/EQUITY | 18 | 18 | USD |
| **XOSL** | Europe | NO | EQUITY | 51 | 38 | NOK |
| **XETR** | Europe | DE | EQUITY | 39 | 39 | EUR |
| **XPAR** | Europe | FR | EQUITY | 38 | 37 | EUR |
| **XLON** | Europe | GB | EQUITY | 31 | 31 | GBP |

### 2.2 Regional Fordeling

```
┌─────────────────────────────────────────────────────────────┐
│ NORTH AMERICA (US)                          278 assets (56%)│
│ ████████████████████████████████████████████████            │
├─────────────────────────────────────────────────────────────┤
│ EUROPE                                      145 assets (29%)│
│ ██████████████████████████                                  │
├─────────────────────────────────────────────────────────────┤
│ GLOBAL (Crypto + FX)                         70 assets (14%)│
│ ████████████                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. CRYPTOCURRENCY (XCRY) - 46 Aktive

### 3.1 Sektor-fordeling

| Sektor | Antall | Eksempler |
|--------|--------|-----------|
| LAYER_1 | 15 | BTC, ETH, SOL, ADA, AVAX, BNB |
| DEFI | 9 | AAVE, UNI, MKR, LDO, INJ, CRV |
| PAYMENT | 4 | LTC, XRP, BCH, XLM |
| METAVERSE | 2 | MANA, SAND |
| MEME | 2 | DOGE, SHIB |
| PRIVACY | 2 | XMR, ZEC |
| LAYER_0 | 2 | ATOM, DOT |
| EXCHANGE | 2 | CRO, OKB |
| ENTERPRISE | 2 | QNT, VET |
| ORACLE | 1 | LINK |
| GAMING | 1 | AXS |
| STORAGE | 1 | FIL |
| INFRASTRUCTURE | 1 | GRT |
| MEDIA | 1 | THETA |
| SPORTS | 1 | CHZ |

### 3.2 Liquidity Tier Fordeling

| Tier | Antall | Assets |
|------|--------|--------|
| **TIER_1** | 10 | BTC, ETH, SOL, ADA, BNB, AVAX, XRP, DOGE, LINK, LTC |
| **TIER_2** | 17 | ATOM, DOT, UNI, MKR, AAVE, SHIB, TRX, NEAR, etc. |
| **TIER_3** | 19 | ALGO, AXS, CHZ, CRO, EOS, FLOW, MANA, SAND, etc. |

### 3.3 Komplett Crypto Liste

| Ticker | Sektor | Liquidity |
|--------|--------|-----------|
| BTC-USD | LAYER_1 | TIER_1 |
| ETH-USD | LAYER_1 | TIER_1 |
| SOL-USD | LAYER_1 | TIER_1 |
| ADA-USD | LAYER_1 | TIER_1 |
| BNB-USD | LAYER_1 | TIER_1 |
| AVAX-USD | LAYER_1 | TIER_1 |
| XRP-USD | PAYMENT | TIER_1 |
| DOGE-USD | MEME | TIER_1 |
| LINK-USD | ORACLE | TIER_1 |
| LTC-USD | PAYMENT | TIER_1 |
| ATOM-USD | LAYER_0 | TIER_2 |
| DOT-USD | LAYER_0 | TIER_2 |
| UNI-USD | DEFI | TIER_2 |
| MKR-USD | DEFI | TIER_2 |
| AAVE-USD | DEFI | TIER_2 |
| SHIB-USD | MEME | TIER_2 |
| TRX-USD | LAYER_1 | TIER_2 |
| NEAR-USD | LAYER_1 | TIER_2 |
| BCH-USD | PAYMENT | TIER_2 |
| ETC-USD | LAYER_1 | TIER_2 |
| FIL-USD | STORAGE | TIER_2 |
| HBAR-USD | LAYER_1 | TIER_2 |
| ICP-USD | LAYER_1 | TIER_2 |
| INJ-USD | DEFI | TIER_2 |
| LDO-USD | DEFI | TIER_2 |
| XLM-USD | PAYMENT | TIER_2 |
| XMR-USD | PRIVACY | TIER_2 |
| ALGO-USD | LAYER_1 | TIER_3 |
| AXS-USD | GAMING | TIER_3 |
| CHZ-USD | SPORTS | TIER_3 |
| CRO-USD | EXCHANGE | TIER_3 |
| CRV-USD | DEFI | TIER_3 |
| EOS-USD | LAYER_1 | TIER_3 |
| FLOW-USD | LAYER_1 | TIER_3 |
| GRT-USD | INFRASTRUCTURE | TIER_3 |
| MANA-USD | METAVERSE | TIER_3 |
| OKB-USD | EXCHANGE | TIER_3 |
| QNT-USD | ENTERPRISE | TIER_3 |
| RPL-USD | DEFI | TIER_3 |
| RUNE-USD | DEFI | TIER_3 |
| SAND-USD | METAVERSE | TIER_3 |
| SNX-USD | DEFI | TIER_3 |
| THETA-USD | MEDIA | TIER_3 |
| VET-USD | ENTERPRISE | TIER_3 |
| XTZ-USD | LAYER_1 | TIER_3 |
| ZEC-USD | PRIVACY | TIER_3 |

---

## 4. FOREIGN EXCHANGE (XFOR) - 24 Aktive

### 4.1 Sektor-fordeling

| Sektor | Antall | Par |
|--------|--------|-----|
| G10_MAJOR | 7 | EURUSD, USDJPY, GBPUSD, USDCHF, AUDUSD, USDCAD, NZDUSD |
| G10_CROSS | 8 | EURGBP, EURJPY, GBPJPY, EURAUD, EURCHF, AUDJPY, CADJPY, CHFJPY |
| NORDIC | 4 | EURNOK, USDNOK, EURSEK, USDSEK |
| EMERGING | 3 | USDMXN, USDZAR, USDTRY |
| ASIA | 2 | USDHKD, USDSGD |

### 4.2 Komplett FX Liste

| Par | Sektor | Quote Currency | Liquidity |
|-----|--------|----------------|-----------|
| EURUSD=X | G10_MAJOR | USD | TIER_1 |
| USDJPY=X | G10_MAJOR | JPY | TIER_1 |
| GBPUSD=X | G10_MAJOR | USD | TIER_1 |
| USDCHF=X | G10_MAJOR | CHF | TIER_1 |
| AUDUSD=X | G10_MAJOR | USD | TIER_1 |
| USDCAD=X | G10_MAJOR | CAD | TIER_1 |
| NZDUSD=X | G10_MAJOR | USD | TIER_1 |
| EURGBP=X | G10_CROSS | GBP | TIER_1 |
| EURJPY=X | G10_CROSS | JPY | TIER_1 |
| GBPJPY=X | G10_CROSS | JPY | TIER_1 |
| EURAUD=X | G10_CROSS | AUD | TIER_2 |
| EURCHF=X | G10_CROSS | CHF | TIER_2 |
| AUDJPY=X | G10_CROSS | JPY | TIER_2 |
| CADJPY=X | G10_CROSS | JPY | TIER_2 |
| CHFJPY=X | G10_CROSS | JPY | TIER_2 |
| EURNOK=X | NORDIC | NOK | TIER_2 |
| USDNOK=X | NORDIC | NOK | TIER_2 |
| EURSEK=X | NORDIC | SEK | TIER_2 |
| USDSEK=X | NORDIC | SEK | TIER_2 |
| USDMXN=X | EMERGING | MXN | TIER_2 |
| USDZAR=X | EMERGING | ZAR | TIER_2 |
| USDHKD=X | ASIA | HKD | TIER_2 |
| USDSGD=X | ASIA | SGD | TIER_2 |
| USDTRY=X | EMERGING | TRY | TIER_3 |

---

## 5. US EQUITIES (XNYS, XNAS, ARCX) - 278 Aktive

### 5.1 Børs-fordeling

| Børs | Type | Antall | Beskrivelse |
|------|------|--------|-------------|
| XNYS | Equity | 171 | New York Stock Exchange - Blue chips |
| XNAS | Equity | 89 | NASDAQ - Tech-fokusert |
| ARCX | ETF | 18 | NYSE Arca - Index & Sector ETFs |

### 5.2 Sektor-fordeling (US Total)

| Sektor | Antall |
|--------|--------|
| TECHNOLOGY | 52 |
| FINANCIALS | 53 |
| HEALTHCARE | 37 |
| INDUSTRIALS | 56 |
| CONSUMER_DISC | 31 |
| COMMUNICATION | 25 |
| ENERGY | 27 |
| MATERIALS | 28 |
| UTILITIES | 22 |
| REAL_ESTATE | 17 |
| INDEX_ETF | 6 |
| SECTOR_ETF | 11 |

### 5.3 Index ETFs (Benchmark Tracking)

| Ticker | Navn | Indeks |
|--------|------|--------|
| SPY | SPDR S&P 500 | S&P 500 |
| VOO | Vanguard S&P 500 | S&P 500 |
| VTI | Vanguard Total Market | US Total Market |
| IWM | iShares Russell 2000 | Russell 2000 |
| DIA | SPDR Dow Jones | DJIA |

### 5.4 Sector ETFs (SPDR Select Sector)

| Ticker | Sektor |
|--------|--------|
| XLK | Technology |
| XLF | Financials |
| XLV | Healthcare |
| XLI | Industrials |
| XLE | Energy |
| XLY | Consumer Discretionary |
| XLP | Consumer Staples |
| XLB | Materials |
| XLU | Utilities |
| XLRE | Real Estate |
| XLC | Communications |

### 5.5 Notable US Equities (Sample - TIER_1)

| Ticker | Sektor | Børs |
|--------|--------|------|
| AAPL | TECHNOLOGY | XNAS |
| MSFT | TECHNOLOGY | XNAS |
| AMZN | CONSUMER_DISC | XNAS |
| GOOGL | COMMUNICATION | XNAS |
| META | COMMUNICATION | XNAS |
| TSLA | CONSUMER_DISC | XNAS |
| NVDA | TECHNOLOGY | XNAS |
| JPM | FINANCIALS | XNYS |
| V | FINANCIALS | XNYS |
| JNJ | HEALTHCARE | XNYS |
| UNH | HEALTHCARE | XNYS |
| XOM | ENERGY | XNYS |
| CVX | ENERGY | XNYS |

---

## 6. OSLO BØRS (XOSL) - 38 Aktive

### 6.1 Sektor-fordeling

| Sektor | Antall | Nøkkelselskaper |
|--------|--------|-----------------|
| ENERGY | 7 | EQNR, AKRBP, VAR, TGS, SUBC, BWO, AKSO |
| CONSUMER_STAPLES | 6 | MOWI, SALM, ORK, LSG, BAKKA, AUSS |
| INDUSTRIALS | 10 | AKER, FRO, HAFNI, KOG, STRO, TOM |
| FINANCIALS | 4 | DNB, GJF, STB, MORG |
| MATERIALS | 2 | NHY, YAR |
| UTILITIES | 3 | NEL, SCATC, ELMRA |
| REAL_ESTATE | 2 | ENTRA, OLT |
| TECHNOLOGY | 1 | AUTO |
| COMMUNICATION | 1 | TEL |
| CONSUMER_DISC | 1 | KID |
| HEALTHCARE | 1 | PHO |

### 6.2 Komplett Oslo Børs Liste

| Ticker | Sektor | Liquidity |
|--------|--------|-----------|
| EQNR.OL | ENERGY | TIER_1 |
| DNB.OL | FINANCIALS | TIER_1 |
| MOWI.OL | CONSUMER_STAPLES | TIER_1 |
| NHY.OL | MATERIALS | TIER_1 |
| YAR.OL | MATERIALS | TIER_1 |
| SALM.OL | CONSUMER_STAPLES | TIER_1 |
| ORK.OL | CONSUMER_STAPLES | TIER_1 |
| TEL.OL | COMMUNICATION | TIER_1 |
| AKRBP.OL | ENERGY | TIER_1 |
| AKSO.OL | ENERGY | TIER_2 |
| BWO.OL | ENERGY | TIER_2 |
| VAR.OL | ENERGY | TIER_2 |
| TGS.OL | ENERGY | TIER_2 |
| SUBC.OL | ENERGY | TIER_2 |
| LSG.OL | CONSUMER_STAPLES | TIER_2 |
| BAKKA.OL | CONSUMER_STAPLES | TIER_2 |
| AUSS.OL | CONSUMER_STAPLES | TIER_2 |
| GJF.OL | FINANCIALS | TIER_2 |
| STB.OL | FINANCIALS | TIER_2 |
| AKER.OL | INDUSTRIALS | TIER_2 |
| FRO.OL | INDUSTRIALS | TIER_2 |
| HAFNI.OL | INDUSTRIALS | TIER_2 |
| KOG.OL | INDUSTRIALS | TIER_2 |
| STRO.OL | INDUSTRIALS | TIER_2 |
| TOM.OL | INDUSTRIALS | TIER_2 |
| NEL.OL | UTILITIES | TIER_2 |
| SCATC.OL | UTILITIES | TIER_2 |
| ENTRA.OL | REAL_ESTATE | TIER_2 |
| AUTO.OL | TECHNOLOGY | TIER_2 |
| KID.OL | CONSUMER_DISC | TIER_3 |
| MORG.OL | FINANCIALS | TIER_3 |
| PHO.OL | HEALTHCARE | TIER_3 |
| AKVA.OL | INDUSTRIALS | TIER_3 |
| BEWI.OL | INDUSTRIALS | TIER_3 |
| NOD.OL | INDUSTRIALS | TIER_3 |
| WAWI.OL | INDUSTRIALS | TIER_3 |
| OLT.OL | REAL_ESTATE | TIER_3 |
| ELMRA.OL | UTILITIES | TIER_3 |

---

## 7. EUROPEAN EQUITIES

### 7.1 Deutsche Börse XETRA (XETR) - 39 Aktive

| Sektor | Antall | Nøkkelselskaper |
|--------|--------|-----------------|
| TECHNOLOGY | 4 | SAP, IFX, AIXA |
| INDUSTRIALS | 8 | SIE, AIR, DHL |
| FINANCIALS | 5 | ALV, DBK, MUV2 |
| CONSUMER_CYCLICAL | 6 | BMW, VOW3, MBG, ADS |
| HEALTHCARE | 4 | FRE, MRK, BAY |
| MATERIALS | 3 | BAS, HEN3, LIN |
| UTILITIES | 3 | RWE, EON |
| ENERGY | 2 | ENR |
| COMMUNICATION | 2 | DTE |
| REAL_ESTATE | 1 | VNA |
| CONSUMER_DEFENSIVE | 1 | BEI |

### 7.2 Euronext Paris (XPAR) - 37 Aktive

| Sektor | Antall | Nøkkelselskaper |
|--------|--------|-----------------|
| CONSUMER_CYCLICAL | 8 | MC, KER, RMS, OR |
| INDUSTRIALS | 6 | AIR, SAF, VIE, SGO |
| FINANCIALS | 5 | BNP, ACA, GLE, CS |
| HEALTHCARE | 3 | SAN |
| ENERGY | 3 | TTE, EN |
| TECHNOLOGY | 3 | CAP, DSY, ATO |
| UTILITIES | 3 | ENGI, EL |
| MATERIALS | 2 | AI, ML |
| COMMUNICATION | 2 | VIV, ORA, PUB |
| CONSUMER_DEFENSIVE | 2 | RI, BN, DG |

### 7.3 London Stock Exchange (XLON) - 31 Aktive

| Sektor | Antall | Nøkkelselskaper |
|--------|--------|-----------------|
| FINANCIALS | 7 | HSBA, BARC, LLOY, STAN |
| ENERGY | 5 | BP, SHEL |
| HEALTHCARE | 4 | AZN, GSK |
| INDUSTRIALS | 5 | RR, BA |
| MATERIALS | 4 | RIO, AAL, GLEN |
| CONSUMER_DEFENSIVE | 3 | ULVR, DGE |
| UTILITIES | 2 | NG, SSE |
| COMMUNICATION | 1 | VOD |

---

## 8. PRISDATA: Tabeller, Frekvens og Vendors

### 8.1 Pris-tabeller i Systemet

| Tabell | Schema | Formål | Frekvens |
|--------|--------|--------|----------|
| `prices` | fhq_market | **Primær kanonisk pris** | DAGLIG |
| `staging_prices` | fhq_market | Staging før validering | Kontinuerlig |
| `price_series` | fhq_data | Historisk arkiv | DAGLIG |
| `price_staging` | fhq_data | Raw import | Kontinuerlig |
| `intraday_bars_h1` | fhq_operational | 1-times bars | INTRADAG (H1) |
| `intraday_bars_h4` | fhq_operational | 4-times bars | INTRADAG (H4) |
| `market_prices_raw` | fhq_core | Rå vendor data | Kontinuerlig |
| `market_prices_clean` | fhq_core | Renset data | DAGLIG |
| `market_prices_live` | fhq_core | Real-time feed | LIVE |
| `backtest_price_cache` | fhq_research | Backtest-optimalisert | Batch |

### 8.2 Prisfrekvens per Asset Class

| Asset Class | Primær Frekvens | Intradag | Kilde |
|-------------|-----------------|----------|-------|
| **CRYPTO** | DAGLIG (24/7) | H1 (498 records) | CoinGecko, yfinance |
| **FX** | DAGLIG (24/5) | Planlagt | ECB, TwelveData |
| **US EQUITY** | DAGLIG | Planlagt | Alpaca, Yahoo |
| **EU EQUITY** | DAGLIG | Planlagt | Yahoo, TwelveData |
| **OSLO BØRS** | DAGLIG | Planlagt | Yahoo |

### 8.3 Intraday Data Status

| Intervall | Records | Assets | Periode | Status |
|-----------|---------|--------|---------|--------|
| **H1** | 498 | 3 | 2026-01-10 til 2026-01-17 | AKTIV |
| **H4** | 0 | 0 | - | IKKE POPULERT |

**Note:** Intradag-data er begrenset til 3 assets for testing (BTC, ETH, SOL).

---

## 9. VENDORS & DATAKILDER

### 9.1 Vendor Fordeling (etter prisrecords)

| Vendor | Records | Assets | Andel |
|--------|---------|--------|-------|
| **yfinance_colab** | 1,126,086 | 464 | 91.8% |
| **MIGRATION_FROM_PRICE_SERIES** | 67,248 | 27 | 5.5% |
| **yfinance** | 14,594 | 489 | 1.2% |
| **YAHOO** | 8,189 | 473 | 0.7% |
| **yahoo_chart_v8_raw** | 6,379 | 5 | 0.5% |
| **ALPACA** | 2,003 | 10 | 0.2% |
| **TWELVEDATA** | 1,427 | 247 | 0.1% |
| **COINGECKO_REPAIR** | 232 | 19 | <0.1% |
| **ECB** | 91 | 7 | <0.1% |
| **TWELVEDATA_FX** | 87 | 24 | <0.1% |
| **binance** | 30 | 3 | <0.1% |
| **alphavantage** | 13 | 4 | <0.1% |

### 9.2 Vendor Policy per Asset Class

| Asset Class | Primær Vendor | Fallback | Verifikasjonsmetode |
|-------------|---------------|----------|---------------------|
| **CRYPTO** | FJORDHQ_WELCOME_CENTER | FJORDHQ_WELCOME_CENTER | Synkronisering for å unngå indikator-mismatch |
| **FX** | FJORDHQ_WELCOME_CENTER | FJORDHQ_WELCOME_CENTER | Single canonical feed for å unngå cross-rate drift |
| **COMMODITY** | FJORDHQ_WELCOME_CENTER | FJORDHQ_WELCOME_CENTER | Hash-verifisering mot raw vendor export |

### 9.3 Vendor Dekning per Region

| Region | Primær | Sekundær | Tertiary |
|--------|--------|----------|----------|
| US Equities | Yahoo Finance | Alpaca IEX | TwelveData |
| Oslo Børs | Yahoo Finance | - | - |
| EU Equities | Yahoo Finance | TwelveData | - |
| Crypto | CoinGecko | Binance | Yahoo Crypto |
| FX | ECB | TwelveData | Yahoo FX |

---

## 10. DATA KVALITET OG HISTORIKK

### 10.1 Prishistorikk Dekning

| Asset Class | Tidligste Data | Seneste Data | Gjennomsnittlig Rekker |
|-------------|----------------|--------------|------------------------|
| CRYPTO | 2015-12-01 | 2026-01-22 | ~2,900 |
| FX | 2015-12-10 | 2025-12-10 | ~2,605 |
| EU EQUITY | 2015-12-10 | 2025-12-10 | ~2,560 |
| US EQUITY | Varierende | 2026-01-22 | ~2,500 |
| OSLO BØRS | 2015-12-10 | 2025-12-10 | ~2,500 |

### 10.2 Iron Curtain Thresholds (IoS-001 §4.1)

| Asset Class | Quarantine | Full History |
|-------------|------------|--------------|
| Equities | 252 rows (1 år) | 1,260 rows (5 år) |
| FX | 252 rows (1 år) | 1,260 rows (5 år) |
| Crypto | 365 rows (1 år) | 1,825 rows (5 år) |

### 10.3 Liquidity Tier Fordeling

| Tier | Crypto | FX | US Equity | Oslo | EU |
|------|--------|----|-----------| ---- | -- |
| **TIER_1** | 10 | 10 | ~80 | 9 | ~30 |
| **TIER_2** | 17 | 13 | ~100 | 18 | ~50 |
| **TIER_3** | 19 | 1 | ~98 | 11 | ~65 |

---

## 11. OPPSUMMERING

### 11.1 Nøkkeltall

| Dimensjon | Verdi |
|-----------|-------|
| **Total Aktive Assets** | 493 |
| **Geografisk Dekning** | Global, North America, Europe |
| **Børser** | 9 (XCRY, XFOR, XNYS, XNAS, ARCX, XOSL, XETR, XPAR, XLON) |
| **Asset Classes** | 4 (Crypto, FX, Equity, ETF) |
| **Sektorer** | 50+ unike |
| **Prisrecords** | 1,226,501 |
| **Historikk** | 10+ år for de fleste assets |
| **Primær Vendor** | Yahoo Finance (91.8%) |
| **Intradag Dekning** | Begrenset (3 assets, H1) |

### 11.2 Neste Steg (Anbefalinger)

1. **Utvid intradag-dekning** til flere US Equities og Oslo Børs
2. **Konsolider vendor-mangfold** - for mye avhengighet av Yahoo Finance
3. **Populer H4 bars** for regime-analyse
4. **Legg til commodity ETFs** (GLD, SLV, USO, UNG) for makro-analyse

---

*Generert av STIG (EC-003) | 2026-01-22*
*Database: PostgreSQL 17.6 @ 127.0.0.1:54322*
*Hierarki-referanse: IoS-001_2026_PRODUCTION v2026.PROD.3*
