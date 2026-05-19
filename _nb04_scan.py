import json

with open('notebooks/04_filtering.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
print(f'Total cells: {len(nb["cells"])}')
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if any(kw in src for kw in ['apply_signal_cleaning_pipeline', 'apply_hampel', 'hampel_mask',
                                     'to_parquet', 'pipeline_metadata', 'DERIV_04']):
            out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
            print(f'=== Cell {i} (first 1200) ===')
            print(out[:1200])
            print('---')
