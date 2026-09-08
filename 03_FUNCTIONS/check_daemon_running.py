#!/usr/bin/env python3
import psutil
import os

# Check for outcome_settlement_daemon.py running
daemon_running = False
daemon_pids = []

for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        if 'outcome_settlement_daemon.py' in proc.info['cmdline']:
            daemon_running = True
            daemon_pids.append(proc.info['pid'])
            print(f"FOUND: PID {proc.info['pid']} - {proc.info['cmdline']}")
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass

if not daemon_running:
    print("NOT RUNNING: No outcome_settlement_daemon.py process found")

print(f"\nTotal Python processes: {len([p for p in psutil.process_iter(['name']) if 'python' in p.info['name']])}")
