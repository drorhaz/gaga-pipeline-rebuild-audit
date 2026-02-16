# Quality Control Documentation Suite - Overview

Quick navigation guide for the Quality Control framework.

---

## What This Suite Covers

This documentation suite provides a quality assurance framework for biomechanical motion capture data:

1. **Audit Protocol** - Standardized checklist with literature-based standards
2. **Joint Tracking** - Rationale for joint-level debugging

For the complete JSON field schema, see [../technical/PARAMETER_SCHEMA.md](../technical/PARAMETER_SCHEMA.md).

---

## Documents in This Suite

### [01_RECORDING_AUDIT_CHECKLIST.md](01_RECORDING_AUDIT_CHECKLIST.md)

**Purpose**: Standardized audit protocol for every motion capture recording

**When to Use**:
- Auditing individual recordings
- Establishing quality criteria for research
- Training new analysts on standards
- Creating acceptance/rejection criteria

**Key Content**:
- 90+ audit checkpoints across 7 pipeline stages
- Literature-based thresholds (Winter, Wu/ISB, Skurowski, Racz)
- PASS/WARN/FAIL criteria for each metric
- Critical failure conditions (automatic rejection)

**Pipeline Stages Covered**:
- Stage 1: Data Loading (6 subsections)
- Stage 2: Preprocessing (5 subsections)
- Stage 3: Resampling (2 subsections)
- Stage 4: Filtering (4 subsections)
- Stage 5: Reference Detection (5 subsections)
- Stage 6: Kinematic Calculation (6 subsections)
- Stage 7: Final QA (4 subsections)

---

### [03_JOINT_LEVEL_TRACKING.md](03_JOINT_LEVEL_TRACKING.md)

**Purpose**: Rationale and implementation for joint-level metric tracking

**When to Use**:
- Understanding WHY joint tracking matters
- Implementing joint identification in step_06
- Debugging context-aware quality control
- Creating joint-specific thresholds

**Key Insight**:
```
"Max_Ang_Vel": 1026.98 deg/s
-> Normal for "RightHand"
-> Unphysiological for "Hips"

Context = Everything!
```

---

## Related Documentation

| Need | Document |
|------|----------|
| Complete JSON field definitions | [../technical/PARAMETER_SCHEMA.md](../technical/PARAMETER_SCHEMA.md) |
| Scientific methods | [../technical/METHODS_DOCUMENTATION.md](../technical/METHODS_DOCUMENTATION.md) |
| Pipeline architecture | [../technical/PIPELINE_COMPONENTS_EXPLAINED.md](../technical/PIPELINE_COMPONENTS_EXPLAINED.md) |
| Joint naming | [../JOINT_NAMING_CONVENTION.md](../JOINT_NAMING_CONVENTION.md) |
| Region mapping | [../ANATOMICAL_REGION_MAPPING.md](../ANATOMICAL_REGION_MAPPING.md) |

---

## Literature Alignment

All standards based on:
- Winter (2009) - Filtering methodology
- Wu et al. (2005) - ISB joint standards
- Skurowski et al. - Artifact detection
- Racz et al. (2025) - CAST calibration

---

**Last Updated:** February 2026
