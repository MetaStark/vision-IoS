# Alpaca Options & Inverse Instruments - Complete Reference

**Directive:** CEO-DIR-2026-VERBAL (Asset Verification)
**Author:** STIG (EC-003)
**Date:** 2026-01-23
**Classification:** OPERATIONAL / TRADING-READY

---

## Executive Summary

| Kategori | Status | Antall |
|----------|--------|--------|
| Options Level | **3 (SPREADS_ENABLED)** | - |
| Options Buying Power | **$104,801.51** | - |
| Symboler med PUT opsjoner | **27/27** | 100% |
| Inverse ETFs tilgjengelig | **41+** | Via Alpaca |

---

## 1. Alpaca Options - Verifisert Status

### 1.1 Konto-status

```
Account ID:          1efc48bb-0ba6-434c-8971-5e31a59dd7ec
Options Level:       3 (SPREADS_ENABLED)
Options Buying Power: $104,801.51
Verification Date:   2026-01-23T20:39:13Z
```

**Options Levels Forklart:**
| Level | Navn | Tillatte Strategier |
|-------|------|---------------------|
| 0 | NO_OPTIONS | Ingen opsjonshandel |
| 1 | COVERED_ONLY | Covered calls, cash-secured puts |
| 2 | LONG_OPTIONS | Long calls, long puts |
| **3** | **SPREADS_ENABLED** | **Spreads, straddles, strangles** |
| 4 | NAKED_CALLS | Naked calls (krever margin) |

### 1.2 FjordHQ Universe - PUT Options Tilgjengelighet

**ALLE 27 symboler har PUT opsjoner tilgjengelig:**

| Symbol | Sektor | PUT Kontrakter | Strike Range | Expirations |
|--------|--------|----------------|--------------|-------------|
| **AAPL** | Tech | 100 | $110 - $400 | 2 |
| **MSFT** | Tech | 100 | $270 - $655 | 2 |
| **GOOGL** | Tech | 100 | $100 - $450 | 2 |
| **AMZN** | Tech | 100 | $125 - $345 | 2 |
| **META** | Tech | 100 | $100 - $662.50 | 1 |
| **NVDA** | Tech | 100 | $50 - $360 | 2 |
| **TSLA** | Tech | 100 | $80 - $517.50 | 1 |
| **JPM** | Finance | 100 | $160 - $400 | 2 |
| **V** | Finance | 100 | $190 - $445 | 2 |
| **JNJ** | Healthcare | 100 | $105 - $315 | 2 |
| **UNH** | Healthcare | 100 | $190 - $495 | 2 |
| **PG** | Consumer | 100 | $75 - $220 | 2 |
| **XOM** | Energy | 100 | $65 - $150 | 2 |
| **HD** | Retail | 100 | $220 - $500 | 2 |
| **SPY** | Index ETF | 100 | $500 - $679 | 1 |
| **QQQ** | Index ETF | 100 | $450 - $670 | 1 |
| **IWM** | Index ETF | 100 | $140 - $300 | 2 |
| **GLD** | Commodity | 100 | $250 - $432 | 1 |
| **TLT** | Bond | 100 | $70 - $110 | 3 |
| **XLF** | Sector ETF | 100 | $30 - $65 | 3 |
| **XLE** | Sector ETF | 100 | $25 - $55 | 3 |
| **VXX** | Volatility | 100 | $21 - $61 | 2 |
| **UVXY** | Volatility | 100 | $1 - $48 | 2 |
| **AMD** | Tech | 100 | $40 - $420 | 2 |
| **COIN** | Crypto | 100 | $150 - $490 | 1 |
| **PLTR** | Tech | 100 | $90 - $330 | 2 |
| **SOFI** | Fintech | 100 | $15 - $40 | 3 |

---

## 2. Instrumenter for Profitt ved Nedgang

### 2.1 Metode 1: PUT Opsjoner (Anbefalt for FjordHQ)

**Fordeler:**
- Definert maksimal risiko (premium betalt)
- Ingen margin krav for long puts
- Leverage uten ubegrenset tap
- Tilgjengelig for alle 27 symboler i universet

**Strategier med Level 3:**

