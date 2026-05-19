# Joint Naming Convention Reference

## Standard Joint Names (From skeleton_schema.json)

Your skeleton uses **standard motion capture naming** (similar to BVH/FBX conventions).

---

## Upper Body

### Spine & Head
- `Hips` (root)
- `Spine`
- `Spine1`
- `Neck`
- `Head`

### Left Arm
- `LeftShoulder`
- `LeftArm` (upper arm/humerus)
- `LeftForeArm` (forearm/radius+ulna)
- `LeftHand` (wrist)

### Right Arm
- `RightShoulder`
- `RightArm` (upper arm/humerus)
- `RightForeArm` (forearm/radius+ulna)
- `RightHand` (wrist)

---

## Lower Body

### Left Leg
- `LeftUpLeg` (thigh/femur)
- `LeftLeg` (shin/tibia+fibula)
- `LeftFoot` (ankle)
- `LeftToeBase` (toe)

### Right Leg
- `RightUpLeg` (thigh/femur)
- `RightLeg` (shin/tibia+fibula)
- `RightFoot` (ankle)
- `RightToeBase` (toe)

---

## Fingers (Left & Right)

Each hand has 5 fingers with 3 segments each:

- `[Left/Right]HandThumb1`, `Thumb2`, `Thumb3`
- `[Left/Right]HandIndex1`, `Index2`, `Index3`
- `[Left/Right]HandMiddle1`, `Middle2`, `Middle3`
- `[Left/Right]HandRing1`, `Ring2`, `Ring3`
- `[Left/Right]HandPinky1`, `Pinky2`, `Pinky3`

**Total:** 15 finger segments per hand × 2 hands = 30 finger joints

---

## Important Notes on Naming

### ❌ NOT Used (Common in Other Systems)
- `Elbow` → Use `LeftForeArm` / `RightForeArm`
- `Wrist` → Use `LeftHand` / `RightHand`
- `Knee` → Use `LeftLeg` / `RightLeg`
- `Ankle` → Use `LeftFoot` / `RightFoot`
- `Thigh` → Use `LeftUpLeg` / `RightUpLeg`
- `Shin` → Use `LeftLeg` / `RightLeg`

### ✅ Anatomical Mapping

| Common Name | Your Joint Name | Anatomical Region |
|-------------|-----------------|-------------------|
| **Upper Arm** | `[Left/Right]Arm` | Humerus |
| **Elbow/Forearm** | `[Left/Right]ForeArm` | Radius + Ulna |
| **Wrist/Hand** | `[Left/Right]Hand` | Carpals + Metacarpals |
| **Thigh** | `[Left/Right]UpLeg` | Femur |
| **Knee/Shin** | `[Left/Right]Leg` | Tibia + Fibula |
| **Ankle** | `[Left/Right]Foot` | Tarsals |
| **Toe** | `[Left/Right]ToeBase` | Metatarsals |

---

## Phase 2 Bilateral Pairs (Verified ✅)

The bilateral symmetry code I added uses these pairs:

```python
BILATERAL_PAIRS = {
    "upper_arm": ("LeftArm", "RightArm"),           # ✅ Correct
    "forearm": ("LeftForeArm", "RightForeArm"),     # ✅ Correct
    "hand": ("LeftHand", "RightHand"),              # ✅ Correct
    "thigh": ("LeftUpLeg", "RightUpLeg"),           # ✅ Correct
    "shin": ("LeftLeg", "RightLeg"),                # ✅ Correct
    "foot": ("LeftFoot", "RightFoot"),              # ✅ Correct
}
```

**Status:** All bilateral pairs match your skeleton schema perfectly!

---

## Total Joint Count

| Category | Count |
|----------|-------|
| Core (Hips, Spine, Neck, Head) | 5 |
| Arms (Shoulders, Arms, ForeArms, Hands) | 8 (4 per side) |
| Legs (UpLegs, Legs, Feet, ToeBases) | 8 (4 per side) |
| Fingers | 30 (15 per hand) |
| **TOTAL** | **51 joints** |

---

## Hierarchy Example

```
Hips (root)
├── Spine
│   └── Spine1
│       ├── Neck
│       │   └── Head
│       ├── LeftShoulder
│       │   └── LeftArm
│       │       └── LeftForeArm
│       │           └── LeftHand
│       │               ├── LeftHandThumb1 → Thumb2 → Thumb3
│       │               ├── LeftHandIndex1 → Index2 → Index3
│       │               ├── LeftHandMiddle1 → Middle2 → Middle3
│       │               ├── LeftHandRing1 → Ring2 → Ring3
│       │               └── LeftHandPinky1 → Pinky2 → Pinky3
│       └── RightShoulder
│           └── RightArm
│               └── RightForeArm
│                   └── RightHand
│                       └── (5 fingers, same as left)
├── LeftUpLeg
│   └── LeftLeg
│       └── LeftFoot
│           └── LeftToeBase
└── RightUpLeg
    └── RightLeg
        └── RightFoot
            └── RightToeBase
```

---

## Quick Lookup Table

| If you need... | Use this joint name |
|----------------|---------------------|
| Shoulder | `LeftShoulder` / `RightShoulder` |
| Upper arm | `LeftArm` / `RightArm` |
| Elbow/Forearm | `LeftForeArm` / `RightForeArm` |
| Wrist/Hand | `LeftHand` / `RightHand` |
| Hip | `Hips` (single, central) |
| Thigh | `LeftUpLeg` / `RightUpLeg` |
| Knee/Shin | `LeftLeg` / `RightLeg` |
| Ankle | `LeftFoot` / `RightFoot` |
| Toe | `LeftToeBase` / `RightToeBase` |

---

## For Code/Scripts

When referencing joints in your code, always use the exact capitalization:
- ✅ `LeftArm`
- ❌ `leftarm`
- ❌ `Left_Arm`
- ❌ `left_arm`

**Case-sensitive!** Python will not find `"leftarm"` if the actual joint is `"LeftArm"`.

---

## Source

This naming convention comes from:
- **File:** `config/skeleton_schema.json`
- **Standard:** BVH motion capture format
- **Used by:** Motive (OptiTrack), Maya, Blender, Unity, Unreal Engine
