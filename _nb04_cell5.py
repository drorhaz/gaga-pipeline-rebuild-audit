import json

with open('notebooks/04_filtering.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

# Get cells 5, 6, 7 (the filtering pipeline call and saves)
for i in [5, 6, 7, 8]:
    if i < len(nb['cells']):
        cell = nb['cells'][i]
        if cell['cell_type'] == 'code':
            src = ''.join(cell['source'])
            out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
            print(f'=== Cell {i} (first 2000) ===')
            print(out[:2000])
            print('---')
