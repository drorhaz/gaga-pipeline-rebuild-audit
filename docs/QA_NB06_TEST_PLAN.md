# QA NB06 Validation — Rigorous Mathematical Test Plan

**Lead Biomechanics SDET · Step 1: Plan Only (No Code)**  
**Authority:** `docs/KINEMATIC_FEATURES_README.md`  
**Target:** Rewrite `notebooks/qa_nb06_validation.ipynb` so every test is a **deterministic mathematical proof** of the README logic, with exact toy data and tight floating-point assertions.

---

## 1. Test 1 — Quaternion Unrolling (Temporal Continuity)

**README (§3 A1):** *"The quaternion sequence is unrolled (temporal continuity enforced by flipping signs when `dot(q[t-1], q[t]) < 0` to prevent hemisphere jumps on SO(3))."*

### Toy Data
- **Input:** A (T, 4) quaternion array in SciPy `xyzw` convention:
  - Frame 0: unit quaternion **q0** = [0.1, 0.2, 0.3, 0.9] (normalized).
  - Frame 1: **q1** = **−q0** (same rotation, opposite hemisphere; `dot(q0, q1) < 0`).
  - Frame 2: **q2** = [0.15, 0.25, 0.35, 0.88] normalized, with `dot(q1_corrected, q2) > 0` so no flip.
- **Exact definition:** After normalizing, use `q1_input = -q0` so the unroll step must flip frame 1 to `+q0`.

### Expected Output
- **Frame 0:** unchanged: `q0`.
- **Frame 1:** must be flipped to `+q0` (i.e. `[0.1, 0.2, 0.3, 0.9]` after normalizing q0 to unit length).
- **Frame 2:** unchanged: `q2`.
- So expected array: `[normalize(q0), normalize(q0), normalize(q2)]` with frame 1 equal to frame 0.

### Assertion Strategy
- `np.testing.assert_allclose(actual[1], actual[0], atol=1e-10)` — frame 1 equals frame 0 after unroll.
- `np.testing.assert_allclose(actual[0], expected[0], atol=1e-10)` and same for row 2.
- **Tolerance:** `atol=1e-10, rtol=0` (exact up to double precision).

---

## 2. Test 2 — Quaternion Renormalization

**README (§3 A1):** *"After smoothing, quaternions are renormalized to unit length: `q = q / ||q||`."*

### Toy Data
- **Input:** Three non-unit quaternions with **known norms**:
  - Row 0: **q0** = [0.2, 0.4, 0.6, 1.2] → norm = √(0.04+0.16+0.36+1.44) = √2.0.
  - Row 1: **q1** = [0, 0, 0, 2.0] → norm = 2.0.
  - Row 2: **q2** = [0.3, 0.3, 0.3, 0.3] → norm = 0.6.
- **Exact definition:** Use these exact values so expected output is uniquely defined.

### Expected Output
- **Per-row:** `q_out[i] = q_in[i] / ||q_in[i]||`.
- **Norms:** `[1.0, 1.0, 1.0]`.
- **Components:** e.g. row 0 → [0.2/√2, 0.4/√2, 0.6/√2, 1.2/√2]; row 1 → [0, 0, 0, 1]; row 2 → [0.5, 0.5, 0.5, 0.5].

### Assertion Strategy
- `np.testing.assert_allclose(np.linalg.norm(actual, axis=1), [1.0, 1.0, 1.0], atol=1e-10)`.
- `np.testing.assert_allclose(actual, expected_components, atol=1e-10)` where expected_components are computed analytically from the formulas above.
- **Tolerance:** `atol=1e-10`.

---

## 3. Test 3 — Savitzky-Golay Window Length

**README (§9):** *"Window length = round(sg_window_sec * FS), forced odd, min 5"* and *"min 5"* and polynomial constraint.

### Toy Data (Inputs Only — Integer Function)
- **Case 1:** `fs=120`, `sg_window_sec=0.175`, `polyorder=3`.  
  - `round(120*0.175)=21`, odd → 21; `max(5, 21, polyorder+2=5)` → 21. **Expected: 21.**
