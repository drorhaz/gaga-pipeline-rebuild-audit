"""Ticket 009 verification — 4 Dev Set sessions."""
import json, os, hashlib
import numpy as np
import pandas as pd

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

REQUIRED_FIELDS = [
    'n_artifact_segments_positions',
    'max_artifact_segment_frames_positions',
    'mean_artifact_segment_frames_positions',
    'n_artifact_segments_above_5_frames',
    'n_artifact_segments_above_10_frames',
    'n_gap_fill_events_positions',
    'n_gap_fill_events_quaternions',
    'max_gap_duration_frames_positions',
    'max_gap_duration_frames_quaternions',
]


def content_hash_numeric(df):
    num = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for c in sorted(num):
        v = df[c].values
        r = np.round(v[~np.isnan(v)], 9)
        h.update(c.encode()); h.update(r.tobytes())
    return h.hexdigest()


all_pass = True
print('=' * 90)
print('TICKET 009 VERIFICATION (4 DEV SET SESSIONS)')
print('=' * 90)

for sess in DEV_SET:
    print(f'\n--- {sess[:60]} ---')

    # T1: __s02_interpolation_stats.json exists with all 9 fields
    stats_path = f'derivatives/step_02_preprocess/{sess}__s02_interpolation_stats.json'
    if not os.path.exists(stats_path):
        print(f'  T1 sidecar exists:                   FAIL (file missing)')
        all_pass = False
        continue
    with open(stats_path) as f:
        stats = json.load(f)
    missing = [k for k in REQUIRED_FIELDS if k not in stats]
    t1 = (len(missing) == 0)
    print(f'  T1 sidecar exists + 9 required fields: {"PASS" if t1 else "FAIL (missing="+str(missing)+")"}')
    if not t1: all_pass = False

    # T2: Labels in __interpolation_log.json fixed
    log_path = f'derivatives/step_02_preprocess/{sess}__interpolation_log.json'
    with open(log_path) as f:
        log = json.load(f)
    t2_pos = log.get('position_method') == 'linear_interp'
    t2_quat = log.get('quaternion_method') == 'quaternion_normalize'
    print(f'  T2 __interpolation_log.json labels:   pos="{log.get("position_method")}" {"PASS" if t2_pos else "FAIL"}, '
          f'quat="{log.get("quaternion_method")}" {"PASS" if t2_quat else "FAIL"}')
    if not (t2_pos and t2_quat): all_pass = False

    # T3: Labels in __preprocess_summary.json fixed
    sum_path = f'derivatives/step_02_preprocess/{sess}__preprocess_summary.json'
    with open(sum_path) as f:
        psum = json.load(f)
    im = psum.get('interpolation_method', {})
    t3_pos = im.get('positions') == 'linear_interp'
    t3_quat = im.get('rotations') == 'quaternion_normalize'
    print(f'  T3 __preprocess_summary.json labels:  pos="{im.get("positions")}" {"PASS" if t3_pos else "FAIL"}, '
          f'rot="{im.get("rotations")}" {"PASS" if t3_quat else "FAIL"}')
    if not (t3_pos and t3_quat): all_pass = False

    # T4: 9-field values present (show actual measurements)
    print('  T4 Observed 9-field values:')
    for f in REQUIRED_FIELDS:
        print(f'      {f:<45} = {stats.get(f)}')

    # T5: Parquet numeric hash unchanged (LOCAL blast radius)
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)
    ch = content_hash_numeric(df)
    expected = POST_T007B_HASHES[sess]
    t5 = ch.startswith(expected)
    print(f'  T5 Parquet hash unchanged:          {"PASS" if t5 else "FAIL"}  ({ch[:16]}...)')
    if not t5: all_pass = False

print()
print('=' * 90)
print(f'OVERALL: {"ALL PASS" if all_pass else "FAILURES"}')
print('=' * 90)
