# 🎯 QUICK REFERENCE - Processing Subject 734

## ⚡ FASTEST WAY TO PROCESS

```bash
# Process ALL 8 files from subject 734 (T1 + T2)
python run_pipeline.py --json batch_configs/subject_734_all.json
```

## 🎛️ OTHER OPTIONS

```bash
# T1 session only (4 files)
python run_pipeline.py --json batch_configs/subject_734_T1_only.json

# T2 session only (4 files)
python run_pipeline.py --json batch_configs/subject_734_T2_only.json

# Dry run first (test without executing)
python run_pipeline.py --json batch_configs/subject_734_all.json --dry-run
```

## 📊 WHAT'S INCLUDED

**subject_734_all.json** → 8 files total:
- T1: 4 files (P1_R1, P1_R2, P2_R1, P2_R2)
- T2: 4 files (P1_R1, P1_R2, P2_R1, P2_R2)

## ⏱️ EXPECTED TIME

- ~5-10 minutes per file
- 8 files × 8 minutes = ~64 minutes total

## 📁 OUTPUT LOCATION

```
logs/           → pipeline_run_YYYYMMDD_HHMMSS.log
reports/        → batch_summary_*.json
                → Master_Audit_Log_*.xlsx
derivatives/    → All processed data
```

## ✅ DONE!

That's all you need. Run the command and let it process! 🚀
