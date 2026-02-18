@echo off
schtasks /delete /tn "FjordHQ_OutcomeSettlement_Daemon" /f
schtasks /create /tn "FjordHQ_OutcomeSettlement_Daemon" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_settlement_continuous.bat" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_OutcomeSettlement_Daemon"
schtasks /query /tn "FjordHQ_OutcomeSettlement_Daemon" /fo LIST
pause
