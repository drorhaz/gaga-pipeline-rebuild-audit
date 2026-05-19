# 📋 Batch Configuration Files - User Guide

## 📖 What Are These JSON Files?

Batch configuration files are JSON files that tell the pipeline **exactly which CSV files to process** in a single run. They provide a structured, reusable way to define processing batches.

## 🎯 Why Use JSON Batch Configs?

### ✅ **Advantages:**
1. **Precise Control** - Select exactly which files to process
2. **Reproducible** - Same config = same results every time
3. **Organized** - Group files by subject, session, or any criteria
4. **Documented** - Built-in descriptions and metadata
5. **Version Controlled** - Track what was processed when
6. **Shareable** - Easy to share processing batches with team

### 🆚 **vs. Other Methods:**

| Method | Use Case |
|--------|----------|
| `--json` | ✅ **Best for:** Specific batches, reproducible runs, organized processing |
| `--auto-discover` | Good for: Processing everything quickly |
| `--csv-list` | Good for: Simple text lists, quick edits |
| `--single` | Good for: Testing individual files |

---

## 📂 Pre-Generated Configs

### **Subject 734 - All Sessions (8 files)**
```bash
python run_pipeline.py --json batch_configs/subject_734_all.json
```
Includes: All T1 and T2 files for subject 734

### **Subject 734 - T1 Session Only (4 files)**
```bash
python run_pipeline.py --json batch_configs/subject_734_T1_only.json
```
Includes: Only T1 session files

### **Subject 734 - T2 Session Only (4 files)**
```bash
python run_pipeline.py --json batch_configs/subject_734_T2_only.json
```
Includes: Only T2 session files

---

## 🔧 JSON File Format

### **Structure:**
```json
{
  "batch_name": "Subject_734_All_Sessions",
  "description": "All CSV files for subject 734 (T1 and T2 sessions)",
  "created_date": "2026-01-13",
  "csv_files": [
    "734/T1/734_T1_P1_R1_Take 2025-12-01 02.18.27 PM.csv",
    "734/T1/734_T1_P2_R1_Take 2025-12-01 02.28.24 PM.csv"
  ],
  "total_files": 2,
  "notes": "Use with: python run_pipeline.py --json batch_configs/subject_734_all.json"
}
```

### **Field Descriptions:**

| Field | Required | Description |
|-------|----------|-------------|
| `batch_name` | Yes | Descriptive name for this batch |
| `description` | No | Detailed description |
| `created_date` | No | When this config was created |
| `csv_files` | **Yes** | Array of CSV file paths (relative to `data/`) |
| `total_files` | No | Count of files (for quick reference) |
| `notes` | No | Usage instructions or comments |

