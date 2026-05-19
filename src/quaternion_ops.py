import numpy as np
from scipy.spatial.transform import Rotation as R

def quat_normalize(q, eps=1e-12):
    """Normalizes quaternions to unit length."""
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    n = np.maximum(n, eps)
    return q / n

def quat_inv(q):
    """Inverse/Conjugate of quaternion (x,y,z,w)."""
    q_inv = q.copy()
    q_inv[..., :3] *= -1.0
    return q_inv

def quat_mul(q1, q2):
    """Multiplies two arrays of quaternions using SciPy."""
    r1 = R.from_quat(q1)
    r2 = R.from_quat(q2)
    return (r1 * r2).as_quat()

def quat_shortest(q):
    """Enforces shortest path (w >= 0)."""
    q_out = q.copy()
    neg_w = q_out[..., 3] < 0
    q_out[neg_w] *= -1.0
    return q_out

def quat_enforce_continuity(q):
    """Flips quaternions to minimize temporal jumps."""
    q_out = q.copy()
    if q_out.ndim == 2:
        for t in range(1, q_out.shape[0]):
            if np.dot(q_out[t-1], q_out[t]) < 0:
                q_out[t] *= -1.0
    elif q_out.ndim == 3:
        T, J, _ = q_out.shape
        for j in range(J):
            for t in range(1, T):
                if np.dot(q_out[t-1, j], q_out[t, j]) < 0:
                    q_out[t, j] *= -1.0
    return q_out