"""
Ticket 009 — adversarial synthetic tests for compute_artifact_segment_stats().
"""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join('.', 'src'))
from preprocessing import compute_artifact_segment_stats

failures = []

def _check(name, stats, **expected):
    actual = {k: stats.get(k) for k in expected}
    ok = all(actual[k] == v for k, v in expected.items())
    print(f'{name}: {"PASS" if ok else "FAIL"}')
    for k, v in expected.items():
        got = actual[k]
        match = '==' if got == v else '!='
        print(f'    {k}: expected={v}  got={got}  ({match})')
    if not ok:
        failures.append(name)
    print()

print('=== A1: NaN runs of known lengths [2, 7, 12] in single column ===')
df = pd.DataFrame({'Hips__px': [1.0]*100})
df.loc[10:11, 'Hips__px'] = np.nan       # run of 2 (frames 10..11)
df.loc[30:36, 'Hips__px'] = np.nan       # run of 7
df.loc[60:71, 'Hips__px'] = np.nan       # run of 12
s = compute_artifact_segment_stats(df)
_check('A1',
    s,
    n_artifact_segments=3,
    max_artifact_segment_frames=12,
    mean_artifact_segment_frames=7.0,
    n_artifact_segments_above_5_frames=2,
    n_artifact_segments_above_10_frames=1,
    n_columns_scanned=1,
)

print('=== A2: Multi-column aggregation (2 NaN cols, total 5 segments) ===')
df = pd.DataFrame({'Hips__px': [1.0]*50, 'Hips__py': [1.0]*50, 'Hips__pz': [1.0]*50})
df.loc[0:0, 'Hips__px'] = np.nan         # 1 segment of length 1
df.loc[10:14, 'Hips__px'] = np.nan       # 1 segment of length 5
df.loc[20:30, 'Hips__py'] = np.nan       # 1 segment of length 11
df.loc[40:42, 'Hips__py'] = np.nan       # 1 segment of length 3
df.loc[5:9, 'Hips__pz'] = np.nan         # 1 segment of length 5
s = compute_artifact_segment_stats(df)
# Aggregated lengths: [1, 5, 11, 3, 5] = total 5 segments
_check('A2',
    s,
    n_artifact_segments=5,
    max_artifact_segment_frames=11,
    mean_artifact_segment_frames=5.0,
    n_artifact_segments_above_5_frames=1,   # only the 11
    n_artifact_segments_above_10_frames=1,  # only the 11
    n_columns_scanned=3,
)

print('=== A3: Threshold boundary — runs of exactly 5 and 10 (strict > comparison) ===')
df = pd.DataFrame({'Hips__px': [1.0]*100})
df.loc[10:14, 'Hips__px'] = np.nan       # length 5 (NOT above 5)
df.loc[30:39, 'Hips__px'] = np.nan       # length 10 (NOT above 10)
df.loc[60:65, 'Hips__px'] = np.nan       # length 6 (above 5, not above 10)
df.loc[80:90, 'Hips__px'] = np.nan       # length 11 (above 10)
s = compute_artifact_segment_stats(df)
# Lengths: [5, 10, 6, 11]
# Above 5: 10, 6, 11 -> 3
# Above 10: 11 -> 1
_check('A3',
    s,
    n_artifact_segments=4,
    max_artifact_segment_frames=11,
    n_artifact_segments_above_5_frames=3,
    n_artifact_segments_above_10_frames=1,
)

print('=== A4: Empty/clean DataFrame ===')
df = pd.DataFrame({'Hips__px': [1.0]*100, 'Hips__py': [2.0]*100, 'Hips__pz': [3.0]*100})
s = compute_artifact_segment_stats(df)
_check('A4',
    s,
    n_artifact_segments=0,
    max_artifact_segment_frames=0,
    mean_artifact_segment_frames=0.0,
    n_artifact_segments_above_5_frames=0,
    n_artifact_segments_above_10_frames=0,
    n_columns_scanned=3,
)

print('=== A5: Single isolated NaN frame ===')
df = pd.DataFrame({'Hips__px': [1.0]*100})
df.loc[50:50, 'Hips__px'] = np.nan
s = compute_artifact_segment_stats(df)
_check('A5',
    s,
    n_artifact_segments=1,
    max_artifact_segment_frames=1,
    mean_artifact_segment_frames=1.0,
    n_artifact_segments_above_5_frames=0,
    n_artifact_segments_above_10_frames=0,
)

print('=== A6: NaN at very start and end (boundary cases) ===')
df = pd.DataFrame({'Hips__px': [1.0]*100})
df.loc[0:2, 'Hips__px'] = np.nan         # at start, length 3
df.loc[96:99, 'Hips__px'] = np.nan       # at end, length 4
s = compute_artifact_segment_stats(df)
_check('A6',
    s,
    n_artifact_segments=2,
    max_artifact_segment_frames=4,
    mean_artifact_segment_frames=3.5,
    n_artifact_segments_above_5_frames=0,
    n_artifact_segments_above_10_frames=0,
)

print('=== A7: Filter by suffix — only px/py/pz, not qx/qy/qz/qw ===')
df = pd.DataFrame({
    'Hips__px': [1.0]*50,
    'Hips__qx': [1.0]*50,    # quaternion, should be IGNORED
})
df.loc[5:10, 'Hips__px'] = np.nan        # length 6 — should be counted
df.loc[20:30, 'Hips__qx'] = np.nan       # length 11 — should NOT be counted
s = compute_artifact_segment_stats(df, axis_suffixes=('__px', '__py', '__pz'))
_check('A7',
    s,
    n_artifact_segments=1,
    max_artifact_segment_frames=6,
    n_columns_scanned=1,                  # only Hips__px matched suffix
)

print('=== A8: Adjacent NaN regions separated by 1 valid frame — should be 2 segments ===')
df = pd.DataFrame({'Hips__px': [1.0]*100})
df.loc[10:14, 'Hips__px'] = np.nan       # length 5
# frame 15 is valid (1.0)
df.loc[16:20, 'Hips__px'] = np.nan       # length 5
s = compute_artifact_segment_stats(df)
_check('A8',
    s,
    n_artifact_segments=2,                # NOT merged
    max_artifact_segment_frames=5,
    mean_artifact_segment_frames=5.0,
)

print('=== A9: All-NaN column ===')
df = pd.DataFrame({'Hips__px': [np.nan]*100})
s = compute_artifact_segment_stats(df)
_check('A9',
    s,
    n_artifact_segments=1,
    max_artifact_segment_frames=100,
    mean_artifact_segment_frames=100.0,
    n_artifact_segments_above_10_frames=1,
)

print('=' * 65)
if failures:
    print(f'FAILURES: {len(failures)}')
    for f in failures:
        print(f'  - {f}')
    sys.exit(1)
else:
    print('ALL 9 ADVERSARIAL SYNTHETIC TESTS PASS')
print('=' * 65)
