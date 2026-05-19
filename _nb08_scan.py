import json

with open('notebooks/08_engineering_physical_audit.ipynb', encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']
print(f'Total cells: {len(cells)}')

KEYWORDS = ['n_sessions', 'N_SESSIONS', 'session_count', 'num_sessions',
            'parquet', 'DERIV', 'kinematics', 'glob', 'subject_metadata',
            'assert', 'expected', 'len(', '== 3', '== 14', '== 15']

for i, cell in enumerate(cells):
    if cell['cell_type'] == 'code':
        src = ''.join(cell['source'])
        if any(kw in src for kw in KEYWORDS):
            out = ''.join(ch if ord(ch) < 128 else '?' for ch in src)
            print(f'--- Cell {i} (first 800) ---')
            print(out[:800])
            print()
