"""
Batch runner — Forensic QA Report for Subject 651 P2 R1 (3 sessions).

Loads step_03 (raw) + step_04 (cleaned) parquets for each session,
then calls generate_cleaning_report() which produces:
  - JSON report
  - CSV tables
  - PNG forensic plots + dashboard

Output goes to:  reports/forensic_qa/<run_id>/
"""

import json
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

# ── project paths ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from forensic_report import generate_cleaning_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── configuration ──────────────────────────────────────────────────
CONFIG_PATH = ROOT / "config" / "config_v1.yaml"
SCHEMA_PATH = ROOT / "config" / "skeleton_schema.json"
STEP03_DIR  = ROOT / "derivatives" / "step_03_resample"
STEP04_DIR  = ROOT / "derivatives" / "step_04_filtering"
REPORTS_DIR = ROOT / "reports" / "forensic_qa"

# The 3 sessions from subject_651_p2_r1_all.json
SESSIONS = [
    "651_T1_P2_R1_Take 2026-01-15 04.35.25 PM_002",
    "651_T2_P2_R1_Take 2026-01-26 05.24.12 PM_000",
    "651_T3_P2_R1_2026-02-11 05.50.42 PM_2027",
]


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run_one(run_id: str, config: dict, schema: dict) -> bool:
    """Run forensic report for a single session. Returns True on success."""
    raw_path  = STEP03_DIR / f"{run_id}__resampled.parquet"
    clean_path = STEP04_DIR / f"{run_id}__filtered.parquet"
    summary_path = STEP04_DIR / f"{run_id}__filtering_summary.json"

    # ── validate files exist ──
    for p, label in [(raw_path, "step_03"), (clean_path, "step_04")]:
        if not p.exists():
            log.error("MISSING %s: %s", label, p)
            return False

    log.info("="*70)
    log.info("SESSION: %s", run_id)
    log.info("="*70)

    # ── load data ──
    log.info("Loading raw  (step_03) …")
    original_df = pd.read_parquet(raw_path)
    log.info("  → %d rows × %d cols", *original_df.shape)

    log.info("Loading clean (step_04) …")
    cleaned_df = pd.read_parquet(clean_path)
    log.info("  → %d rows × %d cols", *cleaned_df.shape)

    fs = config.get("fs_target", 120.0)

    # ── load auxiliary data from filtering_summary ──
    artifact_log = None
    snr_report = None
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        artifact_log = summary.get("filter_params")
        snr_report = summary.get("snr_analysis")

    # ── output directory ──
    out_dir = REPORTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── run report ──
    log.info("Generating forensic report …")
    report = generate_cleaning_report(
        original_df=original_df,
        cleaned_df=cleaned_df,
        config=config,
        skeleton_schema=schema,
        fs=fs,
        artifact_log=artifact_log,
        snr_report=snr_report,
        output_dir=out_dir,
        run_id=run_id,
    )

    # ── summary ──
    es = report.get("executive_summary", {})
    verdict = es.get("verdict", "N/A")
    log.info("  Verdict: %s", verdict)
    log.info("  Output : %s", out_dir)
    return True


def main():
    config = load_config()
    schema = load_schema()

    ok, fail = 0, 0
    for run_id in SESSIONS:
        try:
            if run_one(run_id, config, schema):
                ok += 1
            else:
                fail += 1
        except Exception:
            log.exception("FAILED: %s", run_id)
            fail += 1

    log.info("")
    log.info("Done — %d succeeded, %d failed out of %d sessions.", ok, fail, len(SESSIONS))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