- **Case 2:** `fs=100`, `sg_window_sec=0.2`, `polyorder=2`.  
  - `round(20)=20`, even → 21; `max(5, 21, 4)` → 21. **Expected: 21.**
- **Case 3:** `fs=50`, `sg_window_sec=0.1`, `polyorder=3`.  
  - `round(5)=5`, odd → 5; `max(5, 5, 5)` → 5. **Expected: 5** (not 7; current notebook expected value 7 is wrong).
- **Case 4 (edge):** `fs=10`, `sg_window_sec=0.2`, `polyorder=3`.  
  - `round(2)=2`, even → 3; `max(5, 3, 5)` → 5; odd. **Expected: 5.**

### Expected Output
- Single integer per case: 21, 21, 5, 5.

### Assertion Strategy
- `assert actual == expected` (exact integer equality). No floating point.

---

## 4. Test 4 — Hierarchical Quaternion (Relative Rotation)

**README (§3 A1):** *"For each joint with a parent: `q_rel = inv(q_parent) * q_child`."*

### Toy Data
- **Parent (single frame):** rotation of **30° around X**.  
  `q_parent = R.from_euler('x', 30, degrees=True).as_quat()` → exact xyzw.
- **Child (single frame):** rotation of **45° around X**.  
  `q_child = R.from_euler('x', 45, degrees=True).as_quat()`.
- **Exact formula:** `q_rel = (R.from_quat(q_parent).inv() * R.from_quat(q_child)).as_quat()` → rotation of **15° around X** (45° − 30° in same axis).

### Expected Output
- **q_rel** = quaternion for **15° around X** only:  
  `R.from_euler('x', 15, degrees=True).as_quat()`.

### Assertion Strategy
- Compute expected with SciPy: `expected = R.from_euler('x', 15, degrees=True).as_quat()`.
- `np.testing.assert_allclose(actual, expected, atol=1e-10)`.
- **Tolerance:** `atol=1e-10`.

---

## 5. Test 5 — Zeroed (T-Pose Normalized) Quaternion

**README (§3 A2):** *"q_zeroed(t) = inv(q_rel_ref) * q_raw_smooth(t)"* and *"When the subject stands in perfect T-pose, all zeroed quaternions equal the identity [0, 0, 0, 1]."*

### Toy Data
- **Reference (T-pose) quaternion:** `q_ref_rel = [0.1, 0.2, 0.0, 0.975]` (normalized).
- **Raw smoothed quaternion at frame 0:** set **identical to reference**: `q_raw_smooth[0] = q_ref_rel`.
- **Frames 1 and 2:** two other unit quaternions, e.g. small rotations from identity.
- **Exact:** Frame 0 must yield identity after zeroing: `inv(q_ref) * q_ref = identity`.

### Expected Output
- **Frame 0:** exactly `[0, 0, 0, 1]`.
- **Frames 1, 2:** `q_zeroed[i] = (R.from_quat(q_ref).inv() * R.from_quat(q_raw_smooth[i])).as_quat()` — compute once with SciPy as ground truth.

### Assertion Strategy
- `np.testing.assert_allclose(actual[0], [0, 0, 0, 1], atol=1e-10)`.
- `np.testing.assert_allclose(actual[1:], expected[1:], atol=1e-10)`.
- **Tolerance:** `atol=1e-10`.

---

## 6. Test 6 — Angular Velocity (Quaternion Logarithm Method)

**README (§4 B1):** *"ω(t) = rotvec_delta / dt [rad/s]", "Convert to degrees", "body-local frame: dR = inv(R(t)) * R(t+1)", "Last frame is forward-filled from the penultimate frame."*

### Toy Data
- **Constant angular velocity:** exactly **90 deg/s around X-axis** (body-local).
- **Sampling:** `fs = 120` Hz → `dt = 1/120` s.
- **Quaternion sequence:** at t=0 identity; at t=k·dt rotation = 90° × (k/120) around X:
  - Frame 0: 0° → q = [0, 0, 0, 1].
  - Frame 1: 0.75° → q = [sin(0.375° in rad), 0, 0, cos(0.375° in rad)] in xyzw (X rotation).
  - Frame 2: 1.5°; Frame 3: 2.25° (same axis).
