"""Column count diff across all 4 Dev Set sessions — trace every source of variation."""
import pandas as pd, re, collections

SESSIONS = {
    '651_T1': '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002',
    '651_T2': '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM',
    '671_T1': '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002',
    '671_T3': '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001',
}

dfs = {label: pd.read_parquet(f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet')
       for label, sess in SESSIONS.items()}

# Classify each column by its family
def classify(col):
    if col in ('run_id', 'frame_idx', 'time_s', 'qc_frame_valid',
               'subject_id', 'timepoint', 'piece', 'rep'):
        return 'IDENTITY'
    if col in ('wbc_com_x', 'wbc_com_y', 'wbc_com_z', 'com_reliability_score'):
        return 'WBCoM'
    for suf in ('__lin_rel_px','__lin_rel_py','__lin_rel_pz',
                '__lin_vel_rel_x','__lin_vel_rel_y','__lin_vel_rel_z','__lin_vel_rel_mag',
                '__lin_acc_rel_x','__lin_acc_rel_y','__lin_acc_rel_z','__lin_acc_rel_mag'):
        if col.endswith(suf): return 'LIN_KINE'
    if '__euler_' in col: return 'EULER'
    if '__is_artifact' in col or '__is_hampel' in col: return 'FLAGS'
    if '__zeroed_rel_q' in col or '__raw_rel_q' in col: return 'QUAT'
    if '__zeroed_rel_omega' in col or '__zeroed_rel_alpha' in col: return 'OMEGA_ALPHA'
    if '__zeroed_rel_rotvec' in col or '__zeroed_rel_rotmag' in col: return 'ROTVEC'
    return 'OTHER'

print('='*70)
print('COLUMN COUNT BREAKDOWN BY FAMILY (post-T004, includes +4 label cols)')
print('='*70)

families = ['IDENTITY','QUAT','ROTVEC','OMEGA_ALPHA','LIN_KINE','EULER','FLAGS','WBCoM','OTHER']
header = f'{"Family":<18}' + ''.join(f'  {l:<10}' for l in SESSIONS.keys())
print(header)
print('-'*70)

for fam in families:
    row = f'{fam:<18}'
    for label, df in dfs.items():
        cnt = sum(1 for c in df.columns if classify(c) == fam)
        row += f'  {cnt:<10}'
    print(row)

row = f'{"TOTAL":<18}'
for label, df in dfs.items():
    row += f'  {len(df.columns):<10}'
print('-'*70)
print(row)

# Now diff: what specific joints drive the LIN_KINE difference?
print()
print('='*70)
print('LIN_KINE JOINTS PRESENT PER SESSION')
print('='*70)

def lin_joints(df):
    return sorted(set(c.split('__')[0] for c in df.columns if c.endswith('__lin_rel_px')))

all_lin_joints = sorted(set(j for df in dfs.values() for j in lin_joints(df)))
header2 = f'{"Joint":<22}' + ''.join(f'  {l:<8}' for l in SESSIONS.keys())
print(header2)
print('-'*70)
for j in all_lin_joints:
    row = f'{j:<22}'
    for label, df in dfs.items():
        present = j in lin_joints(df)
        row += f'  {"Y" if present else "-":<8}'
    print(row)

# Summary: how many lin joints per session
print('-'*70)
row = f'{"lin_joints_count":<22}'
for label, df in dfs.items():
    row += f'  {len(lin_joints(df)):<8}'
print(row)

# Euler joints check
print()
print('='*70)
print('EULER JOINTS PRESENT PER SESSION')
print('='*70)
def euler_joints(df):
    return sorted(set(c.split('__')[0] for c in df.columns if '__euler_x' in c))
all_euler = sorted(set(j for df in dfs.values() for j in euler_joints(df)))
print(f'Euler joint counts: ' + ', '.join(f'{l}={len(euler_joints(df))}' for l, df in dfs.items()))

# Flags check
print()
print('FLAGS per session (is_artifact + is_hampel counts):')
for label, df in dfs.items():
    art = sum(1 for c in df.columns if '__is_artifact' in c)
    hamp = sum(1 for c in df.columns if '__is_hampel' in c)
    print(f'  {label}: is_artifact={art}, is_hampel={hamp}')
