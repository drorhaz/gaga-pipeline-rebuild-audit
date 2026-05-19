"""Ticket 010 adversarial synthetic + real-data verification."""
import sys, os
import numpy as np
import pandas as pd
import hashlib

sys.path.insert(0, os.path.join('.', 'src'))
from v2_feature_engine import JOINT_GROUPS, compute_atf

failures = []

# ===========================================================================
# A0: Verify JOINT_GROUPS["axial"] no longer contains Hips
# ===========================================================================
print('=== A0: JOINT_GROUPS["axial"] does not contain "Hips" ===')
axial = JOINT_GROUPS['axial']
print(f'  Current JOINT_GROUPS["axial"]: {axial}')
a0 = ('Hips' not in axial) and (axial == ['Spine', 'Spine1', 'Neck', 'Head'])
print('  RESULT:', 'PASS' if a0 else 'FAIL')
if not a0: failures.append('A0')

# ===========================================================================
# A1: _group_median with Hips=0 in synthetic data → OLD vs NEW comparison
# ===========================================================================
print()
print('=== A1: Synthetic median — Hips=0 bias demonstrated ===')
synthetic_atf = {
    'Hips':  0.0,    # always 0 by definition
    'Spine': 0.5,
    'Spine1': 0.6,
    'Neck':  0.7,
    'Head':  0.8,
}
def _group_median(d, group):
    vals = [d[j] for j in group if j in d and not (isinstance(d[j], float) and np.isnan(d[j]))]
    return float(np.median(vals)) if vals else float('nan')

OLD_AXIAL = ['Hips', 'Spine', 'Spine1', 'Neck', 'Head']
NEW_AXIAL = ['Spine', 'Spine1', 'Neck', 'Head']
old_med = _group_median(synthetic_atf, OLD_AXIAL)   # median of [0, 0.5, 0.6, 0.7, 0.8] = 0.6
new_med = _group_median(synthetic_atf, NEW_AXIAL)   # median of [0.5, 0.6, 0.7, 0.8] = 0.65
print(f'  Synthetic atf_per_joint: {synthetic_atf}')
print(f'  OLD median (with Hips=0): {old_med}  (expected 0.6)')
print(f'  NEW median (no Hips):     {new_med}  (expected 0.65)')
a1 = (abs(old_med - 0.6) < 1e-9) and (abs(new_med - 0.65) < 1e-9)
print('  RESULT:', 'PASS' if a1 else 'FAIL')
if not a1: failures.append('A1')

# ===========================================================================
# A2: Real-data verification using NEW code on 4 Dev Set sessions
# ===========================================================================
print()
print('=== A2: Real-data verification — NEW compute_atf matches pre-computed expected values ===')
EXPECTED_NEW = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': 0.820153,
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     0.853659,
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': 0.967603,
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': 0.929982,
}

for sess, exp in EXPECTED_NEW.items():
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)
    res = compute_atf(df, sess, params_f1={}, config={'fs': 120.0})
    got = res.atf_axial
    ok = abs(got - exp) < 1e-4
    print(f'  {sess[:60]:<62} expected={exp:.6f} got={got:.6f} {"PASS" if ok else "FAIL"}')
    if not ok: failures.append(f'A2 {sess[:30]}')

# ===========================================================================
# A3: Kinematics_master.parquet numeric hash UNCHANGED
# ===========================================================================
print()
print('=== A3: kinematics_master.parquet hash unchanged from post-T007a baseline ===')
POST_T007A_HASHES = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': '4e4b81bc9edd2f6b',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     'b7db8a72f4c11a85',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': '5d13f307c9bc50a3',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': '96ae62165289dc2a',
}
def content_hash_numeric(df):
    num = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for c in sorted(num):
        v = df[c].values
        r = np.round(v[~np.isnan(v)], 9)
        h.update(c.encode()); h.update(r.tobytes())
    return h.hexdigest()
for sess, exp in POST_T007A_HASHES.items():
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)
    ch = content_hash_numeric(df)
    ok = ch.startswith(exp)
    print(f'  {sess[:60]:<62} expected_prefix={exp} got={ch[:16]} {"PASS" if ok else "FAIL"}')
    if not ok: failures.append(f'A3 {sess[:30]}')

print()
print('=' * 70)
if failures:
    print(f'FAILURES: {failures}')
    sys.exit(1)
else:
    print('ALL ADVERSARIAL + REAL-DATA TESTS PASS')
print('=' * 70)