- **Exact:** For constant rate, quat-log between consecutive frames gives ω_rad = (0.75° in rad) / dt = 90° in rad/s → ω_deg = 90 deg/s on X; Y and Z zero.

### Expected Output (deg/s)
- **Frames 1, 2, 3:** ω_x = 90.0, ω_y = 0.0, ω_z = 0.0 (exactly, up to floating point).
- **Frame 0:** implementation-defined (forward fill from frame 1 or zero); test will require frame 0 to equal frame 1 (forward fill) **or** explicitly document and assert the implementation’s choice.
- **Frame 3 (last):** forward-filled from frame 2 → same as frame 2: [90, 0, 0] deg/s.

### Assertion Strategy
- Use `quaternion_log_angular_velocity()` from `src/angular_velocity.py`; convert result to deg/s.
- `np.testing.assert_allclose(omega_deg[1:3], [[90,0,0],[90,0,0]], atol=1e-5)` (frames 1 and 2).
- `np.testing.assert_allclose(omega_deg[3], omega_deg[2], atol=1e-10)` (last frame = forward fill).
- **Tolerance:** `atol=1e-5` for ω (deg/s) to allow minimal numerical error from quat→rotvec; `1e-10` for forward-fill equality.

---

## 7. Test 7 — Linear Velocity and Acceleration (Savitzky-Golay)

**README (§5 C2, C3):** *"vel(t) = d(pos_rel)/dt ≈ SavGol(pos_rel, ..., deriv=1, delta=dt)"*, *"acc(t) = d²(pos_rel)/dt² ≈ SavGol(pos_rel, ..., deriv=2, delta=dt)"*, axis-by-axis.

### Toy Data (Deterministic Motion)
- **Trajectory:** Root-relative position in mm, **one segment**, constant velocity and zero acceleration:
  - **p_x(t) = 100 + 240·t** (t in seconds), **p_y(t) = 200**, **p_z(t) = 300**.
  - So: **v_x = 240 mm/s**, **v_y = 0**, **v_z = 0**; **a_x = a_y = a_z = 0**.
- **Sampling:** `fs = 120` Hz, `dt = 1/120` s. Generate 7 frames: t = 0, 1/120, 2/120, …, 6/120.
  - `pos_rel[:,0] = 100 + 240 * np.arange(7) / 120` (exact).
  - `pos_rel[:,1] = 200`, `pos_rel[:,2] = 300`.
- **SavGol:** `window_length=5`, `polyorder=3`, `deriv=1` and `deriv=2`, `delta=dt`, `mode='interp'` (per README boundary handling). For this linear trajectory, the polynomial fit is exact in the interior (frames 2, 3, 4); boundary frames may differ.

### Expected Output
- **Velocity (interior frames 2, 3, 4):** exactly [240.0, 0.0, 0.0] mm/s each.
- **Acceleration (interior frames 2, 3, 4):** exactly [0.0, 0.0, 0.0] mm/s².
- **Boundary frames (0, 1, 5, 6):** Assert only that velocity/acceleration are finite and (optionally) that velocity is close to 240 for x (e.g. atol=1e-2) to avoid reliance on boundary extrapolation.

### Assertion Strategy
- Apply `savgol_filter` to each column of `pos_rel` with `deriv=1, delta=dt` for velocity and `deriv=2, delta=dt` for acceleration.
- `np.testing.assert_allclose(vel[2:5], [[240,0,0]]*3, atol=1e-5)`.
- `np.testing.assert_allclose(acc[2:5], [[0,0,0]]*3, atol=1e-5)`.
- **Tolerance:** `atol=1e-5` (SavGol is exact for polynomial of order ≤ polyorder in the interior).

---

## 8. Test 8 — Artifact Detection (Dual-Criteria, Threshold-Based)

**README (§8 F1):** *"Rotation magnitude > 140°", "Angular velocity > 800 deg/s", "Linear velocity > 3000 mm/s". "A frame is flagged if **any** criterion is **exceeded**."* (Strict inequality **>**.)

