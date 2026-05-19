"""Deep dive: exactly which LIN_KINE suffixes are present per session."""
import pandas as pd

SESSIONS = {
    '651_T1': '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002',
    '651_T2': '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM',
    '671_T1': '671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002',
    '671_T3': '671_T3_P2_R1_Take 2026-02-03 08.05.01 PM_001',
}

dfs = {label: pd.read_parquet(f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet')
       for label, sess in SESSIONS.items()}

LIN_SUFFIXES = [
    'lin_rel_px', 'lin_rel_py', 'lin_rel_pz',
    'lin_vel_rel_x', 'lin_vel_rel_y', 'lin_vel_rel_z', 'lin_vel_rel_mag',
    'lin_acc_rel_x', 'lin_acc_rel_y', 'lin_acc_rel_z', 'lin_acc_rel_mag',
]

# Count which suffixes are actually present across sessions
print('=== LIN_KINE suffix presence per session ===')
print(f'{"Suffix":<25}' + ''.join(f'  {l:<8}' for l in SESSIONS))
print('-' * 65)
all_lin_cols = {label: set(c for c in df.columns
                            if any(c.endswith('__'+s) for s in LIN_SUFFIXES))
                for label, df in dfs.items()}
for suf in LIN_SUFFIXES:
    row = f'{suf:<25}'
    for label, df in dfs.items():
        cnt = sum(1 for c in df.columns if c.endswith('__'+suf))
        row += f'  {cnt:<8}'
    print(row)
print('-' * 65)
totals = f'{"TOTAL LIN_KINE cols":<25}'
for label, df in dfs.items():
    cnt = sum(1 for c in df.columns if any(c.endswith('__'+s) for s in LIN_SUFFIXES))
    totals += f'  {cnt:<8}'
print(totals)

# How many joints per suffix per session
print()
print('=== Count of joints per LIN_KINE suffix ===')
print('(Each suffix should appear once per qualifying joint)')
print()
for label, df in dfs.items():
    suf_counts = {}
    for suf in LIN_SUFFIXES:
        suf_counts[suf] = sum(1 for c in df.columns if c.endswith('__'+suf))
    total = sum(suf_counts.values())
    # Which suffix has fewer joints?
    expected_19 = {s: 19 for s in LIN_SUFFIXES}
    diffs = {s: suf_counts[s] - 19 for s in LIN_SUFFIXES if suf_counts[s] != 19}
    print(f'{label}: total={total}  joints-per-suffix={set(suf_counts.values())}')
    if diffs:
        for s, d in diffs.items():
            print(f'  {s}: {suf_counts[s]} joints (expected 19, diff={d:+d})')
