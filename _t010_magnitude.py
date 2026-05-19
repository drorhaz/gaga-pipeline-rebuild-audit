"""
Ticket 010 magnitude analysis — quantify ATF_axial change from removing Hips.

Runs compute_atf() on each Dev Set session twice:
  - With OLD JOINT_GROUPS['axial'] = [Hips, Spine, Spine1, Neck, Head]
  - With NEW JOINT_GROUPS['axial'] = [Spine, Spine1, Neck, Head]

Reports per-session: OLD, NEW, delta, % change. Plus per-joint ATF inputs.
"""
import sys, os
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.join('.', 'src'))

from v2_feature_engine import compute_atf, JOINT_GROUPS as _LIVE_JOINT_GROUPS

DEV_SET = [
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001',
]

OLD_AXIAL = ['Hips', 'Spine', 'Spine1', 'Neck', 'Head']
NEW_AXIAL = ['Spine', 'Spine1', 'Neck', 'Head']

def _group_median(atf_per_joint, group):
    vals = [atf_per_joint[j] for j in group
            if j in atf_per_joint and not (isinstance(atf_per_joint[j], float) and np.isnan(atf_per_joint[j]))]
    return float(np.median(vals)) if vals else float('nan')

print('=' * 100)
print('TICKET 010 MAGNITUDE ANALYSIS: OLD vs NEW atf_axial')
print('=' * 100)

results = []
for sess in DEV_SET:
    print(f'\n--- {sess[:60]} ---')
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)

    # Check which axial joints have __lin_vel_rel_mag column
    available = {}
    for j in OLD_AXIAL:
        c = f'{j}__lin_vel_rel_mag'
        available[j] = c in df.columns
    print(f'  Axial joints with __lin_vel_rel_mag column:')
    for j, ok in available.items():
        print(f'    {j}: {"present" if ok else "MISSING (silently dropped by NB06 gate)"}')

    # Call compute_atf with current JOINT_GROUPS (which currently has Hips)
    res = compute_atf(df, sess, params_f1={}, config={'fs': 120.0})

    # Per-joint ATF for axial group
    print(f'  Per-joint ATF (axial group only):')
    for j in OLD_AXIAL:
        v = res.atf_per_joint.get(j, None)
        v_str = f'{v:.6f}' if (v is not None and not (isinstance(v, float) and np.isnan(v))) else 'NaN/missing'
        print(f'    {j}: {v_str}')

    # Compute OLD and NEW medians directly (bypassing the LIVE JOINT_GROUPS)
    atf_axial_OLD = _group_median(res.atf_per_joint, OLD_AXIAL)
    atf_axial_NEW = _group_median(res.atf_per_joint, NEW_AXIAL)

    delta = atf_axial_NEW - atf_axial_OLD
    pct = (100.0 * delta / atf_axial_OLD) if atf_axial_OLD not in (0, None) and not np.isnan(atf_axial_OLD) else float('nan')

    print(f'  atf_axial OLD (with Hips):    {atf_axial_OLD:.6f}')
    print(f'  atf_axial NEW (no Hips):      {atf_axial_NEW:.6f}')
    print(f'  delta:                        {delta:+.6f}')
    print(f'  % change:                     {pct:+.3f}%')

    results.append({
        'session': sess[:60],
        'atf_axial_OLD': atf_axial_OLD,
        'atf_axial_NEW': atf_axial_NEW,
        'delta': delta,
        'pct': pct,
    })

print()
print('=' * 100)
print('SUMMARY:')
print('=' * 100)
for r in results:
    print(f"  {r['session']:<62}  OLD={r['atf_axial_OLD']:.4f}  NEW={r['atf_axial_NEW']:.4f}  "
          f"delta={r['delta']:+.4f}  ({r['pct']:+.2f}%)")
