import json
with open('notebooks/06_ultimate_kinematics.ipynb', encoding='utf-8') as f:
    nb = json.load(f)
cell = nb['cells'][20]
for i, line in enumerate(cell['source']):
    if 'Ticket 004' in line or 'NaN Integrity Guard' in line or 'WARNING: ref_is_fallback' in line:
        print(f'Line {i}: {repr(line[:100])}')
