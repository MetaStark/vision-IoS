#!/usr/bin/env python3
"""
CEO-DIR-045: Start outcome_settlement_daemon as background process
"""
import subprocess
import sys
import os
import time

DAEMON_SCRIPT = "C:\\fhq-market-system\\vision-ios\\03_FUNCTIONS\\outcome_settlement_daemon.py"
PYTHON_PATH = "C:\\Python312\\python.exe"

print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting outcome_settlement_daemon in continuous mode...")

# Start the daemon in continuous mode
process = subprocess.Popen(
    [PYTHON_PATH, DAEMON_SCRIPT, "--continuous", "--interval", "3600"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
)

print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Daemon PID: {process.pid}")
print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Daemon started. Monitoring output...")

# Wait a bit to see initial output
time.sleep(5)

# Check if process is still running
if process.poll() is None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Daemon is running")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] To stop: kill {process.pid} or Ctrl+C")
else:
    stdout, stderr = process.communicate()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Daemon exited with code {process.returncode}")
    if stderr:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error: {stderr}")
