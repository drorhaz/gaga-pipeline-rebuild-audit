import json
d = json.load(open(r'derivatives/step_04_filtering/671_T1_P1_R1_Take 2026-01-06 03.57.12 PM_001__filtering_summary.json'))
fp = d.get('filter_params', {})
print('filter_params keys:')
print(json.dumps(list(fp.keys()), indent=2))

pc = fp.get('per_column', {})
if pc:
    k = list(pc.keys())[0]
    print(f'\nper_column sample ({k}):')
    print(json.dumps(list(pc[k].keys()), indent=2))
    print(f'\nstage1_unreliable_gaps: {pc[k].get("stage1_unreliable_gaps", "N/A")}')
    print(f'stage1_max_gap_frames: {pc[k].get("stage1_max_gap_frames", "N/A")}')
    print(f'marker_region: {pc[k].get("marker_region", "N/A")}')
    print(f'stage3_winter_cutoff: {pc[k].get("stage3_winter_cutoff", "N/A")}')

# Check for gap guard at top level
print(f'\ntotal_artifact_frames: {fp.get("total_artifact_frames", "N/A")}')
print(f'stage1_max_interp_limit_frames: {fp.get("stage1_max_interp_limit_frames", "N/A")}')
print(f'stage1_gap_guard: {json.dumps(fp.get("stage1_gap_guard", "N/A"), indent=2)}')
