"""
WAVE-001 PATCH: W001-A — IOS012 Unicode/Logging Fix
=====================================================
Target: ios012_g3_system_loop.py
Issue: print_summary uses Unicode box-drawing character that crashes on Windows
Root Cause: UTF-8 encoding not enforced on stdout/stderr
Fix: Replace Unicode chars with ASCII, normalize output encoding

Author: STIG (CTO)
Date: 2025-12-03
Authority: CEO_DIRECTIVE_WAVE001_20251203
"""

# PATCH INSTRUCTIONS:
# Apply to: 03_FUNCTIONS/ios012_g3_system_loop.py

# CHANGE 1: Line 1036 - Replace Unicode box drawing with ASCII
# OLD:
#     self.logger.info(f"    ─────────────────────────────────")
# NEW:
#     self.logger.info(f"    -------------------------------------")

# CHANGE 2: Add encoding normalization to setup_logging()
# After line 285 (handler = logging.StreamHandler(sys.stdout)), add:
#     import io
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
#     sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# CHANGE 3: Wrap print_summary in try/except for deterministic exit
# OLD (line 1180):
#     self.metrics.print_summary()
# NEW:
#     try:
#         self.metrics.print_summary()
#     except UnicodeEncodeError as e:
#         self.logger.warning(f"Summary print failed (encoding): {e}")

PATCH_ID = "W001-A"
PATCH_TARGET = "ios012_g3_system_loop.py"
PATCH_ISSUE = "Unicode box-drawing character causes UnicodeEncodeError on Windows"
PATCH_FIX = "Replace Unicode with ASCII, add encoding fallback"