| Strategi | Retning | Max Tap | Max Gevinst |
|----------|---------|---------|-------------|
| Long PUT | Bearish | Premium | Strike - Premium |
| Bear PUT Spread | Bearish | Net debit | Strike diff - Net debit |
| PUT Ratio Spread | Bearish | Variable | Amplified |

### 2.2 Metode 2: Short Selling (Tilgjengelig, men Begrenset)

**Alpaca Regler:**
- Kun ETB (Easy-to-Borrow) aksjer kan shortes
- $0 borrow fee for ETB aksjer
- HTB (Hard-to-Borrow) posisjon kan tvinges lukket
- Ubegrenset tapsrisiko

**Ikke anbefalt** for systematisk trading pga. HTB-risiko.

### 2.3 Metode 3: Inverse ETFs (Ingen Margin, Ingen Short)

**Fordeler:**
- Handles som vanlige aksjer (LONG posisjon)
- Ingen margin krav
- Ingen borrow fees
- Kan brukes i IRA/pensjonskontoer
- Definert maksimal tap (100% av investert beløp)

**Ulemper:**
- Daglig reset (compounding decay over tid)
- Høyere expense ratio (0.89-0.95%)
- Ikke egnet for langsiktig holding

---

## 3. Inverse ETFs - Komplett Liste

### 3.1 US Equity Index - Inverse

| Ticker | Navn | Leverage | Underliggende | Expense |
|--------|------|----------|---------------|---------|
| **SH** | ProShares Short S&P 500 | -1x | S&P 500 | 0.88% |
| **SDS** | ProShares UltraShort S&P 500 | -2x | S&P 500 | 0.89% |
| **SPXU** | ProShares UltraPro Short S&P 500 | -3x | S&P 500 | 0.90% |
| **SPXS** | Direxion Daily S&P 500 Bear 3X | -3x | S&P 500 | 1.01% |
| **PSQ** | ProShares Short QQQ | -1x | NASDAQ-100 | 0.95% |
| **QID** | ProShares UltraShort QQQ | -2x | NASDAQ-100 | 0.95% |
| **SQQQ** | ProShares UltraPro Short QQQ | -3x | NASDAQ-100 | 0.95% |
| **RWM** | ProShares Short Russell 2000 | -1x | Russell 2000 | 0.95% |
| **TWM** | ProShares UltraShort Russell 2000 | -2x | Russell 2000 | 0.95% |
| **SRTY** | ProShares UltraPro Short Russell 2000 | -3x | Russell 2000 | 0.95% |
| **DOG** | ProShares Short Dow 30 | -1x | DJIA | 0.95% |
| **DXD** | ProShares UltraShort Dow 30 | -2x | DJIA | 0.95% |
| **SDOW** | ProShares UltraPro Short Dow 30 | -3x | DJIA | 0.95% |

### 3.2 Sector-Specific Inverse

| Ticker | Navn | Leverage | Sektor |
|--------|------|----------|--------|
| **FAZ** | Direxion Daily Financial Bear 3X | -3x | Financials |
| **SKF** | ProShares UltraShort Financials | -2x | Financials |
| **ERY** | Direxion Daily Energy Bear 2X | -2x | Energy |
| **DRIP** | Direxion Daily S&P Oil & Gas Bear 2X | -2x | Oil & Gas E&P |
| **LABD** | Direxion Daily S&P Biotech Bear 3X | -3x | Biotech |
| **DUST** | Direxion Daily Gold Miners Bear 2X | -2x | Gold Miners |
| **JDST** | Direxion Daily Junior Gold Bear 2X | -2x | Junior Gold |
| **SOXS** | Direxion Daily Semiconductor Bear 3X | -3x | Semiconductors |
| **WEBS** | Direxion Daily Dow Jones Internet Bear 3X | -3x | Internet |
| **TECS** | Direxion Daily Technology Bear 3X | -3x | Technology |

### 3.3 Bond Inverse

