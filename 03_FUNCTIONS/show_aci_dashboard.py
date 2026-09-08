#!/usr/bin/env python3
"""Display ACI Triangle Dashboard from API."""
import urllib.request
import json

try:
    with urllib.request.urlopen('http://localhost:3000/api/aci-triangle') as response:
        d = json.loads(response.read().decode())
except Exception as e:
    print(f"Error fetching API: {e}")
    exit(1)

print('=' * 70)
print('ACI CONSTRAINT TRIANGLE - SHADOW MODE')
print('=' * 70)
print()

# Summary header
s = d.get('summary', {})
print(f"Database: {s.get('totalNeedlesInDatabase', 0)} needles | Chain Hash: {s.get('needlesWithChainHash', 0)}/{s.get('totalNeedlesInDatabase', 0)} ({s.get('chainHashCoverage', 0):.0f}%)")
print(f"Sample Evaluated: {s.get('totalNeedlesEvaluated', 0)} | Mode: {s.get('mode', 'SHADOW')} | Filter: {s.get('assetFilter', 'CRYPTO_ONLY')}")
print()

# EC-020 SitC
sitc = d.get('sitc', {})
integrity = 100 - sitc.get('brokenChainRate', 0)
print('-' * 70)
print('EC-020 SitC (Reasoning Chain Integrity)           [Prefrontal Cortex]')
print('-' * 70)
print(f"  Chain Integrity:    {integrity:.0f}%")
print(f"  Broken Chains:      {sitc.get('brokenChains', 0)} / {sitc.get('totalEvaluated', 0)}")
print(f"  Avg Score:          {sitc.get('avgScore', 0):.3f}")
reasons = sitc.get('reasonDistribution', {})
if reasons:
    print(f"  Failure Types:      {reasons}")
else:
    print(f"  Failure Types:      None (all chains valid)")
print()

# EC-021 InForage
inf = d.get('inforage', {})
balance = inf.get('currentBalance', 0)
budget = inf.get('budgetCapUsd', 50)
ratio = balance / budget if budget > 0 else 0
status = 'HEALTHY' if ratio > 0.5 else 'CAUTION' if ratio > 0.2 else 'CRITICAL'
print('-' * 70)
print('EC-021 InForage (API Budget Discipline)           [CFO of Curiosity]')
print('-' * 70)
print(f"  DeepSeek Balance:   ${balance:.2f} (LIVE from API)")
print(f"  Budget Cap:         ${budget:.2f}/day")
print(f"  Balance Ratio:      {ratio*100:.1f}% [{status}]")
print(f"  Source:             DEEPSEEK_API_BALANCE")
print()

# EC-022 IKEA
ikea = d.get('ikea', {})
confidence = ikea.get('avgScore', 1) * 100
print('-' * 70)
print('EC-022 IKEA (Hallucination Firewall)              [Conscience]')
print('-' * 70)
print(f"  Confidence Score:   {confidence:.0f}%")
print(f"  Flagged Total:      {ikea.get('flaggedTotal', 0)} / {ikea.get('totalEvaluated', 0)}")
print(f"  Fabrications:       {ikea.get('fabricationCount', 0)}")
print(f"  Stale Data:         {ikea.get('staleDataCount', 0)}")
print(f"  Unverifiable:       {ikea.get('unverifiableCount', 0)}")
print()

print('=' * 70)
last_scan = s.get('lastFullScanAt', 'Never')
if last_scan and last_scan != 'Never':
    from datetime import datetime
    dt = datetime.fromisoformat(last_scan.replace('Z', '+00:00'))
    last_scan = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
print(f"Last Scan: {last_scan}")
print('=' * 70)
