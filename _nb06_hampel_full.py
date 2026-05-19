import json

with open('notebooks/06_ultimate_kinematics.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

# Get full Cell 12 (artifact flags cell)
cell = nb['cells'][12]
src = ''.join(cell['source'])
out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
print('=== Cell 12 full ===')
print(out)