| Ticker | Navn | Leverage | Duration |
|--------|------|----------|----------|
| **TBF** | ProShares Short 20+ Year Treasury | -1x | Long-term |
| **TBT** | ProShares UltraShort 20+ Year Treasury | -2x | Long-term |
| **TTT** | ProShares UltraPro Short 20+ Year Treasury | -3x | Long-term |
| **TMV** | Direxion Daily 20+ Yr Trsy Bear 3X | -3x | Long-term |
| **PST** | ProShares UltraShort 7-10 Year Treasury | -2x | Intermediate |
| **TYO** | Direxion Daily 7-10 Yr Treasury Bear 3X | -3x | Intermediate |
| **SJB** | ProShares Short High Yield | -1x | High Yield |

### 3.4 Commodity Inverse

| Ticker | Navn | Leverage | Commodity |
|--------|------|----------|-----------|
| **DGZ** | DB Gold Short ETN | -1x | Gold |
| **GLL** | ProShares UltraShort Gold | -2x | Gold |
| **SCO** | ProShares UltraShort Bloomberg Crude Oil | -2x | Crude Oil |
| **KOLD** | ProShares UltraShort Bloomberg Natural Gas | -2x | Natural Gas |
| **DZZ** | DB Silver Short ETN | -1x | Silver |
| **ZSL** | ProShares UltraShort Silver | -2x | Silver |

### 3.5 Volatility Inverse (Profitt ved VIX nedgang)

| Ticker | Navn | Leverage | Note |
|--------|------|----------|------|
| **SVXY** | ProShares Short VIX Short-Term Futures | -0.5x | Lavere risiko |
| **SVIX** | -1x Short VIX Futures ETF | -1x | Full inverse |

---

## 4. Anbefalt Strategi for FjordHQ

### 4.1 Primær Metode: PUT Opsjoner

For bearish signaler, bruk PUT opsjoner på underliggende:

```
Signal: BEARISH på SPY
Handling: Kjøp SPY PUT
Strike: ATM eller slightly OTM (5%)
Expiration: 30-60 dager
Max risiko: Premium betalt
```

### 4.2 Sekundær Metode: Inverse ETFs for Hedge

For portfolio-hedge uten opsjons-kompleksitet:

```
Portfolio Hedge: 5% av portfolio i SH eller SPXU
Trigger: Regime = RISK_OFF
Holding Period: Maks 5 handelsdager (pga. decay)
Rebalansering: Daglig vurdering
```

### 4.3 Ikke Anbefalt: Short Selling

Pga. HTB-risiko og ubegrenset tap, unngå direkte shorting.

---

## 5. FjordHQ Universe Expansion - Forslag

For å støtte bearish strategier, legg til disse inverse ETFs:

| Ticker | Formål | Prioritet |
|--------|--------|-----------|
| **SH** | S&P 500 hedge (-1x) | P1 |
| **SQQQ** | NASDAQ hedge (-3x) | P1 |
| **TBT** | Bond bear (-2x) | P2 |
| **FAZ** | Financials bear (-3x) | P2 |
| **ERY** | Energy bear (-2x) | P3 |

---

## 6. Kilder

### Alpaca Documentation
- [Options Trading Overview](https://docs.alpaca.markets/docs/options-trading-overview)
- [Margin and Short Selling](https://docs.alpaca.markets/docs/margin-and-short-selling)

### Inverse ETF Providers
- [ProShares Leveraged & Inverse ETFs](https://www.proshares.com/our-etfs/find-leveraged-and-inverse-etfs)
- [Direxion Leveraged & Inverse ETFs](https://www.direxion.com/)
- [ETF Database - Inverse ETFs](https://etfdb.com/etfs/inverse/)

### Research
- [StockBrokers.com - 41 Best Inverse ETFs 2026](https://www.stockbrokers.com/education/inverse-short-etfs-bearish-etf-funds)
- [NerdWallet - What Are Inverse ETFs?](https://www.nerdwallet.com/investing/learn/inverse-etfs)

---

## 7. Evidence Files

| Fil | Innhold |
|-----|---------|
| `CEO_DIR_2026_120_OPTIONS_LEVEL3_VERIFICATION.json` | Full PUT verifikasjon |
| `CEO_DIR_2026_ALPACA_OPTIONS_AND_INVERSE_INSTRUMENTS.md` | Dette dokumentet |

---

**Signed:** STIG (EC-003)
**Timestamp:** 2026-01-23T21:45:00.000Z
**Verification Hash:** 68e3b9d2a48f5ad9...