### Toy Data
- **Four frames**, scalar values per criterion (joint: rot_mag, omega_mag; segment: add lin_vel):
  - Frame 0: rot_mag=10, omega=100, lin_vel=500 → no flag.
  - Frame 1: rot_mag=140, omega=800, lin_vel=3000 → **none exceeded** (boundary: not >) → no flag.
  - Frame 2: rot_mag=150, omega=900, lin_vel=3500 → all exceeded → flag.
  - Frame 3: rot_mag=20, omega=200, lin_vel=1000 → no flag.
- **Exact:** Use thresholds 140.0, 800.0, 3000.0; condition is `>`, not `>=`.

### Expected Output
- **Joint-level mask** (rotation OR angular velocity exceeded): `[False, False, True, False]`.
- **Segment-level mask** (rotation OR angular velocity OR linear velocity exceeded): same for this toy data since frame 2 exceeds all.
- **Boundary:** At exactly 140°, 800, 3000 → **False** (not flagged).

### Assertion Strategy
- `artifact_joint = (rotation_mag > 140) | (angular_vel > 800)`.
- `artifact_segment = artifact_joint | (linear_vel > 3000)`.
- `np.testing.assert_array_equal(artifact_joint, [False, False, True, False])`.
- `np.testing.assert_array_equal(artifact_segment, [False, False, True, False])`.
- **Tolerance:** Exact boolean; no float tolerance.

---

## 9. Test 9 — Rotation Vector Conversion (Zeroed → Rotvec)

**README (§3 A3):** *"rotvec(t) = RotationToRotvec(q_zeroed(t))" using SciPy "Rotation.from_quat(q_zeroed).as_rotvec()". "rotvec = angle * axis", magnitude = angle in radians.*

### Toy Data
- **Identity:** q = [0, 0, 0, 1] → rotvec = [0, 0, 0].
- **90° around X:** q = [sin(45°), 0, 0, cos(45°)] in xyzw → rotvec = [π/2, 0, 0] rad.
- **45° around Y:** q = [0, sin(22.5°), 0, cos(22.5°)] → rotvec = [0, π/4, 0] rad.
- Use SciPy to generate exact q for 90° X and 45° Y, then expected rotvec = [π/2,0,0] and [0,π/4,0].

### Expected Output
- **expected[0] = [0, 0, 0]**; **expected[1] = [np.pi/2, 0, 0]**; **expected[2] = [0, np.pi/4, 0]**.

### Assertion Strategy
- `actual = R.from_quat(q_array).as_rotvec()`.
- `np.testing.assert_allclose(actual, expected, atol=1e-10)`.
- **Tolerance:** `atol=1e-10`.

---

## 10. Test 10 — Euler Angle Conversion (ZYX Axial, XYZ Limbs)

**README (§7):** *"Axial chain (Hips, Spine, Spine1, Neck, Head): as_euler('ZYX', degrees=True). Limb joints: as_euler('XYZ', degrees=True)."*

### Toy Data
- **Same quaternions as Test 9:** identity, 90° X, 45° Y.
- **Axial (ZYX):** For 90° rotation around X in intrinsic ZYX, expected Euler (Z,Y,X) ≈ [0, 0, 90]. For 45° around Y in ZYX, expected ≈ [0, 45, 0] (or equivalent depending on convention). Compute expected with `R.from_quat(q).as_euler('ZYX', degrees=True)` once and use as golden.
- **Limb (XYZ):** For 90° X: Euler XYZ = [90, 0, 0]. For 45° Y: [0, 45, 0]. Identity: [0, 0, 0].

### Expected Output
- **ZYX (axial):** Three rows from SciPy `as_euler('ZYX', degrees=True)` for the three quaternions — compute in test setup and assert equality.
- **XYZ (limb):** Three rows from `as_euler('XYZ', degrees=True)`.

### Assertion Strategy
- Do not use loose “approximate” checks; compute expected with the same SciPy API and assert exact match.
- `np.testing.assert_allclose(euler_zyx, expected_zyx, atol=1e-5)` (degrees can have slightly larger representation error).
- `np.testing.assert_allclose(euler_xyz, expected_xyz, atol=1e-5)`.
- **Tolerance:** `atol=1e-5` for degrees.

---

