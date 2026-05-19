"""UD-006 investigation: parse label components from current RUN_IDs."""
import os, re

parq_dir = 'derivatives/step_06_kinematics'
sessions = sorted([f.replace('__kinematics_master.parquet','')
                   for f in os.listdir(parq_dir) if f.endswith('.parquet')])

print('=== Current RUN_IDs (14 sessions) ===')
for s in sessions:
    print(' ', s)

print()
# Parse: e.g. "651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002"
# Groups: (subject) _ (timepoint) _ (piece) _ (rep)
pattern = re.compile(r'^(\d+)_(T\d+)_(P\d+)_(R\d+)')
print('=== Parsed label components from RUN_ID stem ===')
print('  Session                                   subject  tp    piece  rep')
print('  ' + '-'*75)
for s in sessions:
    m = pattern.match(s)
    if m:
        print(f'  {s[:42]:<44} {m.group(1):<9}{m.group(2):<6}{m.group(3):<7}{m.group(4):<5}')
    else:
        print(f'  {s[:42]:<44} [pattern not matched]')
