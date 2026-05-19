"""Ticket 003 verification: confirm all 14 sessions gained exactly +1 frame at S06."""
import pandas as pd, hashlib, numpy as np, os, json

# Pre-Ticket-003 (Ticket 001) baseline shapes
pre_t003 = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': (30423, 773),
    '651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002': (19303, 803),
    '651_T1_P2_R2_Take 2026-01-15 04.35.25 PM_005': (19894, 803),
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     (32109, 783),
    '651_T2_P2_R1_Take 2026-01-26 05.24.12 PM_000': (21601, 803),
    '651_T3_P1_R1_2026-02-11 05.50.42 PM_2026':     (30834, 803),
    '651_T3_P2_R1_2026-02-11 05.50.42 PM_2027':     (22486, 803),
    '651_T3_P2_R2_2026-02-11 05.50.42 PM_2030':     (22960, 803),
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': (16914, 803),
    '671_T1_P2_R2_Take 2026-01-06 03.57.12 PM_004': (17685, 803),
    '671_T2_P2_R1_Take 2026-01-15 04.35.25 PM_006': (20046, 803),
    '671_T2_P2_R2_Take 2026-01-15 04.35.25 PM_010': (20764, 803),
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': (21772, 803),
    '671_T3_P2_R2_Take 2026-02-03 08.05.01 PM_006': (22215, 803),
}


def content_hash(path):
    df = pd.read_parquet(path)
    num_cols = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for col in sorted(num_cols):
        vals = df[col].values
        rounded = np.round(vals[~np.isnan(vals)], 9)
        h.update(col.encode())
        h.update(rounded.tobytes())
    return h.hexdigest(), df.shape


print('=== S06 frame-count delta verification (14 sessions) ===')
print('-' * 110)
deltas = []
new_baseline = {}
for sess, (pre_rows, pre_cols) in pre_t003.items():
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    ch, (post_rows, post_cols) = content_hash(path)
    row_delta = post_rows - pre_rows
    col_delta = post_cols - pre_cols
    status = 'OK' if (row_delta == 1 and col_delta == 0) else 'UNEXPECTED'
    deltas.append(row_delta)
    new_baseline[sess] = (ch, (post_rows, post_cols))
    print(f'  {sess[:50]:<52} ({pre_rows},{pre_cols}) -> ({post_rows},{post_cols})  d_rows=+{row_delta}  d_cols={col_delta:+d}  [{status}]')

print()
print(f'Set of row-deltas:', set(deltas))
print(f'14/14 gained exactly +1 frame:', all(d == 1 for d in deltas))

print()
print('=== New content-based golden baseline (post-Ticket-003) ===')
for sess, (ch, shape) in new_baseline.items():
    print(f'  {sess[:50]:<52}  shape={shape}  content={ch[:16]}...')

# Also verify the resample_summary.json contains the new fields
print()
print('=== S03 resample_summary.json field check (sample 3 sessions) ===')
for sess in list(pre_t003.keys())[:3]:
    sp = f'derivatives/step_03_resample/{sess}__resample_summary.json'
    with open(sp) as f:
        s = json.load(f)
    nf_in = s.get('n_frames_input')
    nf_out = s.get('n_frames_output')
    delta = s.get('frame_count_delta')
    print(f'  {sess[:50]:<52} n_in={nf_in}  n_out={nf_out}  delta={delta}')
