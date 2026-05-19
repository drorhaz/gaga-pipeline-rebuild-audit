"""Ticket 004 smoke-test verification."""
import pandas as pd
import pyarrow.parquet as pq

sess = '651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002'
path = f'derivatives/step_06_kinematics/{sess}__kinematics_master.parquet'

df = pd.read_parquet(path)
print('=== SMOKE TEST: Ticket 004 session labels ===')
print(f'Shape: {df.shape}')
print()

label_cols = ('subject_id', 'timepoint', 'piece', 'rep')
print('T1 - 4 label columns present:')
for col in label_cols:
    present = col in df.columns
    if present:
        val = df[col].iloc[0]
        dtype = str(df[col].dtype)
        n_unique = int(df[col].nunique())
        print(f'  {col}: PRESENT  dtype={dtype}  value={repr(val)}  n_unique={n_unique}')
    else:
        print(f'  {col}: MISSING  *** FAIL ***')

print()
print('T2 - all label dtypes are object (string):')
present_labels = [c for c in label_cols if c in df.columns]
all_obj = all(df[c].dtype == 'object' for c in present_labels)
print(f'  all_object_dtype: {all_obj}  (PASS={all_obj})')

print()
print('T3 - session-constant (1 unique value each):')
all_const = all(df[c].nunique() == 1 for c in present_labels)
print(f'  all_constant: {all_const}  (PASS={all_const})')
for col in present_labels:
    print(f'    {col}: {df[col].unique().tolist()}')

print()
print('T4/T5 - PyArrow metadata for ref_is_fallback:')
table = pq.read_table(path)
meta = table.schema.metadata or {}
key = b'ref_is_fallback'
present_meta = key in meta
val_meta = meta[key].decode('utf-8') if present_meta else 'NOT FOUND'
print(f'  ref_is_fallback present: {present_meta}  (PASS={present_meta})')
print(f'  ref_is_fallback value:   {val_meta}')

print()
print('T7 - column count:')
pre_t004_col_count = 773  # this session had 773 before T004
expected = pre_t004_col_count + 4
print(f'  pre-T004 cols: {pre_t004_col_count}')
print(f'  expected post-T004: {expected}')
print(f'  actual cols: {len(df.columns)}')
print(f'  PASS: {len(df.columns) == expected}')