## 11. Test 11 — Whole-Body Center of Mass (compute_whole_body_com)

**README (§6):** *"CoM_seg = pos_proximal + ratio * (pos_distal - pos_proximal)", "WBCoM = Σ(m_i * CoM_i) / Σ(m_i)" over available segments. Missing-segment: sum over available only.*

### Toy Data
- **Two segments only**, to isolate formula:
  - **Segment A:** mass_frac = 0.5, proximal = distal = "A" (point mass at joint A). Position A: (0, 100, 200) mm at all frames.
  - **Segment B:** mass_frac = 0.5, proximal = distal = "B". Position B: (0, 0, 0) mm at all frames.
- **DataFrame:** 3 frames. Columns: `A__lin_rel_px`, `A__lin_rel_py`, `A__lin_rel_pz`, `B__lin_rel_px`, `B__lin_rel_py`, `B__lin_rel_pz`. Frame 0: A=(0,100,200), B=(0,0,0). Frame 1: A=(10,100,200), B=(0,10,0). Frame 2: A=(20,100,200), B=(0,20,0).
- **Custom segment dict:** proximal/distal both the same so `compute_segment_com` returns the joint position; mass 0.5 each.

### Expected Output (Exact)
- **Frame 0:** WBCoM = 0.5×(0,100,200) + 0.5×(0,0,0) = **(0, 50, 100)** mm.
- **Frame 1:** (0.5×(10,100,200) + 0.5×(0,10,0)) = **(5, 55, 100)** mm.
- **Frame 2:** **(10, 60, 100)** mm.

### Assertion Strategy
- Call `compute_whole_body_com(df, segments=custom_two_segments)`.
- `np.testing.assert_allclose(wbcom, expected_wbcom, atol=1e-5)` (mm).
- Report: `segments_available == 2`, `mass_available_pct == 100.0`.
- **Tolerance:** `atol=1e-5` for positions in mm.

---

## Summary Table

| Test | README Section | Toy Data Summary | Key Expected | atol |
|------|----------------|------------------|---------------|------|
| 1 | §3 A1 | q with hemisphere flip | Frame 1 = Frame 0 after unroll | 1e-10 |
| 2 | §3 A1 | Non-unit quats, known norms | Unit norms + exact q/‖q‖ | 1e-10 |
| 3 | §9 | (fs, w_sec, poly) cases | 21, 21, 5, 5 | exact int |
| 4 | §3 A1 | 30° X parent, 45° X child | 15° X relative | 1e-10 |
| 5 | §3 A2 | Ref = raw at frame 0 | Identity at 0; inv(ref)*raw at 1,2 | 1e-10 |
| 6 | §4 B1 | Constant 90 deg/s X, 120 Hz | ω = [90,0,0]; last = forward fill | 1e-5 / 1e-10 |
| 7 | §5 C2, C3 | p_x = 100+240t, 120 Hz, 7 frames | vel=[240,0,0], acc=0 interior | 1e-5 |
| 8 | §8 F1 | 4 frames, boundary at 140/800/3000 | Flag only where strictly > | exact bool |
| 9 | §3 A3 | Identity, 90° X, 45° Y quats | rotvec [0,0,0], [π/2,0,0], [0,π/4,0] | 1e-10 |
| 10 | §7 | Same as Test 9 | ZYX and XYZ from SciPy | 1e-5 |
| 11 | §6 | 2 segments, 50% each, 3 frames | WBCoM (0,50,100), (5,55,100), (10,60,100) | 1e-5 |

---

## Implementation Notes (For Step 2)

- All assertions must use `np.testing.assert_allclose` or `assert_array_equal`; no loose checks (e.g. `vel > 0`).
- Expected arrays must be computed analytically or via the same SciPy/README formulas in the notebook so the test is a **reproducible proof**.
- Test 3 expected for case 3 is **5**, not 7 (current notebook is wrong).
- Artifact test must use **strict `>`** to match README “exceeded”.
- Test 6: confirm in code whether frame 0 is zero or forward-filled and assert accordingly.

---

*End of Step 1 — Test Plan. No Python code has been written. Awaiting approval to proceed to Step 2 (full notebook implementation).*
