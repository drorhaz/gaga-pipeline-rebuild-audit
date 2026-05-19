"""
Motion capture preprocessing modules.

Gate System:
- Gate 2: Signal Integrity (resampling.py)
- Gate 3: Dynamic Filtering (filtering.py)
- Gate 4: ISB Compliance (euler_isb.py)
- Gate 5: Burst Classification (burst_classification.py)
"""

from .artifacts import (
    detect_velocity_artifacts,
    expand_artifact_mask,
    compute_true_velocity,
    apply_artifact_truncation
)

from .time_alignment import (
    generate_perfect_time_grid,
    ensure_hemispheric_alignment,
    precise_temporal_resampling,
    resample_positions,
    resample_quaternions,
    verify_resampling_quality
)

# Gate 2: Signal Integrity & Temporal Quality
from .resampling import (
    compute_sample_jitter,
    get_interpolation_fallback_metrics,
    estimate_fs
)

# Gate 3: Dynamic Filtering (imported from filtering.py when needed)
# Gate 4: ISB Compliance
from .euler_isb import (
    get_euler_sequences_audit,
    assess_quaternion_health,
    get_euler_sequence,
    ISB_EULER_SEQUENCES
)

# Gate 5: Burst Classification
from .burst_classification import (
    classify_burst_events,
    generate_burst_audit_fields,
    create_joint_status_dataframe,
    apply_artifact_exclusion,
    compute_clean_statistics,
    VELOCITY_TRIGGER,
    VELOCITY_EXTREME
)

# Gate Integration (combines all gates)
from .gate_integration import (
    run_gate_2,
    run_gate_3,
    run_gate_4,
    run_gate_5,
    run_all_gates,
    get_overall_decision,
    print_gate_summary
)
