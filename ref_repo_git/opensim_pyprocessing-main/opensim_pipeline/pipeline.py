"""Pipeline orchestrator: runs the full biomechanical processing pipeline."""

from __future__ import annotations

import argparse
import logging
import sys

from opensim_pipeline.c3d_export import export_c3d_to_trc_and_mot
from opensim_pipeline.center_of_mass import compute_com
from opensim_pipeline.config import PipelineConfig, load_config
from opensim_pipeline.inverse_dynamics import run_id
from opensim_pipeline.inverse_kinematics import run_ik
from opensim_pipeline.scaling import run_scaling

logger = logging.getLogger(__name__)


def run_pipeline(cfg: PipelineConfig) -> None:
    """Execute the biomechanical processing pipeline.

    Parameters
    ----------
    cfg : PipelineConfig
        Loaded and validated pipeline configuration.
    """
    cfg.output_folder.mkdir(parents=True, exist_ok=True)

    # --- C3D export ---
    if cfg.steps.get("c3d_export"):
        c3d_files = sorted(cfg.c3d_folder.glob("*.c3d"))
        logger.info("C3D export: %d files found in %s", len(c3d_files), cfg.c3d_folder)

        for c3d_file in c3d_files:
            logger.info("  Processing: %s", c3d_file.name)
            try:
                result = export_c3d_to_trc_and_mot(
                    c3d_file,
                    output_dir=cfg.output_folder,
                    lab_to_opensim_transform=cfg.coordinate_transform,
                    max_missing_samples=cfg.fill_gaps_max_missing_samples,
                )
                logger.info("    TRC: %s", result["trc_file"])
                if "mot_file" in result:
                    logger.info("    MOT: %s", result["mot_file"])
                else:
                    logger.info("    No forces data (TRC only)")
            except Exception as e:
                logger.error("    Error: %s", e)

    # --- Scaling ---
    if cfg.steps.get("scaling"):
        static_trc_files = list(
            cfg.output_folder.glob(f"{cfg.static_pattern}.trc")
        )
        if static_trc_files:
            static_trc_file = static_trc_files[0]
            scaled_model_file = cfg.output_folder / "scaled_model.osim"

            logger.info("Scaling with static trial: %s", static_trc_file.name)
            try:
                result = run_scaling(
                    static_trc_file=static_trc_file,
                    model_file=cfg.generic_model,
                    output_model_file=scaled_model_file,
                    measurements_tsv=cfg.scaling_measurements_tsv,
                    ik_weights_tsv=cfg.ik_marker_weights_tsv,
                    subject_mass=cfg.subject_mass,
                )
                logger.info("  Scaled model: %s", result)
            except Exception as e:
                logger.error("  Scaling error: %s", e)
        else:
            logger.warning(
                "No static trial found (pattern: '%s'). Skipping scaling.",
                cfg.static_pattern,
            )

    # --- Inverse kinematics ---
    if cfg.steps.get("inverse_kinematics"):
        trc_files = [
            f
            for f in cfg.output_folder.glob("*.trc")
            if not f.match(cfg.static_pattern + ".trc")
        ]
        scaled_model = cfg.output_folder / "scaled_model.osim"

        if not scaled_model.exists():
            logger.error("Scaled model not found. Run scaling first.")
        elif not trc_files:
            logger.warning("No TRC files found for IK (excluding static trials).")
        else:
            logger.info("IK: %d TRC files", len(trc_files))
            for trc_file in sorted(trc_files):
                logger.info("  Processing: %s", trc_file.name)
                try:
                    result = run_ik(
                        trc_file=trc_file,
                        model_file=scaled_model,
                        ik_weights_tsv=cfg.ik_marker_weights_tsv,
                        output_dir=cfg.output_folder,
                    )
                    logger.info("    IK result: %s", result)
                except Exception as e:
                    logger.error("    IK error: %s", e)

    # --- Inverse dynamics ---
    if cfg.steps.get("inverse_dynamics"):
        ik_files = list(cfg.output_folder.glob("*_ik.mot"))
        scaled_model = cfg.output_folder / "scaled_model.osim"

        if not scaled_model.exists():
            logger.error("Scaled model not found. Run scaling first.")
        elif not ik_files:
            logger.warning("No IK result files found. Run IK first.")
        else:
            logger.info("ID: %d IK files", len(ik_files))
            for ik_file in sorted(ik_files):
                base_name = ik_file.stem.replace("_ik", "")
                grf_file = cfg.output_folder / f"{base_name}.mot"

                if not grf_file.exists():
                    logger.warning(
                        "  Skipping %s: no GRF file (%s)", ik_file.name, grf_file.name
                    )
                    continue

                logger.info("  Processing: %s", ik_file.name)
                try:
                    result = run_id(
                        ik_mot_file=ik_file,
                        model_file=scaled_model,
                        grf_mot_file=grf_file,
                        external_loads_tsv=cfg.external_loads_tsv,
                        output_dir=cfg.output_folder,
                        low_pass_cutoff=cfg.id_low_pass_cutoff,
                    )
                    logger.info("    ID result: %s", result)
                except Exception as e:
                    logger.error("    ID error: %s", e)

    # --- Center of mass ---
    if cfg.steps.get("center_of_mass"):
        ik_files = list(cfg.output_folder.glob("*_ik.mot"))
        scaled_model = cfg.output_folder / "scaled_model.osim"

        if not scaled_model.exists():
            logger.error("Scaled model not found. Run scaling first.")
        elif not ik_files:
            logger.warning("No IK result files found. Run IK first.")
        else:
            logger.info("COM: %d IK files", len(ik_files))
            for ik_file in sorted(ik_files):
                logger.info("  Processing: %s", ik_file.name)
                try:
                    result = compute_com(
                        model_file=scaled_model,
                        ik_mot_file=ik_file,
                        output_dir=cfg.output_folder,
                    )
                    logger.info("    COM result: %s", result)
                except Exception as e:
                    logger.error("    COM error: %s", e)

    logger.info("Pipeline complete.")


def main() -> None:
    """CLI entry point: parse arguments, load config, and run the pipeline."""
    parser = argparse.ArgumentParser(
        description="OpenSim biomechanical processing pipeline.",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s  %(message)s",
    )

    cfg = load_config(args.config)
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
