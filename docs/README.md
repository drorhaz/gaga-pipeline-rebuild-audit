# Gaga Mocap Pipeline - Documentation Index

Complete documentation for the Gaga Motion Capture Kinematic Analysis Pipeline.

---

## Documentation Structure

```
docs/
├── README.md                        # This index file
├── PIPELINE_RUN_CONVENTION.md       # How RUN_ID propagates through pipeline
├── JOINT_NAMING_CONVENTION.md       # Standard joint names reference
├── ANATOMICAL_REGION_MAPPING.md     # Joint-to-region aggregation
├── ROM_DOCUMENTATION.md             # Range of Motion analysis
├── HEIGHT_ESTIMATION_DOCUMENTATION.md # Anthropometric calculations
├── guides/                          # User guides
│   ├── PIPELINE_USAGE.md           # Complete pipeline documentation
│   ├── QUICK_START_734.md          # Example: processing subject 734
│   ├── JSON_BATCH_SYSTEM.md        # JSON batch configuration guide
│   ├── DASHBOARD_GUIDE.md          # Visualization dashboard guide
│   └── JOINT_STATISTICS_GUIDE.md   # Joint QC interpretation
├── technical/                       # Technical documentation
│   ├── METHODS_DOCUMENTATION.md    # Scientific methods (publication-ready)
│   ├── PIPELINE_COMPONENTS_EXPLAINED.md # Component deep-dive
│   └── PARAMETER_SCHEMA.md         # Report field definitions (all JSON params)
└── quality_control/                 # Quality control framework
    ├── 00_OVERVIEW.md              # QC documentation overview
    ├── 01_RECORDING_AUDIT_CHECKLIST.md # Audit protocol per recording
    └── 03_JOINT_LEVEL_TRACKING.md  # Joint-level debugging rationale
```

---

## Quick Navigation

### I want to...

| Task | Document |
|------|----------|
| **Run the pipeline** | [guides/PIPELINE_USAGE.md](guides/PIPELINE_USAGE.md) |
| **Process batch files** | [guides/JSON_BATCH_SYSTEM.md](guides/JSON_BATCH_SYSTEM.md) |
| **Quick start example** | [guides/QUICK_START_734.md](guides/QUICK_START_734.md) |
| **Use the dashboard** | [guides/DASHBOARD_GUIDE.md](guides/DASHBOARD_GUIDE.md) |
| **Interpret joint QC** | [guides/JOINT_STATISTICS_GUIDE.md](guides/JOINT_STATISTICS_GUIDE.md) |
| **Audit a recording** | [quality_control/01_RECORDING_AUDIT_CHECKLIST.md](quality_control/01_RECORDING_AUDIT_CHECKLIST.md) |
| **Understand methods** | [technical/METHODS_DOCUMENTATION.md](technical/METHODS_DOCUMENTATION.md) |
| **View report schema** | [technical/PARAMETER_SCHEMA.md](technical/PARAMETER_SCHEMA.md) |
| **Understand RUN_ID flow** | [PIPELINE_RUN_CONVENTION.md](PIPELINE_RUN_CONVENTION.md) |
| **Look up joint names** | [JOINT_NAMING_CONVENTION.md](JOINT_NAMING_CONVENTION.md) |
| **Region mapping** | [ANATOMICAL_REGION_MAPPING.md](ANATOMICAL_REGION_MAPPING.md) |
| **Access ROM data** | [ROM_DOCUMENTATION.md](ROM_DOCUMENTATION.md) |
| **Height estimation** | [HEIGHT_ESTIMATION_DOCUMENTATION.md](HEIGHT_ESTIMATION_DOCUMENTATION.md) |

---

## Recommended Reading Order

### For New Users
1. [../README.md](../README.md) - Project overview
2. [guides/PIPELINE_USAGE.md](guides/PIPELINE_USAGE.md) - How to run the pipeline
3. [guides/QUICK_START_734.md](guides/QUICK_START_734.md) - Process your first file

### For Researchers (Quality Assurance)
1. [quality_control/00_OVERVIEW.md](quality_control/00_OVERVIEW.md) - QC framework
2. [quality_control/01_RECORDING_AUDIT_CHECKLIST.md](quality_control/01_RECORDING_AUDIT_CHECKLIST.md) - Audit protocol
3. [guides/JOINT_STATISTICS_GUIDE.md](guides/JOINT_STATISTICS_GUIDE.md) - Interpret results

### For Developers / AI Agents
1. [PIPELINE_RUN_CONVENTION.md](PIPELINE_RUN_CONVENTION.md) - How RUN_ID and current_csv flow
2. [technical/PIPELINE_COMPONENTS_EXPLAINED.md](technical/PIPELINE_COMPONENTS_EXPLAINED.md) - Architecture
3. [technical/PARAMETER_SCHEMA.md](technical/PARAMETER_SCHEMA.md) - JSON field definitions
4. [technical/METHODS_DOCUMENTATION.md](technical/METHODS_DOCUMENTATION.md) - Scientific methods
5. [JOINT_NAMING_CONVENTION.md](JOINT_NAMING_CONVENTION.md) - Joint name reference
6. [ANATOMICAL_REGION_MAPPING.md](ANATOMICAL_REGION_MAPPING.md) - Region aggregation

---

## Configuration Files

- [`../config/config_v1.yaml`](../config/config_v1.yaml) - Main pipeline configuration
- [`../config/biomechanical_config.json`](../config/biomechanical_config.json) - Biomechanical thresholds
- [`../batch_configs/`](../batch_configs/) - Batch processing configurations

---

## References (Academic Literature)

Located in [`../references/`](../references/):
- Winter (2009) - Biomechanics textbook
- Wu et al. (2005) - ISB joint coordinate standards
- Skurowski et al. - Artifact truncation methods
- Racz et al. (2025) - CAST technique

---

**Last Updated:** February 2026
