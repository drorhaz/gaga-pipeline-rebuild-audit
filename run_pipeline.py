#!/usr/bin/env python3
"""
Automated Motion Capture Pipeline Runner
Processes multiple CSV files through the complete pipeline.

Usage:
    python run_pipeline.py                    # default: Subject_671_All_Sessions
    python run_pipeline.py --json batch_configs/subject_671_all.json
    python run_pipeline.py --csv-list csv_files.txt
    python run_pipeline.py --auto-discover
    python run_pipeline.py --single "data/734/T1/file.csv"
"""

import os
import re
import sys
import yaml
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import argparse


class PipelineRunner:
    """Orchestrates the complete motion capture processing pipeline."""
    
    def __init__(self, project_root: str, dry_run: bool = False):
        self.project_root = Path(project_root)
        self.config_file = self.project_root / "config" / "config_v1.yaml"
        self.notebooks_dir = self.project_root / "notebooks"
        self.dry_run = dry_run
        
        # Pipeline sequence (notebook numbers)
        self.pipeline_sequence = ['01', '02', '03', '04', '05', '06','08']
        
        # Load subjects anthropometric registry once at startup
        self.subjects_registry = self._load_subjects_registry()
        
        # Setup logging
        self.setup_logging()
        
    def setup_logging(self):
        """Configure logging to file and console."""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f"pipeline_run_{timestamp}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Pipeline Runner initialized. Log: {log_file}")
    
    def _load_subjects_registry(self) -> Dict:
        """Load per-subject anthropometric registry from data/subjects_registry.json."""
        registry_path = self.project_root / "data" / "subjects_registry.json"
        if not registry_path.exists():
            return {}
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Strip metadata keys (prefixed with _)
            return {k: v for k, v in data.items() if not k.startswith("_")}
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: Could not load subjects registry: {e}")
            return {}
    
    @staticmethod
    def _extract_subject_id(csv_path: Path, data_dir: Path) -> Optional[str]:
        """
        Extract subject ID from CSV path.
        
        Tries: relative-path first directory component (e.g. '671/T1/...' -> '671'),
        then leading digits in filename (e.g. '671_T1_...' -> '671').
        """
        try:
            relative = csv_path.relative_to(data_dir)
            parts = relative.parts
            if parts and parts[0].isdigit():
                return parts[0]
        except ValueError:
            pass
        # Fallback: leading digits in filename
        m = re.match(r"^(\d+)", csv_path.stem)
        return m.group(1) if m else None
    
    def _get_subject_anthropometrics(self, csv_path: Path) -> Dict:
        """
        Look up height/weight for the subject that owns *csv_path*.
        
        Returns dict with subject_id, subject_height_cm, subject_mass_kg,
        subject_height_source, subject_weight_source.  Values are None when
        not found in the registry.
        """
        data_dir = self.project_root / "data"
        subject_id = self._extract_subject_id(csv_path, data_dir)
        result = {
            "subject_id": subject_id,
            "subject_height_cm": None,
            "subject_mass_kg": None,
            "subject_height_source": None,
            "subject_weight_source": None,
        }
        if subject_id is None:
            return result
        
        entry = self.subjects_registry.get(subject_id, {})
        if entry.get("height_cm") is not None:
            result["subject_height_cm"] = float(entry["height_cm"])
            result["subject_height_source"] = entry.get("height_source", "registry")
        if entry.get("weight_kg") is not None:
            result["subject_mass_kg"] = float(entry["weight_kg"])
            result["subject_weight_source"] = entry.get("weight_source", "registry")
        
        return result
    
    def discover_csv_files(self, pattern: str = "**/*.csv") -> List[Path]:
        """Auto-discover CSV files in data directory."""
        data_dir = self.project_root / "data"
        csv_files = list(data_dir.glob(pattern))
        
        # Exclude files with 'test' or 'backup' in name
        csv_files = [f for f in csv_files 
                     if 'test' not in f.name.lower() 
                     and 'backup' not in f.name.lower()]
        
        self.logger.info(f"Discovered {len(csv_files)} CSV files")
        return sorted(csv_files)
    
    def update_config(self, csv_path: Path) -> bool:
        """Update config.yaml with new CSV path and subject anthropometrics."""
        try:
            # Calculate relative path from data dir
            data_dir = self.project_root / "data"
            relative_path = csv_path.relative_to(data_dir)
            
            # Read current config
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Update CSV path (use forward slashes for cross-platform)
            config['current_csv'] = str(relative_path).replace('\\', '/')
            
            # --- Inject subject anthropometrics from registry ---
            anthro = self._get_subject_anthropometrics(csv_path)
            config['subject_id'] = anthro['subject_id']
            config['subject_height_cm'] = anthro['subject_height_cm']
            config['subject_mass_kg'] = anthro['subject_mass_kg']
            config['subject_height_source'] = anthro['subject_height_source']
            config['subject_weight_source'] = anthro['subject_weight_source']
            
            # Write back
            if not self.dry_run:
                with open(self.config_file, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False)
            
            self.logger.info(f"Config updated: current_csv = {config['current_csv']}")
            if anthro['subject_id']:
                height_str = f"{anthro['subject_height_cm']}cm" if anthro['subject_height_cm'] else "N/A"
                weight_str = f"{anthro['subject_mass_kg']}kg" if anthro['subject_mass_kg'] else "N/A"
                self.logger.info(
                    f"  Subject {anthro['subject_id']}: height={height_str} "
                    f"({anthro['subject_height_source'] or 'none'}), "
                    f"weight={weight_str} ({anthro['subject_weight_source'] or 'none'})"
                )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update config: {e}")
            return False
    
    def run_notebook(self, notebook_num: str, timeout: int = 600,
                     run_id: Optional[str] = None,
                     current_csv: Optional[str] = None) -> Dict:
        """
        Execute a single notebook using papermill.
        
        Args:
            notebook_num: Notebook number (e.g., '01', '02')
            timeout: Max execution time in seconds
            run_id: When running in batch, the current run ID (CSV stem) to inject
            current_csv: When running in batch, the current_csv path for config consistency
            
        Returns:
            Dict with status, error, execution_time
        """
        notebook_name = f"{notebook_num}_*.ipynb"
        notebooks = sorted(self.notebooks_dir.glob(notebook_name))
        
        if not notebooks:
            return {
                'status': 'error',
                'error': f'Notebook {notebook_num} not found',
                'execution_time': 0
            }
        
        # Prefer *_output.ipynb for step 04 so the notebook that writes parquet runs consistently
        if notebook_num == '04' and len(notebooks) > 1:
            output_nb = [n for n in notebooks if 'output' in n.stem.lower()]
            if output_nb:
                notebooks = output_nb + [n for n in notebooks if n not in output_nb]
        
        notebook_path = notebooks[0]
        output_path = notebook_path.parent / f"{notebook_path.stem}_output.ipynb"
        
        self.logger.info(f"Running: {notebook_path.name}")
        
        if self.dry_run:
            self.logger.info("   [DRY RUN - Skipped]")
            return {'status': 'skipped', 'error': None, 'execution_time': 0}
        
        # Inject run context so notebooks use correct RUN_ID when config is read at import time
        parameters = {}
        if run_id is not None:
            parameters['RUN_ID'] = run_id
        if current_csv is not None:
            parameters['current_csv'] = current_csv
        
        start_time = datetime.now()
        
        try:
            # Use papermill to execute notebook
            import papermill as pm
            
            # Save current directory and change to project root
            original_cwd = os.getcwd()
            os.chdir(self.project_root)
            
            try:
                pm.execute_notebook(
                    input_path=str(notebook_path),
                    output_path=str(output_path),
                    kernel_name='python3',
                    timeout=timeout,
                    progress_bar=False,
                    cwd=str(self.project_root),  # Set working directory
                    parameters=parameters if parameters else None
                )
            finally:
                # Restore original directory
                os.chdir(original_cwd)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Completed in {execution_time:.1f}s")
            
            # Cleanup output notebook (optional)
            output_path.unlink(missing_ok=True)
            
            return {
                'status': 'success',
                'error': None,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            error_msg = str(e)
            self.logger.error(f"Failed after {execution_time:.1f}s: {error_msg}")
            
            return {
                'status': 'failed',
                'error': error_msg,
                'execution_time': execution_time
            }
    
    def process_single_csv(self, csv_path: Path) -> Dict:
        """
        Process a single CSV file through the entire pipeline.
        
        Returns:
            Dict with run summary
        """
        self.logger.info("="*70)
        self.logger.info(f"Processing: {csv_path.name}")
        self.logger.info("="*70)
        
        run_summary = {
            'csv_file': str(csv_path),
            'run_id': csv_path.stem,
            'start_time': datetime.now().isoformat(),
            'notebooks': {},
            'status': 'started'
        }
        
        # Step 1: Update config
        if not self.update_config(csv_path):
            run_summary['status'] = 'failed'
            run_summary['error'] = 'Config update failed'
            return run_summary
        
        # Step 2: Run pipeline notebooks (inject run context so each notebook sees correct RUN_ID)
        data_dir = self.project_root / "data"
        try:
            current_csv_rel = str(csv_path.relative_to(data_dir)).replace('\\', '/')
        except ValueError:
            current_csv_rel = csv_path.name
        run_id = csv_path.stem
        
        total_time = 0
        all_success = True
        
        for notebook_num in self.pipeline_sequence:
            result = self.run_notebook(notebook_num, timeout=600, run_id=run_id, current_csv=current_csv_rel)
            run_summary['notebooks'][notebook_num] = result
            total_time += result['execution_time']
            
            if result['status'] == 'failed':
                all_success = False
                self.logger.warning(f"Stopping pipeline due to failure in notebook {notebook_num}")
                break
        
        # Step 3: Verify outputs
        if all_success:
            derivatives_exist = self.verify_outputs(csv_path.stem)
            run_summary['outputs_verified'] = derivatives_exist
            
            if derivatives_exist:
                run_summary['status'] = 'success'
                self.logger.info(f"Successfully processed {csv_path.name}")
            else:
                run_summary['status'] = 'partial'
                self.logger.warning(f"Pipeline completed but missing some outputs")
        else:
            run_summary['status'] = 'failed'
        
        run_summary['end_time'] = datetime.now().isoformat()
        run_summary['total_execution_time'] = total_time
        
        return run_summary
    
    def verify_outputs(self, run_id: str) -> bool:
        """Verify that all expected output files were created."""
        derivatives_dir = self.project_root / "derivatives"
        
        expected_files = [
            f"step_01_parse/{run_id}__parsed_run.parquet",
            f"step_02_preprocess/{run_id}__preprocessed.parquet",
            f"step_03_resample/{run_id}__resampled.parquet",
            f"step_04_filtering/{run_id}__filtered.parquet",
            f"step_06_kinematics/{run_id}__kinematics_master.parquet",
            f"step_06_kinematics/{run_id}__validation_report.json",
        ]
        
        all_exist = True
        for file_path in expected_files:
            full_path = derivatives_dir / file_path
            if not full_path.exists():
                self.logger.warning(f"Missing: {file_path}")
                all_exist = False
        
        return all_exist
    
    def process_batch(self, csv_files: List[Path], 
                      stop_on_error: bool = False) -> Dict:
        """
        Process multiple CSV files.
        
        Args:
            csv_files: List of CSV file paths
            stop_on_error: If True, stop entire batch on first error
            
        Returns:
            Dict with batch summary
        """
        batch_summary = {
            'total_files': len(csv_files),
            'start_time': datetime.now().isoformat(),
            'runs': [],
            'success_count': 0,
            'failed_count': 0
        }
        
        self.logger.info(f"Starting batch processing of {len(csv_files)} files")
        
        for i, csv_path in enumerate(csv_files, 1):
            self.logger.info(f"\n[{i}/{len(csv_files)}] Processing {csv_path.name}")
            
            run_result = self.process_single_csv(csv_path)
            batch_summary['runs'].append(run_result)
            
            if run_result['status'] == 'success':
                batch_summary['success_count'] += 1
            else:
                batch_summary['failed_count'] += 1
                
                if stop_on_error:
                    self.logger.error("Stopping batch due to error (stop_on_error=True)")
                    break
        
        batch_summary['end_time'] = datetime.now().isoformat()
        
        # Save batch summary
        self.save_batch_summary(batch_summary)
        
        return batch_summary
    
    def save_batch_summary(self, summary: Dict):
        """Save batch processing summary to JSON."""
        reports_dir = self.project_root / "reports"
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_file = reports_dir / f"batch_summary_{timestamp}.json"
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.logger.info(f"Batch summary saved: {summary_file}")


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description='Automated Motion Capture Pipeline Runner'
    )
    
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='Path to project root directory'
    )
    
    parser.add_argument(
        '--csv-list',
        type=str,
        help='Text file with list of CSV paths (one per line)'
    )
    
    parser.add_argument(
        '--auto-discover',
        action='store_true',
        help='Automatically discover all CSV files in data/'
    )
    
    parser.add_argument(
        '--single',
        type=str,
        help='Process a single CSV file'
    )
    
    parser.add_argument(
        '--json',
        type=str,
        default='batch_configs/subject_671_all.json',
        help='JSON file with batch configuration (default: Subject_671_All_Sessions)'
    )
    
    parser.add_argument(
        '--stop-on-error',
        action='store_true',
        help='Stop batch processing on first error'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate run without executing notebooks'
    )
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = PipelineRunner(args.project_root, dry_run=args.dry_run)
    
    # Get CSV file list
    csv_files = []
    
    if args.single:
        csv_files = [Path(args.single)]
    elif args.csv_list:
        with open(args.csv_list, 'r') as f:
            csv_files = [Path(line.strip()) for line in f if line.strip()]
    elif args.auto_discover:
        csv_files = runner.discover_csv_files()
    else:
        # Default: use JSON batch config (e.g. subject_671_all.json)
        json_path = Path(args.json)
        if not json_path.is_absolute():
            json_path = runner.project_root / args.json
        with open(json_path, 'r') as f:
            batch_config = json.load(f)
        
        data_dir = runner.project_root / "data"
        csv_files = [data_dir / csv_path for csv_path in batch_config['csv_files']]
        
        print(f"Loaded batch config: {batch_config.get('batch_name', 'Unnamed')}")
        print(f"Description: {batch_config.get('description', 'N/A')}")
    
    if not csv_files:
        print("ERROR: No CSV files found to process")
        sys.exit(1)
    
    # Run pipeline
    print(f"\nProcessing {len(csv_files)} file(s)...")
    batch_result = runner.process_batch(csv_files, stop_on_error=args.stop_on_error)
    
    # Print summary
    print("\n" + "="*70)
    print("BATCH PROCESSING COMPLETE")
    print("="*70)
    print(f"Success: {batch_result['success_count']}")
    print(f"Failed:  {batch_result['failed_count']}")
    print(f"Total:   {batch_result['total_files']}")
    print("="*70)


if __name__ == '__main__':
    main()
