"""Unit tests for Tickets 005 and 006."""
import sys, os, math, json, numpy as np
sys.path.insert(0, '.')
import importlib

# Use package imports (project root on path)
from src.reference import compute_q_ref_and_ref_qc
from src.v2_feature_engine import compute_quality_gates, build_pca_engine
import pandas as pd

print('=== TICKET 005: ref_quality_score / t_pose_failed guards ===')

n_joints = 3
T = 200
q_local = np.tile([0.0, 0.0, 0.0, 1.0], (T, n_joints, 1)).astype(float)
cfg = {'REF_WINDOW_SEC': 1.0, 'FS_TARGET': 120.0}

# T1: t_pose_failed=True path → ref_quality_score and identity_error_ref_med must be None
ref_info_fail = {'t_pose_failed': True, 'ref_start': 0.0, 'ref_end': 1.0, 'method': 'test'}
_, qc = compute_q_ref_and_ref_qc(None, q_local, ref_info_fail, [], [], cfg)
t1a = qc['ref_quality_score'] is None
t1b = qc['identity_error_ref_med'] is None
t1c = True
try:
    json.dumps(qc)
except Exception as e:
    t1c = False
    print(f'  JSON error: {e}')
print(f'T1 t_pose_failed path: rqs=None={t1a}  iem=None={t1b}  JSON_valid={t1c}')
assert t1a and t1b and t1c, 'FAIL T1'
print('  PASS')

# T2: Valid path → ref_quality_score is finite float, JSON valid
time_s = np.linspace(0, 5.0, T)
ref_info_ok = {'t_pose_failed': False, 'ref_start': 0.5, 'ref_end': 1.5, 'method': 'criteria',
               'ref_is_fallback': False, 'gravity_guard_passed': True}
_, qc2 = compute_q_ref_and_ref_qc(time_s, q_local, ref_info_ok, [0, 1, 2], [0, 1, 2], cfg)
t2a = isinstance(qc2['ref_quality_score'], float) and math.isfinite(qc2['ref_quality_score'])
t2b = True
try:
    json.dumps(qc2)
except Exception as e:
    t2b = False
print(f'T2 valid path: rqs_finite_float={t2a}  JSON_valid={t2b}')
assert t2a and t2b, 'FAIL T2'
print('  PASS')

print()
print('=== TICKET 006: hard_exclude dead session guard ===')

ALL_JOINTS = ['Hips','Spine','Spine1','Neck','Head','LeftShoulder','LeftArm','LeftForeArm',
              'LeftHand','RightShoulder','RightArm','RightForeArm','RightHand','LeftUpLeg',
              'LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot']

# T3: Dead session (5 frames) → hard_exclude=True
dead_df = pd.DataFrame({'time_s': [0.0]*5, 'frame_idx': range(5)})
for j in ALL_JOINTS:
    dead_df[f'{j}__is_artifact'] = 0
qdf = compute_quality_gates({'dead': dead_df}, {})
t3 = bool(qdf[qdf['run_id'] == 'dead'].iloc[0]['hard_exclude'])
print(f'T3 dead session (5 frames) hard_exclude=True: {t3}')
assert t3, 'FAIL T3'
print('  PASS')

# T4: Normal session (4000 frames, 0 artifacts) → hard_exclude=False
norm_df = pd.DataFrame({'time_s': [i/120.0 for i in range(4000)], 'frame_idx': range(4000)})
for j in ALL_JOINTS:
    norm_df[f'{j}__is_artifact'] = 0
qdf2 = compute_quality_gates({'normal': norm_df}, {})
t4 = not bool(qdf2[qdf2['run_id'] == 'normal'].iloc[0]['hard_exclude'])
print(f'T4 normal session hard_exclude=False: {t4}')
assert t4, 'FAIL T4'
print('  PASS')

# T5: build_pca_engine skips excluded session
def _make_df(n=5000):
    df = pd.DataFrame({'time_s': [i/120.0 for i in range(n)]})
    for j in ALL_JOINTS:
        df[f'{j}__zeroed_rel_omega_mag'] = np.random.rand(n)
        df[f'{j}__is_artifact'] = 0
    return df

ref_df = _make_df()
other_df = _make_df(500)  # would normally get transformed
sessions = {'ref': ref_df, 'other': other_df}
engine = build_pca_engine(sessions, 'ref', {}, excluded_run_ids={'other'})
t5 = 'other' not in engine.scores_by_run
print(f'T5 excluded session not in PCA scores: {t5}')
assert t5, 'FAIL T5'
print('  PASS')

print()
print('ALL TESTS PASS')
