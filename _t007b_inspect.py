"""Inspect quaternion norm behavior in S04 filtered parquet for Ticket 007b design."""
import pandas as pd
import numpy as np

sess = '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002'
df = pd.read_parquet(f'derivatives/step_04_filtering/{sess}__filtered.parquet')

# Find all quaternion columns
quat_cols_by_joint = {}
for c in df.columns:
    if c.endswith('__qx') or c.endswith('__qy') or c.endswith('__qz') or c.endswith('__qw'):
        joint = c.rsplit('__', 1)[0]
        quat_cols_by_joint.setdefault(joint, []).append(c)

print(f'Total joints with quaternions: {len(quat_cols_by_joint)}')
print()

print('=== Per-joint quaternion norm stats (post-S04 — what NB06 consumes) ===')
print(f'{"joint":<22} {"n":<8} {"norm_mean":<12} {"norm_std":<12} {"norm_min":<12} {"norm_max":<12} {"pct_norm>1.05_or<0.95":<22}')
joints_with_issue = []
for joint, cols in list(quat_cols_by_joint.items()):
    cols_sorted = sorted(cols, key=lambda c: 'xyzw'.index(c[-1]))
    if len(cols_sorted) != 4:
        continue
    Q = df[cols_sorted].values
    # Filter NaN rows
    valid = ~np.isnan(Q).any(axis=1)
    Qv = Q[valid]
    if len(Qv) == 0:
        continue
    norms = np.linalg.norm(Qv, axis=1)
    renorm_burden_count = int(np.sum(np.abs(norms - 1.0) > 0.05))
    renorm_burden_pct = 100.0 * renorm_burden_count / len(norms)
    print(f'{joint:<22} {len(Qv):<8} {norms.mean():<12.6f} {norms.std():<12.6f} '
          f'{norms.min():<12.6f} {norms.max():<12.6f} {renorm_burden_pct:<22.2f}')
    if renorm_burden_pct > 5.0:
        joints_with_issue.append((joint, renorm_burden_pct))

print()
print(f'Joints with renorm_burden_pct > 5%: {len(joints_with_issue)}')
for j, p in joints_with_issue:
    print(f'  {j}: {p:.2f}%')

# Check hemisphere flips
print()
print('=== Per-joint hemisphere flip detection ===')
print(f'{"joint":<22} {"n_pairs":<10} {"n_flips":<10} {"flip_pct":<10}')
for joint, cols in list(quat_cols_by_joint.items())[:5]:
    cols_sorted = sorted(cols, key=lambda c: 'xyzw'.index(c[-1]))
    if len(cols_sorted) != 4:
        continue
    Q = df[cols_sorted].values
    valid = ~np.isnan(Q).any(axis=1)
    Qv = Q[valid]
    if len(Qv) < 2:
        continue
    # A flip is when dot(q_t, q_t+1) < 0
    dots = np.sum(Qv[:-1] * Qv[1:], axis=1)
    n_flips = int(np.sum(dots < 0))
    flip_pct = 100.0 * n_flips / max(len(dots), 1)
    print(f'{joint:<22} {len(dots):<10} {n_flips:<10} {flip_pct:<10.3f}')
