#!/usr/bin/env python3
"""
Batch Configuration Generator
Auto-generates JSON configuration files for pipeline batch processing.

Usage:
    python generate_batch_config.py --subject 734
    python generate_batch_config.py --subject 734 --session T1
    python generate_batch_config.py --all
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime


def find_csv_files(data_dir: Path, subject: str = None, session: str = None):
    """
    Find CSV files in the data directory.
    
    Args:
        data_dir: Path to data directory
        subject: Subject ID (e.g., '734', '763') or None for all
        session: Session ID (e.g., 'T1', 'T2') or None for all
    
    Returns:
        List of CSV file paths relative to data_dir
    """
    csv_files = []
    
    if subject:
        # Search in specific subject folder
        subject_dir = data_dir / subject
        if not subject_dir.exists():
            print(f"⚠️  Warning: Subject directory not found: {subject_dir}")
            return []
        
        if session:
            # Search in specific session folder
            search_pattern = f"{subject}/{session}/*.csv"
        else:
            # Search in all sessions
            search_pattern = f"{subject}/*/*.csv"
    else:
        # Search everywhere
        search_pattern = "**/*.csv"
    
    for csv_path in data_dir.glob(search_pattern):
        # Get relative path from data directory
        relative_path = csv_path.relative_to(data_dir)
        # Convert to forward slashes for cross-platform compatibility
        csv_files.append(str(relative_path).replace('\\', '/'))
    
    return sorted(csv_files)


def create_batch_config(csv_files: list, name: str, description: str) -> dict:
    """Create a batch configuration dictionary."""
    return {
        "batch_name": name,
        "description": description,
        "created_date": datetime.now().strftime('%Y-%m-%d'),
        "csv_files": csv_files,
        "total_files": len(csv_files),
        "notes": f"Use with: python run_pipeline.py --json batch_configs/{name}.json"
    }


def save_batch_config(config: dict, output_dir: Path, filename: str):
    """Save batch configuration to JSON file."""
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / filename
    
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Created: {output_path}")
    print(f"   Files: {config['total_files']}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate batch configuration JSON files for pipeline processing'
    )
    
    parser.add_argument(
        '--subject',
        type=str,
        help='Subject ID (e.g., 734, 763)'
    )
    
    parser.add_argument(
        '--session',
        type=str,
        help='Session ID (e.g., T1, T2) - only used with --subject'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Generate configs for all subjects found in data/'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='batch_configs',
        help='Output directory for JSON files (default: batch_configs/)'
    )
    
    parser.add_argument(
        '--project-root',
        type=str,
        default='.',
        help='Path to project root directory'
    )
    
    args = parser.parse_args()
    
    project_root = Path(args.project_root)
    data_dir = project_root / "data"
    output_dir = project_root / args.output_dir
    
    if not data_dir.exists():
        print(f"❌ Error: Data directory not found: {data_dir}")
        return
    
    print(f"🔍 Scanning data directory: {data_dir}\n")
    
    if args.all:
        # Generate configs for all subjects
        subjects = [d.name for d in data_dir.iterdir() if d.is_dir() and d.name.isdigit()]
        
        if not subjects:
            print("❌ No subject directories found in data/")
            return
        
        print(f"Found subjects: {', '.join(subjects)}\n")
        
        for subject in subjects:
            # All sessions for this subject
            csv_files = find_csv_files(data_dir, subject=subject)
            if csv_files:
                config = create_batch_config(
                    csv_files,
                    name=f"subject_{subject}_all",
                    description=f"All CSV files for subject {subject}"
                )
                save_batch_config(config, output_dir, f"subject_{subject}_all.json")
            
            # Per-session configs
            subject_dir = data_dir / subject
            sessions = [d.name for d in subject_dir.iterdir() if d.is_dir()]
            
            for session in sessions:
                csv_files = find_csv_files(data_dir, subject=subject, session=session)
                if csv_files:
                    config = create_batch_config(
                        csv_files,
                        name=f"subject_{subject}_{session}_only",
                        description=f"CSV files for subject {subject}, {session} session only"
                    )
                    save_batch_config(config, output_dir, f"subject_{subject}_{session}_only.json")
        
        # All files config
        all_csv_files = find_csv_files(data_dir)
        if all_csv_files:
            config = create_batch_config(
                all_csv_files,
                name="all_subjects_all_sessions",
                description="All CSV files from all subjects and sessions"
            )
            save_batch_config(config, output_dir, "all_subjects_all_sessions.json")
    
    elif args.subject:
        if args.session:
            # Specific subject and session
            csv_files = find_csv_files(data_dir, subject=args.subject, session=args.session)
            if csv_files:
                config = create_batch_config(
                    csv_files,
                    name=f"subject_{args.subject}_{args.session}_only",
                    description=f"CSV files for subject {args.subject}, {args.session} session only"
                )
                save_batch_config(config, output_dir, f"subject_{args.subject}_{args.session}_only.json")
            else:
                print(f"❌ No CSV files found for subject {args.subject}, session {args.session}")
        else:
            # All sessions for specific subject
            csv_files = find_csv_files(data_dir, subject=args.subject)
            if csv_files:
                config = create_batch_config(
                    csv_files,
                    name=f"subject_{args.subject}_all",
                    description=f"All CSV files for subject {args.subject}"
                )
                save_batch_config(config, output_dir, f"subject_{args.subject}_all.json")
            else:
                print(f"❌ No CSV files found for subject {args.subject}")
    
    else:
        parser.print_help()
        return
    
    print(f"\n📁 Batch configurations saved to: {output_dir}/")
    print(f"\n🚀 Usage example:")
    print(f"   python run_pipeline.py --json {output_dir}/subject_{args.subject or '734'}_all.json")


if __name__ == '__main__':
    main()
