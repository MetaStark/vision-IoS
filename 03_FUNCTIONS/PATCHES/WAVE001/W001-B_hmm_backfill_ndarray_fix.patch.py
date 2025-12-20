"""
WAVE-001 PATCH: W001-B — HMM_BACKFILL ndarray Index Fix
========================================================
Target: hmm_backfill_v1.py
Issue: index/take ndarray error during HMM inference
Root Cause: iterrows() index doesn't match numpy array indices after filtering
Fix: Use enumerate() for proper array indexing

Author: STIG (CTO)
Date: 2025-12-03
Authority: CEO_DIRECTIVE_WAVE001_20251203
"""

# PATCH INSTRUCTIONS:
# Apply to: 03_FUNCTIONS/hmm_backfill_v1.py

# CHANGE 1: Line 628-629 - Fix array index mismatch
# OLD:
#     for idx, row in features_df.iterrows():
#         state = hidden_states[idx]
# NEW:
#     for i, (idx, row) in enumerate(features_df.iterrows()):
#         state = hidden_states[i]
#         confidence = float(confidence_scores[i])

# CHANGE 2: Add array length validation before decode (after line 607)
# ADD:
#     if len(X) == 0:
#         print(f"  WARNING: No valid features for {asset_id}")
#         stats['assets'][asset_id] = {'rows': 0, 'error': 'Empty feature matrix'}
#         continue
#
#     # Validate no NaN values remain
#     if np.isnan(X).any():
#         print(f"  WARNING: NaN values in feature matrix for {asset_id}, filling with 0")
#         X = np.nan_to_num(X, nan=0.0)

# CHANGE 3: Line 633 - Use enumerate index for confidence
# OLD:
#     confidence = float(confidence_scores[idx])
# NEW:
#     # confidence already set in the for loop header

PATCH_ID = "W001-B"
PATCH_TARGET = "hmm_backfill_v1.py"
PATCH_ISSUE = "iterrows() DataFrame index misaligns with numpy array indices"
PATCH_FIX = "Use enumerate() for sequential array access"
