# Pipeline Automation Script - Usage Guide

## 📋 Overview

The `run_pipeline.py` script automates the complete motion capture processing pipeline for multiple CSV files. It handles configuration updates, notebook execution, error handling, and result aggregation.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Pipeline

```bash
# Auto-discover and process all CSV files
python run_pipeline.py --auto-discover

# Process specific files from a list
python run_pipeline.py --csv-list csv_files_example.txt

# Process a single file
python run_pipeline.py --single "data/734/T1/734_T1_P2_R1_Take 2025-12-01 02.28.24 PM.csv"
```

## 📖 Command-Line Options

### Required (choose one):

- `--auto-discover` - Automatically find all CSV files in `data/` directory
- `--csv-list FILE` - Process files listed in a text file
- `--single FILE` - Process a single CSV file

### Optional:

- `--project-root PATH` - Path to project root (default: current directory)
- `--stop-on-error` - Stop batch processing on first error (default: continue)
- `--dry-run` - Simulate execution without running notebooks (for testing)

## 📝 Usage Examples

### Example 1: Auto-Discovery (Recommended)

```bash
python run_pipeline.py --auto-discover
```

This will:
- Scan `data/` directory for all `.csv` files
- Exclude files with "test" or "backup" in the name
- Process each file through the complete pipeline
- Generate a master quality report at the end

### Example 2: Custom File List

Create a file `my_files.txt`:
```
data/734/T1/734_T1_P2_R1_Take 2025-12-01 02.28.24 PM.csv
data/734/T2/734_T2_P2_R1_Take 2025-12-17 07.04.43 PM.csv
```

Then run:
```bash
python run_pipeline.py --csv-list my_files.txt
```

### Example 3: Single File Processing

```bash
python run_pipeline.py --single "data/734/T1/734_T1_P2_R1_Take 2025-12-01 02.28.24 PM.csv"
```

### Example 4: Dry Run (Testing)

```bash
python run_pipeline.py --auto-discover --dry-run
```

This simulates the pipeline without actually executing notebooks - useful for testing.

### Example 5: Stop on First Error

```bash
python run_pipeline.py --csv-list my_files.txt --stop-on-error
```

If any file fails, the script stops immediately (default: continues to next file).

## 📊 Output Files

### Logs
```
logs/
└── pipeline_run_20260113_143022.log
```
- Detailed execution log with timestamps
- Errors, warnings, and progress information

### Reports
```
reports/
├── batch_summary_20260113_143500.json
└── Master_Audit_Log_20260113_143530.xlsx
```
- **batch_summary_*.json** - Detailed JSON report of all processed files
- **Master_Audit_Log_*.xlsx** - Excel report comparing all runs (from notebook 07)

### Derivatives
```
derivatives/
├── step_01_parse/
│   └── [RUN_ID]__parsed_run.parquet
├── step_02_preprocess/
│   ├── [RUN_ID]__preprocessed.parquet
│   ├── [RUN_ID]__kinematics_map.json
│   └── [RUN_ID]__preprocess_summary.json
├── step_03_resample/
│   └── [RUN_ID]__resampled.parquet
├── step_04_filtering/
│   ├── [RUN_ID]__filtered.parquet
│   └── [RUN_ID]__filtering_summary.json
├── step_05_reference/
│   ├── [RUN_ID]__reference_map.json
│   └── [RUN_ID]__reference_summary.json
└── step_06_kinematics/
    ├── [RUN_ID]__kinematics.parquet
    └── [RUN_ID]__kinematics_summary.json
```

## 🔧 Pipeline Sequence

The script executes notebooks in this order:

1. **Notebook 01** - Load & Inspect CSV
2. **Notebook 02** - Preprocess (gap filling, bone QC)
3. **Notebook 03** - Resample to uniform time grid
4. **Notebook 04** - Filter (Butterworth low-pass)
5. **Notebook 05** - Reference detection (static calibration)
6. **Notebook 06** - Kinematics calculation (angles, velocities)
7. **Notebook 07** - Master quality report (after all files)

## ⚠️ Error Handling

- If a notebook fails, the error is logged
- By default, the script continues to the next CSV file
- Use `--stop-on-error` to stop on first failure
- Each run's status is saved in the batch summary

## 📈 Monitoring Progress

Watch the console output or tail the log file:

```bash
# In another terminal
tail -f logs/pipeline_run_*.log
```

## 🎯 Tips & Best Practices

1. **Start with `--dry-run`** to verify file paths before processing
2. **Use `--auto-discover`** for convenience
3. **Create custom file lists** for specific subsets (e.g., only T1 sessions)
4. **Check the log file** if something fails - it has detailed error traces
5. **Review `batch_summary_*.json`** for detailed run statistics

## 🐛 Troubleshooting

### Problem: "No CSV files found"
- Check that CSV files exist in `data/` directory
- Verify file paths in your custom file list
- Use absolute paths if relative paths don't work

### Problem: Notebook fails
- Check the log file for detailed error message
- Verify that all dependencies are installed (`pip list`)
- Ensure notebook kernel matches Python environment
- Try running the failing notebook manually to see the error

### Problem: "papermill not found"
```bash
pip install papermill pyyaml
```

### Problem: Slow execution
- Each notebook typically takes 1-5 minutes
- Large CSV files (>100MB) may take longer
- Consider processing files in smaller batches

## 🔄 Workflow Integration

### Daily Batch Processing
```bash
# Process all new files daily
python run_pipeline.py --auto-discover >> daily_log.txt 2>&1
```

### Scheduled Execution (cron)
```bash
# Add to crontab (runs every day at 2 AM)
0 2 * * * cd /path/to/project && python run_pipeline.py --auto-discover
```

### Integration with Other Scripts
```python
from run_pipeline import PipelineRunner

runner = PipelineRunner(project_root='.')
result = runner.process_single_csv(Path('data/734/T1/file.csv'))
print(f"Status: {result['status']}")
```

## 📞 Support

For issues or questions:
1. Check the log file in `logs/`
2. Review the batch summary JSON
3. Verify notebook execution manually
4. Check that `config/config_v1.yaml` is valid

---

**Last Updated:** 2026-01-13
**Script Version:** 1.0
