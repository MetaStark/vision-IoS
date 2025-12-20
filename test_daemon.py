#!/usr/bin/env python3
"""Quick test of g2c_alpha_daemon"""
import sys
sys.path.insert(0, r'C:\fhq-market-system\vision-ios\03_FUNCTIONS')
import g2c_alpha_daemon
d = g2c_alpha_daemon.G2CAlphaDaemon()
d.connect()
ctx = d.get_market_context()
print('Market Context:', ctx)
d.close()
