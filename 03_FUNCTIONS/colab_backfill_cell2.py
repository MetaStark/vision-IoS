# CELL 2: Main backfill script - Copy this entire file into Google Colab
import yfinance as yf
import pandas as pd
import requests_cache
import time
from datetime import datetime, timedelta
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Configure cache
requests_cache.install_cache('yfinance_cache', expire_after=timedelta(hours=24))

# ============================================================================
# ALL 515 TICKERS FROM FjordHQ DATABASE
# ============================================================================

# CRYPTO - 50 assets
CRYPTO = [
    "AAVE-USD", "ADA-USD", "ALGO-USD", "APT-USD", "ATOM-USD", "AVAX-USD",
    "AXS-USD", "BCH-USD", "BNB-USD", "BTC-USD", "CHZ-USD", "COMP-USD",
    "CRO-USD", "CRV-USD", "DOGE-USD", "DOT-USD", "EOS-USD", "ETC-USD",
    "ETH-USD", "FIL-USD", "FLOW-USD", "FTM-USD", "GRT-USD", "HBAR-USD",
    "ICP-USD", "INJ-USD", "LDO-USD", "LINK-USD", "LTC-USD", "MANA-USD",
    "MATIC-USD", "MKR-USD", "NEAR-USD", "OKB-USD", "QNT-USD", "RPL-USD",
    "RUNE-USD", "SAND-USD", "SHIB-USD", "SNX-USD", "SOL-USD", "THETA-USD",
    "TRX-USD", "UNI-USD", "VET-USD", "XLM-USD", "XMR-USD", "XRP-USD",
    "XTZ-USD", "ZEC-USD"
]

# FX - 25 pairs
FX = [
    "AUDJPY=X", "AUDUSD=X", "CADJPY=X", "CHFJPY=X", "EURAUD=X", "EURCHF=X",
    "EURGBP=X", "EURJPY=X", "EURNOK=X", "EURSEK=X", "EURUSD=X", "GBPJPY=X",
    "GBPUSD=X", "NZDUSD=X", "USDCAD=X", "USDCHF=X", "USDHKD=X", "USDJPY=X",
    "USDMXN=X", "USDNOK=X", "USDSEK=X", "USDSGD=X", "USDTRY=X", "USDZAR=X"
]

