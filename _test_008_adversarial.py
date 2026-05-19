"""
Ticket 008 — adversarial synthetic tests.

Proves the new OR-union and tightened 0.20 threshold fire correctly on synthetic
inputs DESIGNED to expose the old behavior's weakness, and confirms no regression
in Tickets 005/006 (NaN sanitization and dead-session guard).
"""
import sys
import json
import math
import numpy as np
import pandas as pd

sys.path.insert(0, '.')
from src.v2_feature_engine import compute_quality_gates, validate_reference
from src.reference import compute_q_ref_and_ref_qc

ALL_19_JOINTS = [
    'Hips', 'Spine', 'Spine1', 'Neck', 'Head',
    'LeftShoulder', 'LeftArm', 'LeftForeArm', 'LeftHand',
    'RightShoulder', 'RightArm', 'RightForeArm', 'RightHand',
    'LeftUpLeg', 'LeftLeg', 'LeftFoot',
    'RightUpLeg', 'RightLeg', 'RightFoot',
]
N = 10000  # 10000 frames, ~83 s at 120 Hz

def _empty_df(n=N):
    df = pd.DataFrame({'time_s': [i/120.0 for i in range(n)], 'frame_idx': range(n)})
    for j in ALL_19_JOINTS:
        df[f'{j}__is_artifact'] = 0
    return df

failures = []

# ===========================================================================
# A1: OR-union catches what max() would miss
# ===========================================================================
# Setup: each of 6 joints has 10% artifact rate at DIFFERENT, non-overlapping
# frame ranges. max(joint_art_rates) = 0.10 (OLD: hard_exclude=False under any
# old/new threshold). OR-union = 6 × 10% = 60% (NEW: hard_exclude=True under 0.20).
print('=== A1: OR-union catches scattered artifacts that max() misses ===')
df_a1 = _empty_df()
chunk = N // 10  # 10% chunk size
for i, joint in enumerate(['Hips', 'Spine', 'LeftArm', 'RightArm', 'LeftLeg', 'RightLeg']):
    start = i * chunk
    end = start + chunk
    df_a1.loc[start:end-1, f'{joint}__is_artifact'] = 1

q = compute_quality_gates({'a1': df_a1}, {})
row_a1 = q[q['run_id'] == 'a1'].iloc[0]
print(f'  global_artifact_frac (OR-union): {row_a1["global_artifact_frac"]:.4f}')
print(f'  clean_fraction_pca:              {row_a1["clean_fraction_pca"]:.4f}')
print(f'  hard_exclude (NEW behavior):     {bool(row_a1["hard_exclude"])}')
# OLD max behavior: max(0.10, 0.10, ..., 0.0) = 0.10, would be hard_exclude=False under any threshold
print(f'  OLD max would give:              0.10 (would be hard_exclude=False under both 0.30 and 0.20)')
expected_or = 0.6  # 6 joints × 10% non-overlapping
got_close = abs(row_a1['global_artifact_frac'] - expected_or) < 0.01
hard_excl_correct = bool(row_a1['hard_exclude']) is True
if not (got_close and hard_excl_correct):
    failures.append('A1: OR-union not capturing scattered artifacts')
    print('  RESULT: FAIL')
else:
    print(f'  RESULT: PASS — OR-union={row_a1["global_artifact_frac"]:.2f}, hard_exclude=True')

