import json

with open('notebooks/04_filtering.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

cell = nb['cells'][5]
src = ''.join(cell['source'])
out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
print('=== Cell 5 full ===')
print(out)
