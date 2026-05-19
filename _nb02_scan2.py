import json
with open('notebooks/02_preprocess.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
for i in [2, 3, 4, 5, 6, 7, 8]:
    if i < len(nb['cells']):
        cell = nb['cells'][i]
        if cell['cell_type'] == 'code':
            src = ''.join(cell['source'])
            out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
            print(f'=== Cell {i} (first 1200) ===')
            print(out[:1200])
            print('---')
