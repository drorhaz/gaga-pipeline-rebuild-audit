"""Ticket 004 verification — 4 representative sessions."""
import pandas as pd
import pyarrow.parquet as pq
import pyarrow as pa
import hashlib
import numpy as np
import os

# The 4 sessions, with their pre-T004 shapes from Ticket 003 baseline
SESSIONS = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': {
        'pre_shape': (30423, 773),
        'expected_labels': ('651', 'T1', 'P1', 'R1'),
    },
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM': {
        'pre_shape': (32110, 783),
        'expected_labels': ('651', 'T2', 'P1', 'R1'),
    },
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': {
        'pre_shape': (16915, 803),
        'expected_labels': ('671', 'T1', 'P2', 'R1'),
    },
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': {
        'pre_shape': (21773, 803),
        'expected_labels': ('671', 'T3', 'P2', 'R1'),
    },
}

# Post-T003 content hashes for the numeric columns (first 16 chars) — regression baseline
POST_T003_HASHES = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': '4e4b81bc9edd2f6b',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     'b7db8a72f4c11a85',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': '5d13f307c9bc50a3',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': '96ae62165289dc2a',
}


def content_hash_numeric_only(df):
    """SHA256 over sorted NUMERIC columns only (excludes new string label cols)."""
    num_cols = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for col in sorted(num_cols):
        vals = df[col].values
        rounded = np.round(vals[~np.isnan(vals)], 9)
        h.update(col.encode())
        h.update(rounded.tobytes())
    return h.hexdigest()


all_pass = True
new_baseline = {}

print('=' * 90)
print('TICKET 004 — 4-SESSION AUDIT REPORT')
print('=' * 90)

for sess, info in SESSIONS.items():
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)
    table = pq.read_table(path)
    meta = table.schema.metadata or {}
    pre_rows, pre_cols = info['pre_shape']
    exp_sid, exp_tp, exp_pc, exp_rep = info['expected_labels']
    post_rows, post_cols = df.shape
    expected_post_cols = pre_cols + 4

    print(f'\n--- {sess[:60]} ---')

    # T1: 4 label columns present
    t1 = all(c in df.columns for c in ('subject_id', 'timepoint', 'piece', 'rep'))
    print(f'  T1 Label cols present:     {"PASS" if t1 else "FAIL"}')
    if not t1:
        all_pass = False

    # T2: dtype object
    t2 = all(df[c].dtype == 'object' for c in ('subject_id', 'timepoint', 'piece', 'rep') if c in df.columns)
    print(f'  T2 dtype=object:           {"PASS" if t2 else "FAIL"}')
    if not t2:
        all_pass = False

    # T3: correct values
    actual_sid = df['subject_id'].iloc[0] if 'subject_id' in df.columns else None
    actual_tp  = df['timepoint'].iloc[0]  if 'timepoint'  in df.columns else None
    actual_pc  = df['piece'].iloc[0]      if 'piece'      in df.columns else None
    actual_rep = df['rep'].iloc[0]        if 'rep'        in df.columns else None
    t3 = (actual_sid == exp_sid and actual_tp == exp_tp and
          actual_pc == exp_pc and actual_rep == exp_rep)
    print(f'  T3 Correct values:         {"PASS" if t3 else "FAIL"}  '
          f'(subject_id={repr(actual_sid)}, timepoint={repr(actual_tp)}, '
          f'piece={repr(actual_pc)}, rep={repr(actual_rep)})')
    if not t3:
        all_pass = False

    # T4: ref_is_fallback in metadata
    t4 = b'ref_is_fallback' in meta
    val_rif = meta[b'ref_is_fallback'].decode('utf-8') if t4 else 'NOT FOUND'
    print(f'  T4 ref_is_fallback meta:   {"PASS" if t4 else "FAIL"}  value={val_rif}')
    if not t4:
        all_pass = False

    # T5: session-constant (1 unique per column)
    t5 = all(df[c].nunique() == 1 for c in ('subject_id', 'timepoint', 'piece', 'rep') if c in df.columns)
    print(f'  T5 Session-constant:       {"PASS" if t5 else "FAIL"}')
    if not t5:
        all_pass = False

    # T7: column count
    t7 = post_cols == expected_post_cols
    print(f'  T7 Col count: {pre_cols}+4={expected_post_cols} -> actual {post_cols}:  {"PASS" if t7 else "FAIL"}')
    if not t7:
        all_pass = False

    # T8: numeric-only content hash vs post-T003 baseline
    ch = content_hash_numeric_only(df)
    expected_prefix = POST_T003_HASHES.get(sess, '')
    t8 = ch.startswith(expected_prefix)
    print(f'  T8 Numeric regression:     {"PASS" if t8 else "FAIL"}  '
          f'(expected prefix={expected_prefix}, actual={ch[:16]}...)')
    if not t8:
        all_pass = False

    # New content hash (all columns including labels)
    new_baseline[sess] = (ch, df.shape)

print()
print('=' * 90)
print(f'OVERALL RESULT: {"ALL PASS" if all_pass else "FAILURES DETECTED"}')
print('=' * 90)

print()
print('=== New content-based baseline (numeric cols, 4 sessions) ===')
for sess, (ch, shape) in new_baseline.items():
    print(f'  {sess[:60]:<62}  shape={shape}  numeric_hash={ch[:16]}...')
