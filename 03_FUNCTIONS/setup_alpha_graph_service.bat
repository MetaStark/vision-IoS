@echo off
schtasks /delete /tn "FjordHQ_AlphaGraphSync" /f
schtasks /create /tn "FjordHQ_AlphaGraphSync" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_alpha_graph_sync.bat" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_AlphaGraphSync"
schtasks /query /tn "FjordHQ_AlphaGraphSync" /fo LIST
pause
