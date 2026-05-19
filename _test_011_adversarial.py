"""Ticket 011 adversarial synthetic tests — Hampel OR mask propagation."""
import sys, os, numpy as np, pandas as pd
sys.path.insert(0, os.path.join('.', 'src'))

from filtering import apply_hampel_filter, apply_signal_cleaning_pipeline

failures = []


# ===========================================================================
# A1: apply_hampel_filter marks correct frames as True
# ===========================================================================
print('=== A1: apply_hampel_filter returns correct per-frame mask ===')
# Build a signal with a known spike at frame 20 (1000 mm/s vs baseline ~1 mm/s)
N = 200
signal = np.sin(np.linspace(0, 4*np.pi, N)) * 1.0  # baseline ~1 amplitude
signal[20] = 500.0   # spike at frame 20
signal[21] = -500.0  # another spike

filtered, mask = apply_hampel_filter(signal, window_size=5, n_sigma=3.0)

n_true = int(np.sum(mask))
# Frames 20 and 21 should be flagged, others should be False
frame20_flagged = bool(mask[20])
frame21_flagged = bool(mask[21])
mid_clean = not bool(mask[100])  # far from spikes should be clean
print(f'  n_flagged frames: {n_true}')
print(f'  frame 20 flagged: {frame20_flagged}  (expected True)')
print(f'  frame 21 flagged: {frame21_flagged}  (expected True)')
print(f'  frame 100 clean:  {mid_clean}  (expected True)')
a1 = frame20_flagged and frame21_flagged and mid_clean and n_true >= 2
print('  RESULT:', 'PASS' if a1 else 'FAIL')
if not a1: failures.append('A1')


# ===========================================================================
# A2: OR accumulation across two columns yields union
# ===========================================================================
print()
print('=== A2: OR mask is union of all column masks ===')
# Col A: spike at frame 10
# Col B: spike at frame 50
N = 200
fs = 120.0
time_s = np.arange(N) / fs
df_synth = pd.DataFrame({'time_s': time_s})
sigA = np.ones(N) * 5.0
sigA[10] = 9999.0   # huge spike in col A at frame 10
sigB = np.ones(N) * 5.0
sigB[50] = 9999.0   # huge spike in col B at frame 50
df_synth['JointA__px'] = sigA
df_synth['JointB__px'] = sigB

_, pm = apply_signal_cleaning_pipeline(
    df_synth,
    fs=fs,
    pos_cols=['JointA__px', 'JointB__px'],
    velocity_limit=1e9,       # disable velocity gate
    zscore_threshold=1e9,     # disable zscore gate
    hampel_window=5,
    hampel_n_sigma=3.0,
    winter_fmin=1.0,
    winter_fmax=20.0,
    per_joint_winter=False,
    stage1_interpolation_method='linear',
)

or_mask = pm.get('hampel_or_frame_mask', None)
a2_exists = or_mask is not None
a2_len = (len(or_mask) == N) if a2_exists else False
# Frames 10 and 50 should be True; frame 25 should be False
a2_frame10 = bool(or_mask[10]) if a2_exists else False
a2_frame50 = bool(or_mask[50]) if a2_exists else False
a2_frame25 = (not bool(or_mask[25])) if a2_exists else False
print(f'  or_mask exists: {a2_exists}, len={len(or_mask) if a2_exists else None}')
print(f'  frame 10 (ColA spike): {bool(or_mask[10]) if a2_exists else None}  (expected True)')
print(f'  frame 50 (ColB spike): {bool(or_mask[50]) if a2_exists else None}  (expected True)')
print(f'  frame 25 (no spike):   {bool(or_mask[25]) if a2_exists else None}  (expected False)')
a2 = a2_exists and a2_len and a2_frame10 and a2_frame50 and a2_frame25
print('  RESULT:', 'PASS' if a2 else 'FAIL')
if not a2: failures.append('A2')


# ===========================================================================
# A3: Empty / clean signal → OR mask all-False
# ===========================================================================
print()
print('=== A3: Clean signal -> OR mask all-False ===')
df_clean = pd.DataFrame({'time_s': time_s, 'JointC__px': np.sin(time_s) * 2.0})
_, pm_clean = apply_signal_cleaning_pipeline(
    df_clean, fs=fs, pos_cols=['JointC__px'],
    velocity_limit=1e9, zscore_threshold=1e9,
    hampel_window=5, hampel_n_sigma=3.0,
    winter_fmin=1.0, winter_fmax=20.0, per_joint_winter=False,
    stage1_interpolation_method='linear',
)
or_mask_clean = pm_clean.get('hampel_or_frame_mask', None)
a3 = or_mask_clean is not None and not np.any(or_mask_clean)
print(f'  all-False: {not np.any(or_mask_clean) if or_mask_clean is not None else None}  (expected True)')
print('  RESULT:', 'PASS' if a3 else 'FAIL')
if not a3: failures.append('A3')


# ===========================================================================
# A4: Dev Set sanity — filtering_summary confirms Hampel activity; mask must be non-zero
# ===========================================================================
print()
print('=== A4: Dev Set consistency — Hampel activity confirmed in filtering_summary ===')
import json
for sess, exp_nonzero in [
    ('671_T1_P2_R1_Take 2026-01-06 03.57.12 PM_002', True),
    ('651_T1_P1_R1_Take 2026-01-15 04.35.25 PM_002', True),
]:
    fs_path = f'derivatives/step_04_filtering/{sess}__filtering_summary.json'
    mask_path = f'derivatives/step_04_filtering/{sess}__s04_hampel_or_mask.npy'
    # Check filtering_summary for Hampel activity
    with open(fs_path) as f:
        fs_data = json.load(f)
    total_h = fs_data.get('filter_params', {}).get('total_hampel_outliers', 0)
    # Note: mask file may not exist yet if pipeline hasn't re-run
    mask_exists = os.path.exists(mask_path)
    print(f'  {sess[:50]}: filtering_summary total_hampel_outliers={total_h}, mask_file_exists={mask_exists}')
    # We can't verify mask values until after the pipeline runs; this is a structural check
    a4 = (total_h > 0)  # Confirmed activity must exist
    if not a4:
        failures.append(f'A4: {sess[:30]} reports zero Hampel activity unexpectedly')

print()
print('=' * 70)
if failures:
    print(f'FAILURES: {failures}')
    sys.exit(1)
else:
    print('ALL ADVERSARIAL SYNTHETIC TESTS PASS')
print('=' * 70)
