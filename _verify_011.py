"""Ticket 011 verification — is_hampel_outlier now reflects actual Hampel activity."""
import json, os, hashlib, numpy as np, pandas as pd

DEV_SET = [
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001',
]

POST_T007B_HASHES = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': '4e4b81bc9edd2f6b',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     'b7db8a72f4c11a85',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': '5d13f307c9bc50a3',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': '96ae62165289dc2a',
}

def content_hash_numeric_only(df):
    num = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for c in sorted(num):
        v = df[c].values
        r = np.round(v[~np.isnan(v)], 9)
        h.update(c.encode()); h.update(r.tobytes())
    return h.hexdigest()

all_pass = True
print('=' * 90)
print('TICKET 011 VERIFICATION')
print('=' * 90)

for sess in DEV_SET:
    print(f'\n--- {sess[:60]} ---')

    # T1: OR mask sidecar exists
    mask_path = f'derivatives/step_04_filtering/{sess}__s04_hampel_or_mask.npy'
    t1 = os.path.exists(mask_path)
    print(f'  T1 OR mask sidecar exists:          {"PASS" if t1 else "FAIL"}')
    if not t1: all_pass = False; continue

    # Load mask and parquet
    or_mask = np.load(mask_path)
    n_flagged = int(np.sum(or_mask))
    df = pd.read_parquet(f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet')

    # T2: is_hampel_outlier column exists
    hampel_cols = [c for c in df.columns if '__is_hampel_outlier' in c]
    t2 = len(hampel_cols) > 0
    print(f'  T2 is_hampel_outlier cols in parquet: {"PASS" if t2 else "FAIL"}  ({len(hampel_cols)} cols)')
    if not t2: all_pass = False

    # T3: is_hampel_outlier is NOT all-False (it was before Ticket 011)
    # Note: some sessions may have 0 Hampel activity — OK. Check if mask n_flagged > 0.
    filt_sum_path = f'derivatives/step_04_filtering/{sess}__filtering_summary.json'
    with open(filt_sum_path) as f:
        fs = json.load(f)
    total_h = fs.get('filter_params', {}).get('total_hampel_outliers', 0)
    # If total_h > 0, the column should have True values
    if total_h > 0:
        col = hampel_cols[0] if hampel_cols else None
        col_true = int(df[col].sum()) if col else 0
        t3 = col_true > 0
        print(f'  T3 is_hampel_outlier has True values: {"PASS" if t3 else "FAIL"}  '
              f'(total_h_frames={total_h}, or_mask_flagged={n_flagged}, col_True={col_true})')
    else:
        t3 = True  # Zero activity is OK
        print(f'  T3 (N/A — zero Hampel activity for this session)')
    if not t3: all_pass = False

    # T4: All is_hampel_outlier columns hold the SAME value per frame (they're all OR mask)
    if hampel_cols and n_flagged > 0:
        vals = np.column_stack([df[c].values for c in hampel_cols])
        row_same = np.all(vals == vals[:, 0:1], axis=1)
        t4 = bool(np.all(row_same))
        print(f'  T4 All hampel cols identical (OR mask):{"PASS" if t4 else "FAIL"}')
        if not t4: all_pass = False
    else:
        print(f'  T4 (N/A — no flagged frames to compare)')

    # T5: Numeric columns (excluding bool) hash unchanged
    numeric_hash = content_hash_numeric_only(df)
    exp = POST_T007B_HASHES.get(sess, '')
    t5 = numeric_hash.startswith(exp)
    print(f'  T5 Numeric hash unchanged:          {"PASS" if t5 else "FAIL"}  ({numeric_hash[:16]}...)')
    if not t5: all_pass = False

    print(f'  Summary: total_hampel_outliers={total_h}, or_mask_flagged_frames={n_flagged}, '
          f'col_count={len(hampel_cols)}')

print()
print('=' * 90)
print(f'OVERALL: {"ALL PASS" if all_pass else "FAILURES"}')
print('=' * 90)
