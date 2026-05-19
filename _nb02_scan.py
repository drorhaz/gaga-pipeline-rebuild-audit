import json
with open('notebooks/02_preprocess.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
print(f'Total cells: {len(nb["cells"])}')
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if any(kw in src for kw in ['interpolation_log', 'pchip_single_pass', 'position_method',
                                     'detect_and_mask', 'is_artifact', 'artifact_mask',
                                     'POS_RESAMPLE_METHOD', 'interp_summary']):
            out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
            print(f'=== Cell {i} (full) ===')
            print(out[:2000])
            print('---')