# US EQUITIES & ETFs
US_EQUITY = [
    "SPY", "QQQ", "IWM", "DIA", "VOO", "VTI", "XLF", "XLE", "XLK", "XLV",
    "XLI", "XLU", "XLB", "XLY", "XLP", "XLC", "XLRE",
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "UNH", "JNJ", "V", "MA", "XOM", "JPM", "PG", "HD", "CVX", "MRK", "ABBV",
    "PFE", "KO", "PEP", "WMT", "DIS", "NFLX", "AMD", "INTC", "CRM", "ADBE", "NOW",
    "COST", "AVGO", "TMO", "ORCL", "ABT", "DHR", "NEE", "LLY", "TXN", "QCOM",
    "RTX", "BA", "HON", "CAT", "UPS", "GE", "LOW", "UNP", "LMT", "GD", "NOC",
    "SBUX", "NKE", "MCD", "AMGN", "GILD", "BAC", "WFC", "C", "GS", "MS", "BLK",
    "ISRG", "MDT", "BMY", "CVS", "CI", "ELV", "HUM", "REGN", "VRTX", "ZTS",
    "SYK", "BSX", "MCK", "EW", "DXCM",
    "SCHW", "CB", "PGR", "AXP", "CME", "ICE", "AON", "MMC", "USB", "PNC",
    "TFC", "AIG", "MET", "COF", "AFL", "ALL", "TRV", "SPGI", "MCO", "MSCI",
    "FDX", "LHX", "ITW", "EMR", "ROK", "ETN", "PH", "WM", "RSG", "CTAS",
    "CARR", "OTIS", "CSX", "NSC", "DAL", "UAL", "LUV", "DE",
    "CMG", "YUM", "MAR", "HLT", "TGT", "ROST", "ORLY", "AZO", "NVR", "LEN",
    "DHI", "PHM", "EBAY", "ETSY", "DECK", "LULU", "DPZ", "POOL", "TJX",
    "PM", "MO", "CL", "EL", "KMB", "GIS", "KHC", "HSY", "MDLZ", "SYY", "KR",
    "CAG", "CHD", "CLX", "STZ",
    "ADI", "CDNS", "SNPS", "NXPI", "MCHP", "FTNT", "ZS", "OKTA", "WDAY",
    "ANSS", "INTU", "ADSK", "TEAM", "HUBS", "DOCU", "MDB", "SPLK", "FIVN",
    "AKAM", "AMAT", "KLAC", "LRCX", "MU", "MRVL", "PANW", "CRWD", "DDOG", "NET",
    "PSX", "VLO", "MPC", "HES", "DVN", "FANG", "HAL", "BKR", "KMI", "WMB",
    "OKE", "COP", "EOG", "SLB", "OXY", "FCX", "NEM",
    "AEP", "D", "XEL", "EXC", "SRE", "PCG", "WEC", "ES", "ED", "EIX", "DUK", "SO",
    "AWK", "ECL", "DD", "DOW", "PPG", "NUE", "STLD", "VMC", "MLM", "ALB",
    "IFF", "CTVA", "CF", "APD", "LIN", "SHW",
    "AMT", "CCI", "EQIX", "DLR", "PLD", "SPG", "WELL", "AVB", "EQR", "PSA", "SBAC", "VICI",
    "CHTR", "WBD", "PARA", "FOX", "EA", "TTWO", "LYV", "MTCH", "T", "VZ", "TMUS", "CMCSA",
    "PYPL", "SQ", "COIN", "SHOP", "SNOW", "PLTR", "ROKU", "ZM", "UBER", "LYFT",
    "RIVN", "LCID", "F", "GM", "ABNB", "BKNG"
]

# OSLO BORS - Norwegian equities
OSLO = [
    "EQNR.OL", "DNB.OL", "MOWI.OL", "TEL.OL", "YAR.OL", "ORK.OL", "AKRBP.OL",
    "SALM.OL", "STB.OL", "NHY.OL", "SUBC.OL", "AKER.OL", "BAKKA.OL", "SCHA.OL",
    "KOG.OL", "PGS.OL", "AUSS.OL", "CRAYN.OL", "BWO.OL", "AUTO.OL", "AKSO.OL",
    "AKVA.OL", "BELCO.OL", "BEWI.OL", "REC.OL", "NEL.OL", "SCATC.OL", "VAR.OL",
    "LSG.OL", "GOGL.OL", "FRO.OL", "FLNG.OL", "HAFNI.OL", "STRO.OL", "KAHOT.OL",
    "KID.OL", "XXL.OL", "PROTCT.OL", "ELMRA.OL", "ENTRA.OL", "SRBNK.OL",
    "SCHB.OL", "GJFAH.OL", "GJF.OL", "TGS.OL", "PHO.OL", "NOD.OL", "WAWI.OL",
    "TOM.OL", "MORG.OL", "OLT.OL"
]

# GERMAN DAX
GERMAN = [
    "SAP.DE", "SIE.DE", "ALV.DE", "DTE.DE", "BAS.DE", "BAYN.DE", "BMW.DE",
    "MRK.DE", "ADS.DE", "1COV.DE", "AIR.DE", "VOW3.DE", "HEN3.DE", "CON.DE",
    "RWE.DE", "CBK.DE", "BEI.DE", "FRE.DE", "BNR.DE", "DBK.DE", "EOAN.DE",
    "IFX.DE", "MBG.DE", "MUV2.DE", "PAH3.DE", "QIA.DE", "SHL.DE", "VNA.DE",
    "ZAL.DE", "HFG.DE", "SRT3.DE", "MTX.DE", "RHM.DE", "P911.DE", "DHL.DE",
    "DHER.DE", "HNR1.DE", "ENR.DE", "SY1.DE"
]

