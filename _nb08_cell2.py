import json

with open('notebooks/08_engineering_physical_audit.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

# Show cells 1-4 to understand how runs are loaded and whether any hardcoded count exists
for i in [1, 2, 3, 4]:
    cell = nb['cells'][i]
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
        print(f'=== Cell {i} (full) ===')
        print(out[:2000])
        print('---')
