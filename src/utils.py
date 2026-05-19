import os
import json
import hashlib
import numpy as np
from datetime import datetime

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def ensure_dirs(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def sha256_file(path, block_size=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(block_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def fingerprint_file(path):
    if path is None:
        return None
    exists = os.path.exists(path)
    fp = {"path": path, "exists": exists}
    if exists:
        st = os.stat(path)
        fp.update({
            "size": st.st_size,
            "mtime": st.st_mtime,
            "sha256": sha256_file(path)
        })
    return fp

def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def normalize_joint_name(name: str) -> str:
    return str(name).split(":")[-1].strip()


def discover_sessions_from_parquet(deriv_root: str) -> list:
    """
    Ticket 013: Discover session IDs by scanning
    `derivatives/step_06_kinematics/*__kinematics_master.parquet`.

    This gives the ground-truth session count from the actual
    kinematics output files, independent of the JSON-sidecar-based
    discovery used by load_all_runs() in utils_nb07.py.

    Returns a sorted list of run_id strings (without the parquet suffix).
    """
    import pathlib
    p = pathlib.Path(deriv_root) / "step_06_kinematics"
    if not p.exists():
        return []
    return sorted(
        f.stem.replace("__kinematics_master", "")
        for f in p.glob("*__kinematics_master.parquet")
    )