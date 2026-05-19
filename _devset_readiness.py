"""Dev Set readiness check: verify all pipeline stages + Ticket 001-004 artifacts exist."""
import os, json
import pandas as pd
import pyarrow.parquet as pq

DEV_SET = [
    '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002',
    '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM',
    '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002',
    '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001',
]

CHECKS = {
    # Ticket 001 — config snapshot
    'T001 config_snapshot.yaml':
        lambda s: f'derivatives/step_00_config/{s}__config_snapshot.yaml',
    # Ticket 002 — S01 gate (PASS sessions should NOT have fail report)
    'S01 parsed_run.parquet':
        lambda s: f'derivatives/step_01_parse/{s}__parsed_run.parquet',
    'S01 step01_loader_report.json':
        lambda s: f'derivatives/step_01_parse/{s}__step01_loader_report.json',
    # S02
    'S02 preprocessed.parquet':
        lambda s: f'derivatives/step_02_preprocess/{s}__preprocessed.parquet',
    # S03
    'S03 resampled.parquet':
        lambda s: f'derivatives/step_03_resample/{s}__resampled.parquet',
    'S03 resample_summary.json':
        lambda s: f'derivatives/step_03_resample/{s}__resample_summary.json',
    # S04
    'S04 filtered.parquet':
        lambda s: f'derivatives/step_04_filtering/{s}__filtered.parquet',
    'S04 filtering_summary.json':
        lambda s: f'derivatives/step_04_filtering/{s}__filtering_summary.json',
    # S05
    'S05 reference_metadata.json':
        lambda s: f'derivatives/step_05_reference/{s}__reference_metadata.json',
    # S06 + Ticket 004
    'S06 kinematics_master.parquet':
        lambda s: f'derivatives/step_06_kinematics/{s}__kinematics_master.parquet',
    'S06 validation_report.json':
        lambda s: f'derivatives/step_06_kinematics/{s}__validation_report.json',
}

all_ok = True
print(f'{"Artifact":<36}', end='')
for s in DEV_SET:
    label = s[:20]
    print(f'  {label:<22}', end='')
print()
print('-' * (36 + 4 * 24))

for check_name, path_fn in CHECKS.items():
    print(f'{check_name:<36}', end='')
    for s in DEV_SET:
        p = path_fn(s)
        exists = os.path.exists(p)
        if not exists:
            all_ok = False
        print(f'  {"OK" if exists else "MISSING!!":<22}', end='')
    print()

# Deep check for Ticket 004 on the kinematics parquets
print()
print('=== Ticket 004 deep check (label cols + metadata) ===')
for s in DEV_SET:
    path = f'derivatives/step_06_kinematics/{s}__kinematics_master.parquet'
    if not os.path.exists(path):
        print(f'  {s[:50]}: MISSING PARQUET')
        all_ok = False
        continue
    df = pd.read_parquet(path)
    table = pq.read_table(path)
    meta = table.schema.metadata or {}
    has_labels = all(c in df.columns for c in ('subject_id','timepoint','piece','rep'))
    has_rif = b'ref_is_fallback' in meta
    col_count = len(df.columns)
    sid_val = df['subject_id'].iloc[0] if 'subject_id' in df.columns else 'N/A'
    tp_val  = df['timepoint'].iloc[0]  if 'timepoint'  in df.columns else 'N/A'
    pc_val  = df['piece'].iloc[0]      if 'piece'      in df.columns else 'N/A'
    rp_val  = df['rep'].iloc[0]        if 'rep'        in df.columns else 'N/A'
    rif_val = meta[b'ref_is_fallback'].decode() if has_rif else 'MISSING'
    status = 'READY' if (has_labels and has_rif) else 'INCOMPLETE'
    if status != 'READY':
        all_ok = False
    print(f'  {s[:50]:<52} cols={col_count}  labels={has_labels}  '
          f'ref_is_fallback={has_rif}({rif_val})  [{status}]')
    print(f'    values: subject_id={repr(sid_val)} timepoint={repr(tp_val)} '
          f'piece={repr(pc_val)} rep={repr(rp_val)}')

# Check Ticket 003 — resample_summary.json has new fields
print()
print('=== Ticket 003 resample_summary.json field check ===')
for s in DEV_SET:
    path = f'derivatives/step_03_resample/{s}__resample_summary.json'
    if os.path.exists(path):
        with open(path) as f:
            d = json.load(f)
        has_fields = all(k in d for k in ('n_frames_input','n_frames_output','frame_count_delta'))
        print(f'  {s[:50]:<52} n_in={d.get("n_frames_input")} n_out={d.get("n_frames_output")} '
              f'delta={d.get("frame_count_delta")} fields_ok={has_fields}')
    else:
        print(f'  {s[:50]:<52} MISSING')

print()
print('=' * 80)
print(f'DEV SET READINESS: {"ALL READY" if all_ok else "GAPS DETECTED — SEE ABOVE"}')
print('=' * 80)