# ===========================================================================
# A2: OLD threshold 0.30 would pass, NEW threshold 0.20 catches
# ===========================================================================
# Setup: single joint with 25% artifact rate (concentrated). All other joints clean.
# OR-union = 0.25 (since other joints clean for those frames too, OR = max here).
# OLD: 0.25 < 0.30 → hard_exclude=False.
# NEW: 0.25 > 0.20 → hard_exclude=True.
print()
print('=== A2: 0.25 artifact frac — old 0.30 passes, new 0.20 catches ===')
df_a2 = _empty_df()
df_a2.loc[0:N//4-1, 'Hips__is_artifact'] = 1  # 25% of frames in Hips
q = compute_quality_gates({'a2': df_a2}, {})
row_a2 = q[q['run_id'] == 'a2'].iloc[0]
print(f'  global_artifact_frac:            {row_a2["global_artifact_frac"]:.4f}')
print(f'  hard_exclude (NEW art_crit=0.20):{bool(row_a2["hard_exclude"])}')
# Now run with explicit OLD threshold to confirm OLD would have passed
q_old = compute_quality_gates({'a2': df_a2}, {'artifact_critical_threshold': 0.30})
row_a2_old = q_old[q_old['run_id'] == 'a2'].iloc[0]
print(f'  hard_exclude (OLD art_crit=0.30):{bool(row_a2_old["hard_exclude"])}')
correct = (
    abs(row_a2['global_artifact_frac'] - 0.25) < 0.001
    and bool(row_a2['hard_exclude']) is True
    and bool(row_a2_old['hard_exclude']) is False
)
if not correct:
    failures.append('A2: threshold change not behaving as expected')
    print('  RESULT: FAIL')
else:
    print('  RESULT: PASS — new threshold catches; old would have passed')

# ===========================================================================
# A3: REGRESSION — Ticket 006 dead session still hard_excludes
# ===========================================================================
print()
print('=== A3 (Ticket 006 regression): dead session ===')
df_a3 = pd.DataFrame({'time_s': [0.0]*5, 'frame_idx': range(5)})
for j in ALL_19_JOINTS:
    df_a3[f'{j}__is_artifact'] = 0
q = compute_quality_gates({'a3_dead': df_a3}, {})
row_a3 = q[q['run_id'] == 'a3_dead'].iloc[0]
print(f'  n_frames=5, hard_exclude:        {bool(row_a3["hard_exclude"])}')
print(f'  short_session:                   {bool(row_a3["short_session"])}')
if not bool(row_a3['hard_exclude']):
    failures.append('A3: dead session no longer hard_excludes (Ticket 006 regression)')
    print('  RESULT: FAIL')
else:
    print('  RESULT: PASS — Ticket 006 logic preserved')

# ===========================================================================
# A4: Clean session unchanged
# ===========================================================================
print()
print('=== A4: clean session is hard_exclude=False ===')
df_a4 = _empty_df()
q = compute_quality_gates({'a4_clean': df_a4}, {})
row_a4 = q[q['run_id'] == 'a4_clean'].iloc[0]
print(f'  global_artifact_frac:            {row_a4["global_artifact_frac"]:.4f}')
print(f'  hard_exclude:                    {bool(row_a4["hard_exclude"])}')
correct = (
    row_a4['global_artifact_frac'] == 0.0
    and bool(row_a4['hard_exclude']) is False
)
if not correct:
    failures.append('A4: clean session is incorrectly hard_excluded')
    print('  RESULT: FAIL')
else:
    print('  RESULT: PASS — clean session unaffected')

# ===========================================================================
# A5: REGRESSION — Ticket 005 NaN→None serialization
# ===========================================================================
print()
print('=== A5 (Ticket 005 regression): t_pose_failed -> JSON null ===')
n_j = 3
q_local = np.tile([0.0, 0.0, 0.0, 1.0], (200, n_j, 1)).astype(float)
ref_info_fail = {'t_pose_failed': True, 'ref_start': 0.0, 'ref_end': 1.0, 'method': 'test'}
_, qc = compute_q_ref_and_ref_qc(None, q_local, ref_info_fail, [], [], {'REF_WINDOW_SEC': 1.0, 'FS_TARGET': 120.0})
try:
    json_text = json.dumps(qc, allow_nan=False)
    json_ok = True
except Exception as e:
    json_text = ''
    json_ok = False
print(f'  ref_quality_score is None:       {qc["ref_quality_score"] is None}')
print(f'  identity_error_ref_med is None:  {qc["identity_error_ref_med"] is None}')
print(f'  JSON dumps with allow_nan=False: {json_ok}')
if not (qc['ref_quality_score'] is None and qc['identity_error_ref_med'] is None and json_ok):
    failures.append('A5: Ticket 005 regression - NaN sanitization broken')
    print('  RESULT: FAIL')
else:
    print('  RESULT: PASS — Ticket 005 JSON safety preserved')

# ===========================================================================
# A6: New boundary test — exactly 20% artifact
# ===========================================================================
print()
print('=== A6: boundary — exactly 20.00% artifact frac ===')
df_a6 = _empty_df()
df_a6.loc[0:N//5-1, 'Hips__is_artifact'] = 1  # 20% of frames
q = compute_quality_gates({'a6': df_a6}, {})
row_a6 = q[q['run_id'] == 'a6'].iloc[0]
print(f'  global_artifact_frac:            {row_a6["global_artifact_frac"]:.6f}')
print(f'  hard_exclude (threshold is strict >): {bool(row_a6["hard_exclude"])}')
# At exactly 0.20, strict > comparison means hard_exclude=False
if bool(row_a6['hard_exclude']) is not False:
    failures.append('A6: exactly 0.20 should NOT trigger hard_exclude (strict >)')
    print('  RESULT: FAIL')
else:
    print('  RESULT: PASS — boundary behaves as strict > (excluded only if >0.20)')

# ===========================================================================
# Summary
# ===========================================================================
print()
print('=' * 65)
if failures:
    print(f'FAILURES: {len(failures)}')
    for f in failures:
        print(f'  - {f}')
    sys.exit(1)
else:
    print('ALL 6 ADVERSARIAL SYNTHETIC TESTS PASS')
print('=' * 65)
