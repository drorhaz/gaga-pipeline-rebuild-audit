# Gaga Mocap Kinematics Pipeline

A comprehensive motion capture data processing pipeline for biomechanical analysis of Gaga dance movement data. The pipeline processes OptiTrack motion capture data through quality control, filtering, and kinematic analysis stages.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Test Your Setup

```bash
python test_pipeline_setup.py
```

### 3. Run the Pipeline

**Auto-discover all CSV files:**
```bash
python run_pipeline.py --auto-discover
```

**Process with JSON batch config:**
```bash
python run_pipeline.py --json batch_configs/subject_734_all.json
```

**Process single file:**
```bash
python run_pipeline.py --single "data/734/T1/734_T1_P1_R1_Take 2025-12-01 02.18.27 PM.csv"
```

## Project Structure

```
gaga/
├── run_pipeline.py              # Main automation script
├── requirements.txt             # Python dependencies
├── config/
│   ├── config_v1.yaml          # Pipeline configuration
│   └── biomechanical_config.json
├── notebooks/                   # Processing notebooks (00-09)
│   ├── 01_Load_Inspect.ipynb
│   ├── 02_preprocess.ipynb
│   ├── 03_resample.ipynb
│   ├── 04_filtering.ipynb
│   ├── 05_reference_detection.ipynb
│   ├── 06_rotvec_omega.ipynb
│   ├── 07_master_quality_report.ipynb
│   └── 08_visualization_and_analysis.ipynb
├── src/                         # Core processing modules
├── data/                        # Input CSV files
├── derivatives/                 # Processed outputs
├── reports/                     # Quality reports (Excel)
├── logs/                        # Execution logs
├── batch_configs/               # JSON batch configurations
└── docs/                        # Documentation
```

## Documentation

All documentation is organized in the `docs/` directory:

- **[Documentation Index](docs/README.md)** - Complete documentation overview

### Guides
- [Pipeline Usage Guide](docs/guides/PIPELINE_USAGE.md) - Detailed pipeline documentation
- [Quick Start - Subject 734](docs/guides/QUICK_START_734.md) - Example processing
- [JSON Batch System](docs/guides/JSON_BATCH_SYSTEM.md) - Batch configuration guide
- [Dashboard Guide](docs/guides/DASHBOARD_GUIDE.md) - Visualization dashboard
- [Joint Statistics Guide](docs/guides/JOINT_STATISTICS_GUIDE.md) - QC interpretation

### Technical Documentation
- [Methods Documentation](docs/technical/METHODS_DOCUMENTATION.md) - Scientific methods
- [Pipeline Components](docs/technical/PIPELINE_COMPONENTS_EXPLAINED.md) - Component details
- [Parameter Schema](docs/technical/PARAMETER_SCHEMA.md) - Report field definitions

### Conventions & Reference
- [Pipeline Run Convention](docs/PIPELINE_RUN_CONVENTION.md) - RUN_ID propagation
- [Joint Naming Convention](docs/JOINT_NAMING_CONVENTION.md) - Standard joint names
- [Anatomical Region Mapping](docs/ANATOMICAL_REGION_MAPPING.md) - Joint-to-region aggregation

### Quality Control
- [QC Overview](docs/quality_control/00_OVERVIEW.md) - Quality control framework
- [Recording Audit Checklist](docs/quality_control/01_RECORDING_AUDIT_CHECKLIST.md)
- [Joint-Level Tracking](docs/quality_control/03_JOINT_LEVEL_TRACKING.md) - Joint-level debugging

### Features
- [ROM Documentation](docs/ROM_DOCUMENTATION.md) - Range of Motion analysis
- [Height Estimation](docs/HEIGHT_ESTIMATION_DOCUMENTATION.md) - Anthropometric calculations

## Pipeline Stages

| Stage | Notebook | Description |
|-------|----------|-------------|
| 1 | 01_Load_Inspect | Load CSV, validate structure |
| 2 | 02_preprocess | Gap filling, bone length QC |
| 3 | 03_resample | Uniform time grid resampling |
| 4 | 04_filtering | Butterworth low-pass filtering |
| 5 | 05_reference | Static calibration detection |
| 6 | 06_rotvec_omega | Kinematics (angles, velocities) |
| 7 | 07_master_quality | Quality report generation |
| 8 | 08_visualization | Analysis dashboards |

## Outputs

- **Logs:** `logs/pipeline_run_YYYYMMDD_HHMMSS.log`
- **Reports:** `reports/Master_Audit_Log_YYYYMMDD_HHMMSS.xlsx`
- **Derivatives:** `derivatives/step_XX/[run_id]__*.parquet`

## Scientific Standards

The pipeline implements research-validated methods:

- **ISB Compliance:** Wu et al. (2002, 2005) joint coordinate standards
- **Filtering:** Winter (2009) biomechanical signal processing
- **SNR Analysis:** Cereatti et al. (2024) signal quality metrics
- **Quaternion Methods:** Grassia (1998), Shoemake (1985)

## License

[Add your license here]

## Citation

[Add citation information here]
