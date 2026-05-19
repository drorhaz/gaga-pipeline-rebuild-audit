"""Ticket 007b verification — 4 Dev Set sessions."""
import json
import os
import hashlib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

DEV_SET = [
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001',
]

# Post-T007a numeric baseline (same as post-T004)
POST_T007A_HASHES = {
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002': '4e4b81bc9edd2f6b',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM':     'b7db8a72f4c11a85',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002': '5d13f307c9bc50a3',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001': '96ae62165289dc2a',
}


def content_hash_numeric(df):
    num_cols = df.select_dtypes(include='number').columns.tolist()
    h = hashlib.sha256()
    for col in sorted(num_cols):
        vals = df[col].values
        rounded = np.round(vals[~np.isnan(vals)], 9)
        h.update(col.encode())
        h.update(rounded.tobytes())
    return h.hexdigest()


print('=' * 90)
print('TICKET 007b VERIFICATION (4 DEV SET SESSIONS)')
print('=' * 90)

all_pass = True

for sess in DEV_SET:
    print(f'\n--- {sess[:60]} ---')

    # Load validation_report.json
    val_path = f'derivatives/step_06_kinematics/{sess}__validation_report.json'
    with open(val_path) as f:
        val = json.load(f)

    # T1: quaternion_diagnostics present
    qd = val.get('quaternion_diagnostics')
    t1 = qd is not None
    print(f'  T1 quaternion_diagnostics block present:        {"PASS" if t1 else "FAIL"}')
    if not t1:
        all_pass = False
        continue

    # T2: both global and relative sub-blocks present
    t2 = ('global_quat_integrity' in qd) and ('relative_quat_drift' in qd)
    print(f'  T2 both sub-blocks present:                    {"PASS" if t2 else "FAIL"}')
    if not t2: all_pass = False

    # T3: per-joint fields are correct shape (require non-empty global and relative blocks)
    global_block = qd.get('global_quat_integrity', {})
    rel_block = qd.get('relative_quat_drift', {})
    needed = {'quat_norm_mean', 'quat_norm_std', 'quat_norm_min', 'quat_norm_max', 'renorm_burden_pct'}
    if not global_block:
        t3a = False
        global_msg = 'EMPTY (expected non-empty from S04 input)'
    else:
        sample_global = next(iter(global_block.values()))
        t3a = needed.issubset(set(sample_global.keys()))
        global_msg = f'{len(global_block)} joints'
    if not rel_block:
        t3b = False
        rel_msg = 'EMPTY'
    else:
        sample_rel = next(iter(rel_block.values()))
        t3b = needed.issubset(set(sample_rel.keys()))
        rel_msg = f'{len(rel_block)} joints'
    print(f'  T3 per-joint fields:  global={"PASS ("+global_msg+")" if t3a else "FAIL ("+global_msg+")"}  rel={"PASS ("+rel_msg+")" if t3b else "FAIL ("+rel_msg+")"}')
    if not (t3a and t3b): all_pass = False

    # T4: verdict is one of the allowed enum values
    verdict = qd.get('rotation_method_verdict', '')
    t4 = verdict in ('CURRENT_METHOD_ACCEPTABLE', 'REVIEW_SO3_SMOOTHING', 'SO3_UPGRADE_RECOMMENDED')
    print(f'  T4 rotation_method_verdict valid:              {"PASS" if t4 else "FAIL"} ({verdict})')
    if not t4: all_pass = False

    # T5: lin_kine_diagnostics present
    lkd = val.get('lin_kine_diagnostics')
    needed_lkd = {'gate', 'dropped_axes', 'n_joints_with_dropped_axes', 'total_axes_silently_dropped'}
    t5 = lkd is not None and needed_lkd.issubset(set(lkd.keys()))
    print(f'  T5 lin_kine_diagnostics block:                 {"PASS" if t5 else "FAIL"}')
    if t5:
        print(f'      n_joints_with_dropped_axes={lkd["n_joints_with_dropped_axes"]}, '
              f'total_axes_silently_dropped={lkd["total_axes_silently_dropped"]}')
    if not t5: all_pass = False

    # T6: filtering_summary.json has Hampel fields
    filt_path = f'derivatives/step_04_filtering/{sess}__filtering_summary.json'
    with open(filt_path) as f:
        filt = json.load(f)
    fp = filt.get('filter_params', {})
    needed_h = {'hampel_modification_fraction_per_joint', 'hampel_max_fraction_any_joint', 'hampel_joints_above_threshold'}
    t6 = needed_h.issubset(set(fp.keys()))
    print(f'  T6 filtering_summary.json Hampel fields:       {"PASS" if t6 else "FAIL"}')
    if t6:
        print(f'      max_frac_any_joint={fp.get("hampel_max_fraction_any_joint")}, '
              f'joints_above={fp.get("hampel_joints_above_threshold")}')
    if not t6: all_pass = False

    # T7: JSON loads without numeric NaN/Inf literals
    # (a JSON-numeric NaN looks like ": NaN" or ": Infinity"; bare "NaN" in a string field is fine)
    import re as _re_v
    json_nan_pattern = _re_v.compile(r':\s*(NaN|Infinity|-Infinity)\b')
    nan_in_val = bool(json_nan_pattern.search(open(val_path).read()))
    nan_in_filt = bool(json_nan_pattern.search(open(filt_path).read()))
    # Also verify the JSONs parse cleanly with strict mode
    try:
        with open(val_path) as f: json.loads(f.read())
        with open(filt_path) as f: json.loads(f.read())
        json_parses = True
    except Exception as e:
        json_parses = False
    t7 = (not nan_in_val) and (not nan_in_filt) and json_parses
    print(f'  T7 JSON numeric-NaN/Inf absent and parses:     {"PASS" if t7 else "FAIL"}')
    if not t7: all_pass = False

    # T8: numeric content hash unchanged (LOCAL blast radius)
    path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'
    df = pd.read_parquet(path)
    ch = content_hash_numeric(df)
    exp = POST_T007A_HASHES.get(sess, '')
    t8 = ch.startswith(exp)
    print(f'  T8 numeric hash unchanged from post-T007a:     {"PASS" if t8 else "FAIL"}  ({ch[:16]}...)')
    if not t8: all_pass = False

    # T9: PyArrow metadata still has all 5 fields from T007a
    table = pq.read_table(path)
    meta = table.schema.metadata or {}
    needed_meta = {b'ref_is_fallback', b'filter_psd_verdict', b'pipeline_version', b'gate_01_status', b'bone_qc_status'}
    t9 = needed_meta.issubset(set(meta.keys()))
    print(f'  T9 PyArrow metadata (T007a) intact:            {"PASS" if t9 else "FAIL"}')
    if not t9: all_pass = False

print()
print('=' * 90)
print(f'OVERALL: {"ALL PASS" if all_pass else "FAILURES DETECTED"}')
print('=' * 90)
