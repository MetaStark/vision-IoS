@echo off
schtasks /delete /tn "FjordHQ_DecisionPackGenerator" /f
schtasks /create /tn "FjordHQ_DecisionPackGenerator" /tr "C:\fhq-market-system\vision-ios\03_FUNCTIONS\run_decision_pack_generator.bat" /sc onstart /rl highest /ru "SYSTEM" /f
schtasks /run /tn "FjordHQ_DecisionPackGenerator"
schtasks /query /tn "FjordHQ_DecisionPackGenerator" /fo LIST
pause
