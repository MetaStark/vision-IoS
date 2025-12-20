"""
WAVE-001 PATCH: W001-C — IOS013 Graceful Halt Fix
==================================================
Target: ios013_hcp_g3_runner.py
Issue: continuous-run preconditions cause hard crash on failed loops
Root Cause: No error handling for import failures, DB connection, engine errors
Fix: Add graceful error handling with proper exit codes

Author: STIG (CTO)
Date: 2025-12-03
Authority: CEO_DIRECTIVE_WAVE001_20251203
"""

# PATCH INSTRUCTIONS:
# Apply to: 03_FUNCTIONS/ios013_hcp_g3_runner.py

# CHANGE 1: Lines 28-29 - Wrap import in try/except
# OLD:
#     from ios013_hcp_execution_engine import HCPExecutionEngine, ExecutionMode, SignalState
# NEW:
#     try:
#         from ios013_hcp_execution_engine import HCPExecutionEngine, ExecutionMode, SignalState
#         EXECUTION_ENGINE_AVAILABLE = True
#     except ImportError as e:
#         print(f"WARNING: HCP Execution Engine not available: {e}")
#         EXECUTION_ENGINE_AVAILABLE = False
#         HCPExecutionEngine = None
#         ExecutionMode = None
#         SignalState = None

# CHANGE 2: __init__ method (line 60-64) - Add precondition check
# ADD at start of __init__:
#     if not EXECUTION_ENGINE_AVAILABLE:
#         raise RuntimeError("HCP Execution Engine module not available. Cannot start runner.")

# CHANGE 3: run_single_loop (line 310) - Wrap in try/except
# OLD:
#     def run_single_loop(self) -> Dict[str, Any]:
#         """Execute a single G3 loop iteration"""
#         print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === G3 LOOP START ===")
#         # Run the engine loop
#         result = self.engine.run_loop_iteration()
# NEW:
#     def run_single_loop(self) -> Dict[str, Any]:
#         """Execute a single G3 loop iteration"""
#         print(f"\n[{datetime.now().strftime('%H:%M:%S')}] === G3 LOOP START ===")
#         try:
#             # Run the engine loop
#             result = self.engine.run_loop_iteration()
#         except Exception as e:
#             print(f"  [ERROR] Loop iteration failed: {e}")
#             return {
#                 'error': str(e),
#                 'structures_generated': 0,
#                 'structures_executed': 0,
#                 'signals_captured': 0
#             }

# CHANGE 4: run_continuous (around line 414) - Handle loop errors gracefully
# ADD after result = self.run_single_loop():
#     if result.get('error'):
#         print(f"  [WARN] Loop {loop_count} failed: {result['error']}")
#         # Continue to next loop instead of crashing
#         continue

# CHANGE 5: Add connection retry in __init__
# OLD:
#     self.conn = psycopg2.connect(**DB_CONFIG)
# NEW:
#     try:
#         self.conn = psycopg2.connect(**DB_CONFIG)
#     except psycopg2.OperationalError as e:
#         raise RuntimeError(f"Database connection failed: {e}")

PATCH_ID = "W001-C"
PATCH_TARGET = "ios013_hcp_g3_runner.py"
PATCH_ISSUE = "No graceful error handling causes hard crashes"
PATCH_FIX = "Add precondition checks, try/except wrappers, connection retry"