### **Path Format:**
- Paths are **relative to the `data/` directory**
- Use **forward slashes** `/` (cross-platform compatible)
- Examples:
  - ✅ `"734/T1/file.csv"`
  - ✅ `"763/T2/file.csv"`
  - ❌ `"data/734/T1/file.csv"` (don't include "data/")
  - ❌ `"734\\T1\\file.csv"` (don't use backslashes)

---

## 🤖 Auto-Generate Configs

### **Quick Start:**

```bash
# Generate configs for subject 734 (all sessions + per-session)
python generate_batch_config.py --subject 734

# Generate configs for subject 734, T1 only
python generate_batch_config.py --subject 734 --session T1

# Generate configs for ALL subjects (discovers automatically)
python generate_batch_config.py --all
```

### **What Gets Generated:**

**For `--subject 734`:**
- `subject_734_all.json` - All sessions
- `subject_734_T1_only.json` - T1 only
- `subject_734_T2_only.json` - T2 only

**For `--all`:**
- Per-subject all-sessions configs
- Per-subject per-session configs
- `all_subjects_all_sessions.json` - Everything!

---

## ✍️ Create Custom Configs Manually

### **Example 1: Custom Selection**

Create `batch_configs/my_custom_batch.json`:

```json
{
  "batch_name": "Baseline_Tests",
  "description": "Only P1_R1 trials from all subjects",
  "csv_files": [
    "734/T1/734_T1_P1_R1_Take 2025-12-01 02.18.27 PM.csv",
    "734/T2/734_T2_P1_R1_Take 2025-12-17 06.59.27 PM.csv",
    "763/T2/763_T2_P1_R1_Take 2025-12-25 10.45.00 AM.csv"
  ],
  "total_files": 3
}
```

Then run:
```bash
python run_pipeline.py --json batch_configs/my_custom_batch.json
```

### **Example 2: Testing Batch**

Create `batch_configs/test_batch.json`:

```json
{
  "batch_name": "Quick_Test",
  "description": "Small batch for testing pipeline",
  "csv_files": [
    "734/T1/734_T1_P1_R1_Take 2025-12-01 02.18.27 PM.csv"
  ],
  "total_files": 1,
  "notes": "Use for quick pipeline tests before full runs"
}
```

---

## 🚀 Usage Examples

### **1. Dry Run First (Recommended)**
```bash
python run_pipeline.py --json batch_configs/subject_734_all.json --dry-run
```
Tests the configuration without executing notebooks.

### **2. Process Subject 734, All Sessions**
```bash
python run_pipeline.py --json batch_configs/subject_734_all.json
```

### **3. Process Only T1 Session**
```bash
python run_pipeline.py --json batch_configs/subject_734_T1_only.json
```

### **4. Stop on First Error**
```bash
python run_pipeline.py --json batch_configs/subject_734_T1_only.json --stop-on-error
```

### **5. Custom Project Root**
```bash
python run_pipeline.py --json batch_configs/my_batch.json --project-root /path/to/project
```

---

## 📊 Current Available Configs

### Generated Files in `batch_configs/`:

```
batch_configs/
├── subject_734_all.json          (8 files) - All T1 + T2
├── subject_734_T1_only.json      (4 files) - T1 session
└── subject_734_T2_only.json      (4 files) - T2 session
```

### File Breakdown:

**Subject 734, T1 Session (4 files):**
- 734_T1_P1_R1_Take 2025-12-01 02.18.27 PM.csv
- 734_T1_P1_R2_Take 2025-12-01 02.32.02 PM.csv
- 734_T1_P2_R1_Take 2025-12-01 02.28.24 PM.csv
- 734_T1_P2_R2_Take 2025-12-01 02.36.55 PM.csv

**Subject 734, T2 Session (4 files):**
- 734_T2_P1_R1_Take 2025-12-17 06.59.27 PM.csv
- 734_T2_P1_R2_Take 2025-12-17 07.07.16 PM.csv
- 734_T2_P2_R1_Take 2025-12-17 07.04.43 PM.csv
- 734_T2_P2_R2_Take 2025-12-17 07.11.37 PM.csv

---

## ✅ Verification

### **Check What's in a Config:**
```bash
# Pretty print JSON
python -m json.tool batch_configs/subject_734_all.json
```

### **Count Files:**
```bash
# Linux/Mac
jq '.total_files' batch_configs/subject_734_all.json

# Or just open in any text editor
```

---

## 🎯 Best Practices

1. **Use Descriptive Names**
   - ✅ `subject_734_baseline_tests.json`
   - ❌ `batch1.json`

2. **Add Descriptions**
   - Document what the batch includes and why
   - Makes it easy to remember 6 months later

3. **Test with Dry Run**
   - Always run `--dry-run` first
   - Verify file paths are correct

4. **Version Control**
   - Commit JSON configs to git
   - Track what batches were processed when

5. **Organize by Purpose**
   - `batch_configs/subjects/` - Per-subject configs
   - `batch_configs/sessions/` - Per-session configs
   - `batch_configs/analysis/` - Analysis-specific batches

---

## 🔄 Regenerate Configs

If you add new CSV files or need to update configs:

```bash
# Regenerate for subject 734
python generate_batch_config.py --subject 734

# Regenerate everything
python generate_batch_config.py --all
```

This will overwrite existing configs with updated file lists.

---

## 🆘 Troubleshooting

### **Problem: "File not found" errors**

**Solution:** Check that paths are correct
```bash
# Verify files exist
ls data/734/T1/*.csv
```

Paths in JSON should be **relative to `data/`**:
- ✅ `"734/T1/file.csv"`
- ❌ `"data/734/T1/file.csv"`

### **Problem: JSON parsing error**

**Solution:** Validate JSON syntax
```bash
python -m json.tool batch_configs/your_file.json
```

Common issues:
- Missing comma between array elements
- Extra comma after last element
- Unquoted strings
- Backslashes in paths (use forward slashes)

### **Problem: No files processed**

**Solution:** Check the `csv_files` array isn't empty
```bash
# Check content
cat batch_configs/your_file.json
```

---

## 📚 Complete Workflow Example

```bash
# 1. Generate configs
python generate_batch_config.py --subject 734

# 2. Review what was generated
ls batch_configs/

# 3. Test with dry run
python run_pipeline.py --json batch_configs/subject_734_T1_only.json --dry-run

# 4. Run for real
python run_pipeline.py --json batch_configs/subject_734_T1_only.json

# 5. Check results
ls reports/
ls derivatives/step_06_kinematics/
```

---

**Need help?** Check `docs/guides/PIPELINE_USAGE.md` or run:
```bash
python run_pipeline.py --help
python generate_batch_config.py --help
```
