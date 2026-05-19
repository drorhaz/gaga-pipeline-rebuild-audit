import json

with open('notebooks/08_engineering_physical_audit.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

cell = nb['cells'][5]
src = ''.join(cell['source'])
out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
print(f'Cell 5 length: {len(src)} chars')
print(out)
