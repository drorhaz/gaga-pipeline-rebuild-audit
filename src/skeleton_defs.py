# src/skeleton_defs.py
"""
Skeleton hierarchy definitions loaded dynamically from config/skeleton_schema.json.

This module is the Python interface to the canonical skeleton schema. The hierarchy
(parent_map, joint_names) is loaded from the JSON at import time to prevent schema
drift. The angle_name mappings are supplementary metadata defined here.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load canonical schema from JSON (single source of truth)
# ---------------------------------------------------------------------------

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "skeleton_schema.json"
)

try:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as _f:
        _SCHEMA = json.load(_f)
    logger.debug("Loaded skeleton schema from %s", _SCHEMA_PATH)
except FileNotFoundError:
    raise FileNotFoundError(
        f"Skeleton schema not found at {_SCHEMA_PATH}. "
        "Ensure config/skeleton_schema.json exists in the project root."
    )

# ---------------------------------------------------------------------------
# Angle-name lookup (supplementary metadata, not in JSON)
# ---------------------------------------------------------------------------

_ANGLE_NAMES = {
    "Hips": "Pelvis_Global_Orientation (World Space)",
    "Spine": "Lumbar_Angle",
    "Spine1": "Thoracic_Angle",
    "Neck": "Neck_Base_Angle",
    "Head": "Head_Angle",
    "LeftUpLeg": "LeftHip_Angle",
    "LeftLeg": "LeftKnee_Angle",
    "LeftFoot": "LeftAnkle_Angle",
    "LeftToeBase": "LeftToe_Angle",
    "RightUpLeg": "RightHip_Angle",
    "RightLeg": "RightKnee_Angle",
    "RightFoot": "RightAnkle_Angle",
    "RightToeBase": "RightToe_Angle",
    "LeftShoulder": "LeftClavicle_Angle",
    "LeftArm": "LeftShoulder_Joint_Angle",
    "LeftForeArm": "LeftElbow_Angle",
    "LeftHand": "LeftWrist_Angle",
    "RightShoulder": "RightClavicle_Angle",
    "RightArm": "RightShoulder_Joint_Angle",
    "RightForeArm": "RightElbow_Angle",
    "RightHand": "RightWrist_Angle",
    "LeftHandThumb1": "L_Thumb1",
    "LeftHandThumb2": "L_Thumb2",
    "LeftHandThumb3": "L_Thumb3",
    "LeftHandIndex1": "L_Index1",
    "LeftHandIndex2": "L_Index2",
    "LeftHandIndex3": "L_Index3",
    "LeftHandMiddle1": "L_Middle1",
    "LeftHandMiddle2": "L_Middle2",
    "LeftHandMiddle3": "L_Middle3",
    "LeftHandRing1": "L_Ring1",
    "LeftHandRing2": "L_Ring2",
    "LeftHandRing3": "L_Ring3",
    "LeftHandPinky1": "L_Pinky1",
    "LeftHandPinky2": "L_Pinky2",
    "LeftHandPinky3": "L_Pinky3",
    "RightHandThumb1": "R_Thumb1",
    "RightHandThumb2": "R_Thumb2",
    "RightHandThumb3": "R_Thumb3",
    "RightHandIndex1": "R_Index1",
    "RightHandIndex2": "R_Index2",
    "RightHandIndex3": "R_Index3",
    "RightHandMiddle1": "R_Middle1",
    "RightHandMiddle2": "R_Middle2",
    "RightHandMiddle3": "R_Middle3",
    "RightHandRing1": "R_Ring1",
    "RightHandRing2": "R_Ring2",
    "RightHandRing3": "R_Ring3",
    "RightHandPinky1": "R_Pinky1",
    "RightHandPinky2": "R_Pinky2",
    "RightHandPinky3": "R_Pinky3",
}

# ---------------------------------------------------------------------------
# Build SKELETON_HIERARCHY dynamically from JSON parent_map
# ---------------------------------------------------------------------------

SKELETON_HIERARCHY = {}
for _joint, _parent in _SCHEMA["parent_map"].items():
    SKELETON_HIERARCHY[_joint] = {
        "parent": _parent,
        "angle_name": _ANGLE_NAMES.get(_joint, f"{_joint}_Angle"),
    }


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def is_finger_or_toe_segment(joint_name):
    """
    Determines if a joint name represents a finger or toe segment.

    Hand Fingers: All segments containing Hand(Thumb|Index|Middle|Ring|Pinky)
    Foot Toes: LeftToeBase, RightToeBase

    Parameters
    ----------
    joint_name : str
        The joint name to check

    Returns
    -------
    bool
        True if the joint is a finger or toe segment, False otherwise
    """
    finger_patterns = ['HandThumb', 'HandIndex', 'HandMiddle', 'HandRing', 'HandPinky']
    if any(pattern in joint_name for pattern in finger_patterns):
        return True

    if joint_name in ['LeftToeBase', 'RightToeBase']:
        return True

    return False


def get_schema():
    """Return the raw skeleton schema dict loaded from JSON."""
    return _SCHEMA.copy()
