import sys, os, hashlib, numpy as np, pandas as pd
sys.path.insert(0, 'src')
from utils import discover_sessions_from_parquet

# Simulate NB08 Cell 5 assertion
deriv = 'derivatives'
parquet_sessions = set(discover_sessions_from_parquet(deriv))
json_sessions = set(
    f.replace('__step01_loader_report.json', '')
    for f in os.listdir('derivatives/step_01_parse')
    if f.endswith('__step01_loader_report.json')
)

print(f'Parquet sessions : {len(parquet_sessions)}')
print(f'JSON sessions    : {len(json_sessions)}')
consistent = (parquet_sessions == json_sessions)
print(f'CONSISTENT       : {consistent}')
if not consistent:
    print('  In parquet but not JSON:', parquet_sessions - json_sessions)
    print('  In JSON but not parquet:', json_sessions - parquet_sessions)

print()

# Dev Set hash regression
POST_BASELINE = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': '4e4b81bc9edd2f6b',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     'b7db8a72f4c11a85',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': '5d13f307c9bc50a3',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': '96ae62165289dc2a',
}
all_pass = True
for sess, exp in POST_BASELINE.items():
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)
    num = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for c in sorted(num):
        v = df[c].values
        r = np.round(v[~np.isnan(v)], 9)
        h.update(c.encode()); h.update(r.tobytes())
    ch = h.hexdigest()
    ok = ch.startswith(exp)
    if not ok:
        all_pass = False
    status = 'PASS' if ok else 'FAIL'
    print(f'{status}: {sess[:55]}')

print()
print('Assertion:', 'PASS' if consistent else 'FAIL')
print('Regression:', 'ALL PASS' if all_pass else 'FAIL')
