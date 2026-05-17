"""Entry point for the OpenSim processing pipeline.

Usage:
    python run_pipeline.py --config config.yaml
    python run_pipeline.py --config example/example_config.yaml --verbose
"""

from opensim_pipeline.pipeline import main

if __name__ == "__main__":
    main()