# FRENCH CAC
FRENCH = [
    "MC.PA", "OR.PA", "TTE.PA", "SAN.PA", "AI.PA", "AIR.PA", "BNP.PA",
    "SU.PA", "ACA.PA", "CS.PA", "CAP.PA", "BN.PA", "ATO.PA", "ALO.PA",
    "DG.PA", "DSY.PA", "EL.PA", "EN.PA", "ENGI.PA", "ERF.PA", "GLE.PA",
    "HO.PA", "KER.PA", "LR.PA", "ML.PA", "ORA.PA", "PUB.PA", "RI.PA",
    "RMS.PA", "RNO.PA", "SAF.PA", "SGO.PA", "STM.PA", "TEP.PA", "URW.PA",
    "VIE.PA", "VIV.PA", "WLN.PA"
]

# UK FTSE
UK = [
    "HSBA.L", "SHEL.L", "AZN.L", "BP.L", "ULVR.L", "GSK.L", "RIO.L", "DGE.L",
    "BATS.L", "AAL.L", "BHP.L", "BA.L", "BARC.L", "AV.L", "CPG.L", "BT-A.L",
    "GLEN.L", "IAG.L", "III.L", "LGEN.L", "LLOY.L", "NG.L", "NWG.L", "PRU.L",
    "REL.L", "RKT.L", "RR.L", "SSE.L", "STAN.L", "TSCO.L", "VOD.L"
]

# Combine all assets
ALL_ASSETS = {
    "CRYPTO": CRYPTO,
    "FX": FX,
    "US_EQUITY": US_EQUITY,
    "OSLO": OSLO,
    "GERMAN": GERMAN,
    "FRENCH": FRENCH,
    "UK": UK
}

def download_with_retry(tickers, max_retries=3):
    """Download with exponential backoff"""
    for attempt in range(max_retries):
        try:
            df = yf.download(
                tickers,
                period="10y",
                interval="1d",
                auto_adjust=False,
                group_by='ticker',
                progress=True,
                threads=False
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            wait = 60 * (attempt + 1)
            print(f"Attempt {attempt+1} failed: {e}. Waiting {wait}s...")
            time.sleep(wait)
    return None

# Process each category
all_data = {}
total_tickers = sum(len(v) for v in ALL_ASSETS.values())
print(f"Total tickers to download: {total_tickers}")

for category, tickers in ALL_ASSETS.items():
    print(f"\n{'='*60}")
    print(f"Downloading {category}: {len(tickers)} tickers")
    print(f"{'='*60}")

    batch_size = 30
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(tickers) + batch_size - 1) // batch_size
        print(f"\nBatch {batch_num}/{total_batches}: {len(batch)} tickers")

        df = download_with_retry(" ".join(batch))

        if df is not None and not df.empty:
            all_data[f"{category}_batch_{batch_num}"] = df
            print(f"SUCCESS: Downloaded {len(df)} rows")
        else:
            print(f"FAILED: No data for batch")

        if i + batch_size < len(tickers):
            print("Waiting 90s between batches...")
            time.sleep(90)

    print(f"\nCategory {category} complete. Waiting 120s...")
    time.sleep(120)

print("\n\n" + "="*60)
print("DOWNLOAD COMPLETE!")
print("="*60)

# Save to CSV
for name, df in all_data.items():
    filename = f"/content/{name}_prices.csv"
    df.to_csv(filename)
    print(f"Saved: {filename}")

# Download files
from google.colab import files
print("\nDownloading files...")
for name in all_data.keys():
    try:
        files.download(f"/content/{name}_prices.csv")
    except:
        print(f"Manual download: {name}_prices.csv")

print("\nDone! Import with: python import_colab_prices.py --csv-dir <path>")
