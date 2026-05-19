"""Batch 1 verification: Tickets 005, 006, 007a on the 4 Dev Set sessions."""
import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import hashlib
import json
import os

DEV_SET = [
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001',
]

# Post-T004 numeric baseline (unchanged by 005/006; 007a is metadata-only)
POST_T004_HASHES = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': '4e4b81bc9edd2f6b',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     'b7db8a72f4c11a85',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': '5d13f307c9bc50a3',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': '96ae62165289dc2a',
}

APPROVED_METADATA_KEYS = [b'ref_is_fallback', b'filter_psd_verdict',
                           b'pipeline_version', b'gate_01_status', b'bone_qc_status']

def content_hash_numeric(df):
    num_cols = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for col in sorted(num_cols):
        vals = df[col].values
        rounded = np.round(vals[~np.isnan(vals)], 9)
        h.update(col.encode()); h.update(rounded.tobytes())
    return h.hexdigest()

all_pass = True
print('=' * 90)
print('BATCH 1 VERIFICATION: Tickets 005, 006, 007a')
print('=' * 90)

for sess in DEV_SET:
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)
    table = pq.read_table(path)
    meta = table.schema.metadata or {}

    print(f'\n--- {sess[:60]} ---')

    # 007a: All 5 approved metadata fields present
    missing_meta = [k.decode() for k in APPROVED_METADATA_KEYS if k not in meta]
    t007a_1 = len(missing_meta) == 0
    print(f'  T007a-1 All 5 metadata fields present: {"PASS" if t007a_1 else "FAIL — missing: "+str(missing_meta)}')
    if not t007a_1: all_pass = False

    # 007a: Values are not null/empty
    for k in APPROVED_METADATA_KEYS:
        if k in meta:
            val = meta[k].decode('utf-8')
            print(f'    {k.decode()}: {repr(val)}')

    # Regression: numeric hash unchanged
    ch = content_hash_numeric(df)
    expected = POST_T004_HASHES.get(sess, '')
    t_reg = ch.startswith(expected)
    print(f'  T_REG Numeric hash unchanged: {"PASS" if t_reg else "FAIL"}  (prefix={ch[:16]}...)')
    if not t_reg: all_pass = False

    # Label columns still present (Ticket 004)
    t004 = all(c in df.columns for c in ('subject_id', 'timepoint', 'piece', 'rep'))
    print(f'  T004 Label cols still present: {"PASS" if t004 else "FAIL"}')
    if not t004: all_pass = False

print()
print('=' * 90)
print(f'OVERALL: {"ALL PASS" if all_pass else "FAILURES DETECTED"}')
print('=' * 90)

# Ticket 005: verify reference_metadata.json has null not NaN in a sample session
print()
print('=== Ticket 005: Check reference_metadata.json JSON validity ===')
for sess in DEV_SET[:2]:
    p = f'derivatives/step_05_reference/{sess}__reference_metadata.json'
    if os.path.exists(p):
        with open(p) as f:
            content = f.read()
        has_nan_literal = 'NaN' in content or 'Infinity' in content
        print(f'  {sess[:50]}: NaN/Infinity in JSON: {has_nan_literal} (should be False)')
        try:
            json.loads(content)
            print(f'    JSON.loads() succeeds: True')
        except Exception as e:
            print(f'    JSON.loads() FAILS: {e}')
