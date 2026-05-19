#!/usr/bin/env python3
"""
Quick test script to verify pipeline automation setup.
Run this before your first batch processing run.
"""

import sys
from pathlib import Path

def test_setup():
    """Test that all required components are in place."""
    
    print("🔍 Testing Pipeline Automation Setup...\n")
    
    all_good = True
    
    # Test 1: Check required files
    print("1️⃣ Checking required files...")
    required_files = [
        'run_pipeline.py',
        'config/config_v1.yaml',
        'notebooks/01_Load_Inspect.ipynb',
        'notebooks/02_preprocess.ipynb',
        'notebooks/03_resample.ipynb',
        'notebooks/04_filtering.ipynb',
        'notebooks/05_reference_detection.ipynb',
        'notebooks/06_rotvec_omega.ipynb',
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ Missing: {file_path}")
            all_good = False
    
    # Test 2: Check Python dependencies
    print("\n2️⃣ Checking Python dependencies...")
    required_packages = [
        ('papermill', 'papermill'),
        ('yaml', 'pyyaml'),
        ('pandas', 'pandas'),
        ('numpy', 'numpy'),
        ('scipy', 'scipy'),
    ]
    
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print(f"   ✅ {package_name}")
        except ImportError:
            print(f"   ❌ Missing: {package_name} (install with: pip install {package_name})")
            all_good = False
    
    # Test 3: Check data directory
    print("\n3️⃣ Checking data directory...")
    data_dir = Path('data')
    if data_dir.exists():
        csv_files = list(data_dir.glob('**/*.csv'))
        print(f"   ✅ data/ directory exists")
        print(f"   📁 Found {len(csv_files)} CSV files")
        if csv_files:
            print(f"   Example: {csv_files[0]}")
    else:
        print(f"   ⚠️  data/ directory not found (create it if needed)")
    
    # Test 4: Check output directories
    print("\n4️⃣ Checking/creating output directories...")
    output_dirs = ['logs', 'reports', 'derivatives', 'qc']
    for dir_name in output_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"   ✅ {dir_name}/")
        else:
            dir_path.mkdir(exist_ok=True)
            print(f"   ✨ Created {dir_name}/")
    
    # Test 5: Test config.yaml loading
    print("\n5️⃣ Testing config.yaml...")
    try:
        import yaml
        with open('config/config_v1.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        if 'current_csv' in config:
            print(f"   ✅ Config loaded successfully")
            print(f"   📄 Current CSV: {config['current_csv']}")
        else:
            print(f"   ⚠️  'current_csv' not found in config")
            all_good = False
    except Exception as e:
        print(f"   ❌ Error loading config: {e}")
        all_good = False
    
    # Summary
    print("\n" + "="*60)
    if all_good:
        print("✅ ALL TESTS PASSED - Ready to run pipeline!")
        print("\nNext steps:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Test run: python run_pipeline.py --dry-run --auto-discover")
        print("  3. Full run: python run_pipeline.py --auto-discover")
    else:
        print("⚠️  SOME ISSUES FOUND - Please fix before running pipeline")
        print("\nTo install missing dependencies:")
        print("  pip install -r requirements.txt")
    print("="*60)
    
    return all_good


if __name__ == '__main__':
    success = test_setup()
    sys.exit(0 if success else 1)
