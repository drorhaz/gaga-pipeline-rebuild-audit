"""Diagnose T3 (global per-joint fields incomplete) and T7 (NaN in JSON) failures."""
import pandas as pd
import json
import re

sess = '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002'
df = pd.read_parquet(f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet')

plain_qx = [c for c in df.columns if c.endswith('__qx') and 'rel' not in c]
zero_rel_qx = [c for c in df.columns if c.endswith('__zeroed_rel_qx')]
raw_rel_qx = [c for c in df.columns if c.endswith('__raw_rel_qx')]
print(f'Plain __qx (no rel) columns: {len(plain_qx)}')
print(f'  first 3: {plain_qx[:3]}')
print(f'Zeroed_rel_qx columns: {len(zero_rel_qx)}')
print(f'Raw_rel_qx columns: {len(raw_rel_qx)}')

# Check validation_report
with open(f'derivatives/step_06_kinematics/{sess}__validation_report.json') as f:
    content = f.read()
v = json.loads(content)
gqi = v.get('quaternion_diagnostics', {}).get('global_quat_integrity', {})
rqd = v.get('quaternion_diagnostics', {}).get('relative_quat_drift', {})
print(f'\nglobal_quat_integrity joints: {len(gqi)}')
print(f'relative_quat_drift joints: {len(rqd)}')
if gqi:
    j = next(iter(gqi))
    print(f'  Sample global joint "{j}": {gqi[j]}')
if rqd:
    j = next(iter(rqd))
    print(f'  Sample rel joint "{j}": {rqd[j]}')

# Find NaN literal
nan_matches = [(m.start(), m.group()) for m in re.finditer(r'\bNaN\b', content)]
print(f'\nNaN literal count: {len(nan_matches)}')
for pos, _ in nan_matches[:5]:
    snippet = content[max(0, pos-80):pos+50]
    print(f'  at offset {pos}: ...{snippet}...')
