import json

with open('notebooks/06_ultimate_kinematics.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

# Find cells that write is_hampel_outlier
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if 'is_hampel_outlier' in src:
            out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
            print(f'=== Cell {i} (first 1500 chars) ===')
            print(out[:1500])
            print('---')
