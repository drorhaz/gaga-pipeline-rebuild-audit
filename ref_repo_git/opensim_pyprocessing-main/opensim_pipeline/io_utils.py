"""Shared I/O utilities for reading OpenSim files and parsing TSV configs."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np


def read_sto_file(filepath: str | Path) -> dict[str, np.ndarray]:
    """Read an OpenSim .sto/.mot file into a dict of numpy arrays.

    Parameters
    ----------
    filepath : str or Path
        Path to the .sto or .mot file.

    Returns
    -------
    dict[str, np.ndarray]
        Column name -> array of values. Includes a 'time' key.
    """
    data: dict[str, list[float]] = {}
    with open(filepath, "r") as f:
        for line in f:
            if line.strip() == "endheader":
                break
        header_line = f.readline().strip()
        columns = header_line.split("\t")
        for col in columns:
            data[col] = []
        for line in f:
            values = line.strip().split("\t")
            for col, val in zip(columns, values):
                data[col].append(float(val))

    return {col: np.array(vals) for col, vals in data.items()}


def fix_mot_header(mot_file: str | Path) -> None:
    """Rewrite a .mot/.sto file header to the clean OpenSim format.

    The C3D adapter and STOFileAdapter dump metadata into the header which
    corrupts the Storage data source name. This function rewrites the header
    with: filename, version=1, nRows, nColumns, inDegrees=yes, endheader.

    Parameters
    ----------
    mot_file : str or Path
        Path to the .mot or .sto file to fix in-place.
    """
    mot_file = Path(mot_file)
    with open(mot_file, "r") as f:
        lines = f.readlines()

    header_end = next(i for i, l in enumerate(lines) if l.strip() == "endheader")
    after_header = lines[header_end + 1 :]

    # Find the column labels line (starts with "time\t")
    col_idx = next(i for i, l in enumerate(after_header) if l.startswith("time\t"))
    col_header = after_header[col_idx]
    data_lines = after_header[col_idx + 1 :]
    n_cols = len(col_header.strip().split("\t"))

    with open(mot_file, "w") as f:
        f.write(f"{mot_file.name}\n")
        f.write("version=1\n")
        f.write(f"nRows={len(data_lines)}\n")
        f.write(f"nColumns={n_cols}\n")
        f.write("inDegrees=yes\n")
        f.write("endheader\n")
        f.write(col_header)
        f.writelines(data_lines)


def parse_ik_marker_weights_tsv(
    tsv_path: str | Path,
) -> list[dict[str, str | float | bool]]:
    """Parse IK marker weights from a TSV file.

    Parameters
    ----------
    tsv_path : str or Path
        Path to the TSV file with columns: marker, weight, apply.

    Returns
    -------
    list[dict]
        Each dict has 'marker' (str), 'weight' (float), 'apply' (bool).
    """
    markers = []
    with open(tsv_path, "r") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            markers.append(
                {
                    "marker": row["marker"],
                    "weight": float(row["weight"]),
                    "apply": row.get("apply", "true").lower() == "true",
                }
            )
    return markers
