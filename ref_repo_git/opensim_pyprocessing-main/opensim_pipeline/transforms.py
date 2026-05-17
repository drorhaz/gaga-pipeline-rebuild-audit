"""Coordinate and table transformation utilities for OpenSim data tables."""

from __future__ import annotations

import numpy as np
import opensim as osim


def transform_data_table(table: osim.TimeSeriesTableVec3, T: np.ndarray) -> None:
    """Apply a 4x4 homogeneous transformation matrix to a TimeSeriesTableVec3.

    Transforms every Vec3 entry in-place using the inverse of T.

    Parameters
    ----------
    table : osim.TimeSeriesTableVec3
        Table to transform in-place.
    T : np.ndarray
        4x4 homogeneous transformation matrix.
    """
    T_inv = np.linalg.inv(T)
    for i in range(table.getNumRows()):
        row = table.getRowAtIndex(i)
        for j in range(row.size()):
            v = row[j]
            p = np.array([v[0], v[1], v[2], 0])
            p_new = T_inv @ p
            row[j] = osim.Vec3(p_new[0], p_new[1], p_new[2])
        table.setRowAtIndex(i, row)


def counting_nans(table: osim.TimeSeriesTableVec3) -> dict[str, int]:
    """Count NaN values in each column of a TimeSeriesTableVec3.

    Parameters
    ----------
    table : osim.TimeSeriesTableVec3
        Table to inspect.

    Returns
    -------
    dict[str, int]
        Column label -> number of rows containing NaN for that column.
    """
    nan_counts = {
        table.getColumnLabel(j): 0 for j in range(table.getNumColumns())
    }
    for i in range(table.getNumRows()):
        row = table.getRowAtIndex(i)
        for j in range(row.size()):
            vec = row[j]
            if (
                np.isnan(vec.get(0))
                or np.isnan(vec.get(1))
                or np.isnan(vec.get(2))
            ):
                nan_counts[table.getColumnLabel(j)] += 1
    return nan_counts


def scale_table(
    table: osim.TimeSeriesTableVec3, scale_factor: float
) -> None:
    """Scale all Vec3 values in a table by a constant factor.

    Parameters
    ----------
    table : osim.TimeSeriesTableVec3
        Table to scale in-place.
    scale_factor : float
        Multiplicative factor.
    """
    for i in range(table.getNumRows()):
        row = table.getRowAtIndex(i)
        for j in range(row.size()):
            row[j] = row[j] * scale_factor
        table.setRowAtIndex(i, row)
