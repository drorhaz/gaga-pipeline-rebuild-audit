"""Show full T007b diagnostic output for audit report."""
import json

sess = '651_T2_P1_R1_Take 2026-01-26 05.24.12 PM'
with open(f'derivatives/step_06_kinematics/{sess}__validation_report.json') as f:
    v = json.load(f)
qd = v['quaternion_diagnostics']
lkd = v['lin_kine_diagnostics']

print('=== quaternion_diagnostics (651_T2_P1_R1) ===')
print(f'  rotation_method_verdict:           {qd["rotation_method_verdict"]}')
print(f'  total_hemisphere_flips_corrected:  {qd["total_hemisphere_flips_corrected"]}')
print(f'  n_joints_above_renorm_threshold:   {qd["n_joints_above_renorm_threshold"]}')
print(f'  renorm_threshold_pct:              {qd["renorm_threshold_pct"]}')

gqi = qd.get('global_quat_integrity', {})
print(f'\n  global_quat_integrity (sample joint Hips):')
hips = gqi.get('Hips', {})
for k, val in hips.items():
    print(f'      {k}: {val}')

rqd = qd.get('relative_quat_drift', {})
print(f'\n  relative_quat_drift (sample joint Hips):')
hips_r = rqd.get('Hips', {})
for k, val in hips_r.items():
    print(f'      {k}: {val}')

print(f'\n=== lin_kine_diagnostics ===')
print(f'  gate:                          {lkd["gate"]}')
print(f'  n_joints_with_dropped_axes:    {lkd["n_joints_with_dropped_axes"]}')
print(f'  total_axes_silently_dropped:   {lkd["total_axes_silently_dropped"]}')
print(f'  dropped_axes:')
for j, axes in lkd['dropped_axes'].items():
    for a, info in axes.items():
        print(f'    {j} axis={a}: nan_count={info["nan_count"]}, nan_fraction={info["nan_fraction"]:.6f}')

print(f'\n=== filtering_summary.json Hampel summary ===')
with open(f'derivatives/step_04_filtering/{sess}__filtering_summary.json') as f:
    filt = json.load(f)
fp = filt['filter_params']
print(f'  hampel_max_fraction_any_joint: {fp["hampel_max_fraction_any_joint"]}')
print(f'  hampel_joints_above_threshold: {fp["hampel_joints_above_threshold"]}')
print(f'  hampel_threshold_fraction:     {fp["hampel_threshold_fraction"]}')
print(f'  hampel_modification_fraction_per_joint (first 5):')
hmf = fp['hampel_modification_fraction_per_joint']
for k, val in list(hmf.items())[:5]:
    print(f'    {k}: {val}')
