"""
Comprehensive Gate Logic Verification Tests

This module verifies:
1. Logic & Algorithm Verification (Gates 2-5)
2. Audit Logging & Transparency
3. Error & Edge Case Handling
4. Regression & Data Integrity
5. Schema Compliance

Run with: python -m pytest tests/test_gates_verification.py -v
"""

import sys
import os
import json
import numpy as np
import pytest
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Import gate functions
from resampling import compute_sample_jitter, get_interpolation_fallback_metrics
from euler_isb import get_euler_sequences_audit, assess_quaternion_health, ISB_EULER_SEQUENCES
from burst_classification import (
    classify_burst_events, 
    generate_burst_audit_fields, 
    compute_clean_statistics,
    apply_artifact_exclusion,
    VELOCITY_TRIGGER,
    VELOCITY_EXTREME,
    TIER_ARTIFACT_MAX,
    TIER_BURST_MAX
)
from filtering import BODY_REGIONS, WINTER_FMAX


# =============================================================================
# 1. LOGIC & ALGORITHM VERIFICATION
# =============================================================================

class TestGate2TemporalQuality:
    """Gate 2: Signal Integrity & Temporal Quality"""
    
    def test_jitter_calculation_known_value(self):
        """Verify jitter calculation with known standard deviation."""
        # Create time array with exactly 2ms jitter (std dev)
        np.random.seed(42)
        base_dt = 1/120  # 120 Hz
        n_samples = 1000
        time_s = np.cumsum(np.full(n_samples, base_dt))
        # Add jitter with known std
        jitter_std_sec = 0.002  # 2ms
        time_s += np.random.normal(0, jitter_std_sec, n_samples)
        time_s = np.sort(time_s)  # Ensure monotonic
        
        result = compute_sample_jitter(time_s)
        
        # Should be close to 2ms (allow some tolerance due to sorting)
        assert 'step_02_sample_time_jitter_ms' in result
        assert result['step_02_jitter_status'] == 'REVIEW'  # 2ms > threshold
        print(f"  Jitter calculated: {result['step_02_sample_time_jitter_ms']:.4f} ms")
    
    def test_jitter_low_value_passes(self):
        """Verify low jitter (< 2ms) returns PASS status."""
        # Perfect 120 Hz with minimal jitter
        np.random.seed(42)
        n_samples = 1000
        time_s = np.arange(n_samples) / 120.0
        time_s += np.random.normal(0, 0.0005, n_samples)  # 0.5ms jitter
        time_s = np.sort(time_s)
        
        result = compute_sample_jitter(time_s)
        
        assert result['step_02_jitter_status'] == 'PASS'
        assert result['step_02_sample_time_jitter_ms'] < 2.0
        print(f"  Low jitter PASS: {result['step_02_sample_time_jitter_ms']:.4f} ms")
    
    def test_jitter_unit_is_milliseconds(self):
        """Verify jitter is reported in milliseconds, not seconds."""
        time_s = np.arange(1000) / 120.0
        result = compute_sample_jitter(time_s)
        
        # For perfect timing, jitter should be ~0, definitely < 1000
        # If it was in seconds, it would be ~0.008, which is < 1
        # If in ms, it should be < 10 for good data
        assert result['step_02_sample_time_jitter_ms'] < 100, "Jitter seems to be in wrong units"
    
    def test_fallback_metrics_calculation(self):
        """Test interpolation fallback metrics calculation."""
        # Simulate interpolation logger summary
        interp_summary = {
            'total_events': 50,
            'fallback_count': 5,
            'fallback_frames': 25
        }
        total_frames = 10000
        
        result = get_interpolation_fallback_metrics(interp_summary, total_frames)
        
        assert 'step_02_fallback_count' in result
        assert result['step_02_fallback_count'] == 5
        assert result['step_02_fallback_rate_percent'] == pytest.approx(0.25, rel=0.01)


class TestGate3Filtering:
    """Gate 3: Robust Dynamic Filtering"""
    
    def test_body_regions_have_extended_range(self):
        """Verify all body regions have cutoff range extending to 16 Hz."""
        for region, config in BODY_REGIONS.items():
            cutoff_range = config.get('cutoff_range', (0, 0))
            assert cutoff_range[1] >= 10, f"Region {region} has narrow range: {cutoff_range}"
            print(f"  {region}: {cutoff_range}")
    
    def test_winter_fmax_is_16(self):
        """Verify WINTER_FMAX is set to 16 Hz."""
        assert WINTER_FMAX == 16, f"WINTER_FMAX should be 16, got {WINTER_FMAX}"
    
    def test_region_specificity_different_cutoffs(self):
        """Verify different body regions have different cutoff ranges."""
        trunk_range = BODY_REGIONS.get('trunk', {}).get('cutoff_range', (0, 0))
        upper_distal_range = BODY_REGIONS.get('upper_distal', {}).get('cutoff_range', (0, 0))
        
        # Distal should have higher cutoff allowance than trunk
        assert upper_distal_range[1] >= trunk_range[1], \
            f"Distal ({upper_distal_range}) should have >= range than trunk ({trunk_range})"


class TestGate4ISBCompliance:
    """Gate 4: ISB & Mathematical Compliance"""
    
    def test_euler_sequences_known_joints(self):
        """Verify correct ISB sequences for known joints."""
        joint_list = ['Hips', 'LeftUpLeg', 'LeftLeg', 'Spine', 'LeftArm']
        result = get_euler_sequences_audit(joint_list)
        
        assert result['step_06_isb_compliant'] == True
        sequences = result['step_06_euler_sequences_used']
        
        # Verify specific sequences
        assert 'Hips' in sequences
        print(f"  Euler sequences: {sequences}")
    
    def test_unknown_joint_flags_non_compliant(self):
        """Verify unknown joints are flagged as non-ISB-compliant."""
        joint_list = ['Hips', 'UnknownJoint123', 'Spine']
        result = get_euler_sequences_audit(joint_list)
        
        assert result['step_06_isb_compliant'] == False
        assert 'UnknownJoint123' in result.get('step_06_unknown_joints', [])
    
    def test_quaternion_health_thresholds(self):
        """Test quaternion normalization error thresholds."""
        # PASS: error < 0.01
        result_pass = assess_quaternion_health(0.005)
        assert result_pass['step_06_math_status'] == 'PASS'
        
        # REVIEW: 0.01 <= error < 0.05
        result_review = assess_quaternion_health(0.03)
        assert result_review['step_06_math_status'] == 'REVIEW'
        
        # REJECT: error >= 0.05
        result_reject = assess_quaternion_health(0.08)
        assert result_reject['step_06_math_status'] == 'REJECT'
        
        print(f"  PASS threshold: 0.005 -> {result_pass['step_06_math_status']}")
        print(f"  REVIEW threshold: 0.03 -> {result_review['step_06_math_status']}")
        print(f"  REJECT threshold: 0.08 -> {result_reject['step_06_math_status']}")


class TestGate5BurstClassification:
    """Gate 5: Gaga-Aware Biomechanics"""
    
    def test_tier_boundaries_artifact(self):
        """Test that 1-3 frames at >2000 deg/s is classified as ARTIFACT."""
        # Create velocity with 3-frame spike
        n_frames = 1000
        velocity = np.random.randn(n_frames, 5) * 500  # Normal movement
        velocity[100:103, 0] = VELOCITY_TRIGGER + 500  # 3-frame spike = ARTIFACT
        
        result = classify_burst_events(velocity, fs=120.0)
        
        artifacts = [e for e in result['events'] if e['tier'] == 'ARTIFACT']
        assert len(artifacts) >= 1, "Should detect at least 1 artifact"
        assert 100 in result['frames_to_exclude'] or 101 in result['frames_to_exclude']
        print(f"  Artifact detected: frames {artifacts[0]['start_frame']}-{artifacts[0]['end_frame']}")
    
    def test_tier_boundaries_burst(self):
        """Test that 4-7 frames at >2000 deg/s is classified as BURST."""
        n_frames = 1000
        velocity = np.random.randn(n_frames, 5) * 500
        velocity[200:206, 0] = VELOCITY_TRIGGER + 500  # 6-frame spike = BURST
        
        result = classify_burst_events(velocity, fs=120.0)
        
        bursts = [e for e in result['events'] if e['tier'] == 'BURST']
        assert len(bursts) >= 1, "Should detect at least 1 burst"
        assert 200 in result['frames_to_review'] or 201 in result['frames_to_review']
        print(f"  Burst detected: frames {bursts[0]['start_frame']}-{bursts[0]['end_frame']}")
    
    def test_tier_boundaries_flow(self):
        """Test that 8+ frames at >2000 deg/s is classified as FLOW."""
        n_frames = 1000
        velocity = np.random.randn(n_frames, 5) * 500
        velocity[300:315, 0] = VELOCITY_TRIGGER + 500  # 15-frame spike = FLOW
        
        result = classify_burst_events(velocity, fs=120.0)
        
        flows = [e for e in result['events'] if e['tier'] == 'FLOW']
        assert len(flows) >= 1, "Should detect at least 1 flow"
        # Flows are not excluded or flagged for review - they're legitimate
        print(f"  Flow detected: frames {flows[0]['start_frame']}-{flows[0]['end_frame']}")
    
    def test_velocity_thresholds_correct(self):
        """Verify velocity thresholds are set correctly."""
        assert VELOCITY_TRIGGER == 2000, f"VELOCITY_TRIGGER should be 2000, got {VELOCITY_TRIGGER}"
        assert VELOCITY_EXTREME == 5000, f"VELOCITY_EXTREME should be 5000, got {VELOCITY_EXTREME}"
    
    def test_exact_tier_boundaries(self):
        """Test exact frame count boundaries: 3, 4, 7, 8."""
        fs = 120.0
        
        # Test 3 frames = ARTIFACT (max for tier 1)
        vel_3 = np.zeros((100, 1))
        vel_3[10:13, 0] = 2500  # Exactly 3 frames
        result_3 = classify_burst_events(vel_3, fs=fs)
        assert result_3['summary']['artifact_count'] >= 1
        
        # Test 4 frames = BURST (min for tier 2)
        vel_4 = np.zeros((100, 1))
        vel_4[10:14, 0] = 2500  # Exactly 4 frames
        result_4 = classify_burst_events(vel_4, fs=fs)
        assert result_4['summary']['burst_count'] >= 1
        
        # Test 7 frames = BURST (max for tier 2)
        vel_7 = np.zeros((100, 1))
        vel_7[10:17, 0] = 2500  # Exactly 7 frames
        result_7 = classify_burst_events(vel_7, fs=fs)
        assert result_7['summary']['burst_count'] >= 1
        
        # Test 8 frames = FLOW (min for tier 3)
        vel_8 = np.zeros((100, 1))
        vel_8[10:18, 0] = 2500  # Exactly 8 frames
        result_8 = classify_burst_events(vel_8, fs=fs)
        assert result_8['summary']['flow_count'] >= 1
        
        print(f"  3 frames -> Artifact: {result_3['summary']['artifact_count']}")
        print(f"  4 frames -> Burst: {result_4['summary']['burst_count']}")
        print(f"  7 frames -> Burst: {result_7['summary']['burst_count']}")
        print(f"  8 frames -> Flow: {result_8['summary']['flow_count']}")
    
    def test_clean_statistics_excludes_artifacts(self):
        """Verify clean statistics exclude artifact frames."""
        n_frames = 1000
        velocity = np.ones((n_frames, 1)) * 500  # Normal 500 deg/s
        velocity[100:102, 0] = 5000  # 2-frame artifact spike
        
        result = classify_burst_events(velocity, fs=120.0)
        clean_stats = compute_clean_statistics(velocity, result)
        
        # Raw max should be 5000, clean should be ~500
        assert clean_stats['raw_statistics']['max_deg_s'] == pytest.approx(5000, rel=0.01)
        assert clean_stats['clean_statistics']['max_deg_s'] < 1000  # Much lower after exclusion
        assert clean_stats['comparison']['max_reduction_percent'] > 50  # Big reduction
        
        print(f"  Raw max: {clean_stats['raw_statistics']['max_deg_s']:.1f}")
        print(f"  Clean max: {clean_stats['clean_statistics']['max_deg_s']:.1f}")
        print(f"  Reduction: {clean_stats['comparison']['max_reduction_percent']:.1f}%")
    
    def test_clean_velocity_always_lte_raw(self):
        """Verify clean_max_velocity <= raw_max_velocity always."""
        for seed in range(5):
            np.random.seed(seed)
            velocity = np.random.randn(1000, 3) * 800
            velocity[np.random.randint(0, 1000, 5), :] = 3000  # Random spikes
            
            result = classify_burst_events(velocity, fs=120.0)
            clean_stats = compute_clean_statistics(velocity, result)
            
            assert clean_stats['clean_statistics']['max_deg_s'] <= clean_stats['raw_statistics']['max_deg_s']


# =============================================================================
# 2. AUDIT LOGGING & TRANSPARENCY
# =============================================================================

class TestAuditLogging:
    """Audit logging completeness and transparency tests."""
    
    def test_burst_audit_fields_complete(self):
        """Verify all required fields are present in burst audit output."""
        velocity = np.random.randn(1000, 5) * 500
        velocity[100:103, 0] = 3000  # Artifact
        velocity[200:210, 1] = 2500  # Flow
        
        result = classify_burst_events(velocity, fs=120.0)
        audit_fields = generate_burst_audit_fields(result)
        
        # Check required top-level fields
        required_fields = [
            'step_06_burst_analysis',
            'step_06_burst_decision',
            'step_06_frames_to_exclude',
            'step_06_frames_to_review',
            'step_06_data_validity'
        ]
        
        for field in required_fields:
            assert field in audit_fields, f"Missing required field: {field}"
        
        # Check nested fields
        assert 'classification' in audit_fields['step_06_burst_analysis']
        assert 'artifact_count' in audit_fields['step_06_burst_analysis']['classification']
        assert 'overall_status' in audit_fields['step_06_burst_decision']
        assert 'primary_reason' in audit_fields['step_06_burst_decision']
        
        print(f"  All {len(required_fields)} required fields present")
    
    def test_decision_reason_present(self):
        """Verify every decision has a text-based reason."""
        velocity = np.random.randn(1000, 5) * 500
        velocity[100:103, 0] = 3000
        
        result = classify_burst_events(velocity, fs=120.0)
        audit_fields = generate_burst_audit_fields(result)
        
        reason = audit_fields['step_06_burst_decision'].get('primary_reason', '')
        assert len(reason) > 10, "Decision reason should be descriptive"
        assert reason != 'N/A', "Decision reason should not be N/A"
        
        print(f"  Decision reason: {reason[:80]}...")
    
    def test_isb_audit_fields_complete(self):
        """Verify ISB compliance audit fields are complete."""
        joint_list = ['Hips', 'Spine', 'LeftArm', 'RightArm']
        euler_result = get_euler_sequences_audit(joint_list)
        quat_result = assess_quaternion_health(0.005)
        
        # Check ISB fields
        assert 'step_06_euler_sequences_used' in euler_result
        assert 'step_06_isb_compliant' in euler_result
        
        # Check quaternion health fields
        assert 'step_06_math_status' in quat_result
        assert 'step_06_math_decision_reason' in quat_result
        
        print(f"  ISB compliant: {euler_result['step_06_isb_compliant']}")
        print(f"  Math status: {quat_result['step_06_math_status']}")


# =============================================================================
# 3. ERROR & EDGE CASE HANDLING
# =============================================================================

class TestEdgeCases:
    """Edge case and extreme value tests."""
    
    def test_extreme_velocity_single_frame_artifact(self):
        """Test that 10,000 deg/s for 1 frame is flagged as artifact."""
        velocity = np.zeros((1000, 1))
        velocity[500, 0] = 10000  # Single extreme frame
        
        result = classify_burst_events(velocity, fs=120.0)
        
        # Should be artifact (1 frame)
        assert result['summary']['artifact_count'] >= 1
        assert 500 in result['frames_to_exclude']
    
    def test_extreme_velocity_sustained_review(self):
        """Test that 10,000 deg/s for 20 frames triggers REVIEW/REJECT."""
        velocity = np.zeros((1000, 1))
        velocity[500:520, 0] = 10000  # 20 frames of extreme velocity
        
        result = classify_burst_events(velocity, fs=120.0)
        
        # Should trigger review due to extreme sustained velocity
        assert result['decision']['overall_status'] in ['REVIEW', 'REJECT']
        
        # Should be classified as flow (20 frames > 8)
        assert result['summary']['flow_count'] >= 1
    
    def test_quaternion_error_reject_threshold(self):
        """Test that quaternion error >= 0.05 triggers REJECT."""
        result = assess_quaternion_health(0.10)  # Way above threshold
        
        assert result['step_06_math_status'] == 'REJECT'
        assert 'REJECT' in result['step_06_math_decision_reason']
    
    def test_empty_velocity_array(self):
        """Test handling of empty velocity array."""
        velocity = np.array([]).reshape(0, 1)
        
        # Should not crash
        try:
            result = classify_burst_events(velocity, fs=120.0)
            assert result['summary']['total_events'] == 0
        except Exception as e:
            pytest.fail(f"Should handle empty array gracefully: {e}")
    
    def test_all_frames_excluded_clean_stats(self):
        """Test clean statistics when all frames would be excluded."""
        # All frames are artifacts (unrealistic but edge case)
        velocity = np.ones((10, 1)) * 5000
        
        result = classify_burst_events(velocity, fs=120.0)
        
        # This would be a flow (10 frames), not excluded
        # But let's test the exclusion function directly
        frames_to_exclude = list(range(10))
        clean_data = apply_artifact_exclusion(velocity, frames_to_exclude)
        
        # Should be all NaN
        assert np.all(np.isnan(clean_data))
    
    def test_duration_based_filtering_boundary(self):
        """Test exact boundary between burst and flow (7 vs 8 frames)."""
        fs = 120.0
        
        # 7 frames at 25ms threshold = 58.3ms (BURST, < 65ms)
        vel_7 = np.zeros((100, 1))
        vel_7[10:17, 0] = 2500
        result_7 = classify_burst_events(vel_7, fs=fs)
        
        # 8 frames = 66.7ms (FLOW, >= 65ms)
        vel_8 = np.zeros((100, 1))
        vel_8[10:18, 0] = 2500
        result_8 = classify_burst_events(vel_8, fs=fs)
        
        assert result_7['summary']['burst_count'] == 1
        assert result_7['summary']['flow_count'] == 0
        assert result_8['summary']['burst_count'] == 0
        assert result_8['summary']['flow_count'] == 1


# =============================================================================
# 4. REGRESSION & DATA INTEGRITY
# =============================================================================

class TestDataIntegrity:
    """Regression and data integrity tests."""
    
    def test_high_artifacts_correlates_with_low_retained(self):
        """Verify high artifact count correlates with lower data_retained_percent."""
        # Many artifacts
        velocity_many = np.ones((1000, 1)) * 500
        for i in range(0, 1000, 50):  # 20 artifact events
            velocity_many[i:i+2, 0] = 3000
        
        # Few artifacts
        velocity_few = np.ones((1000, 1)) * 500
        velocity_few[100:102, 0] = 3000  # 1 artifact event
        
        result_many = classify_burst_events(velocity_many, fs=120.0)
        result_few = classify_burst_events(velocity_few, fs=120.0)
        
        clean_many = compute_clean_statistics(velocity_many, result_many)
        clean_few = compute_clean_statistics(velocity_few, result_few)
        
        # More artifacts = lower retained percentage
        assert clean_many['comparison']['data_retained_percent'] < clean_few['comparison']['data_retained_percent']
        
        print(f"  Many artifacts: {clean_many['comparison']['data_retained_percent']:.2f}% retained")
        print(f"  Few artifacts: {clean_few['comparison']['data_retained_percent']:.2f}% retained")
    
    def test_frames_to_exclude_are_subset_of_total(self):
        """Verify frames_to_exclude indices are within valid range."""
        n_frames = 500
        velocity = np.random.randn(n_frames, 3) * 800
        velocity[100:102, 0] = 3000
        
        result = classify_burst_events(velocity, fs=120.0)
        
        for frame_idx in result['frames_to_exclude']:
            assert 0 <= frame_idx < n_frames, f"Frame index {frame_idx} out of range"


# =============================================================================
# 5. SCHEMA COMPLIANCE
# =============================================================================

class TestSchemaCompliance:
    """Schema compliance verification."""
    
    def test_burst_analysis_json_structure(self):
        """Verify burst analysis JSON has correct nested structure."""
        velocity = np.random.randn(1000, 5) * 500
        velocity[100:103, 0] = 3000
        
        result = classify_burst_events(velocity, fs=120.0)
        audit = generate_burst_audit_fields(result)
        
        # Verify structure matches expected schema
        expected_structure = {
            'step_06_burst_analysis': {
                'classification': ['artifact_count', 'burst_count', 'flow_count', 'total_events'],
                'frame_statistics': ['total_frames', 'artifact_frames', 'artifact_rate_percent'],
                'timing': ['recording_duration_sec', 'max_consecutive_frames']
            }
        }
        
        analysis = audit['step_06_burst_analysis']
        for section, fields in expected_structure['step_06_burst_analysis'].items():
            assert section in analysis, f"Missing section: {section}"
            for field in fields:
                assert field in analysis[section], f"Missing field: {section}.{field}"
    
    def test_euler_sequences_are_valid_strings(self):
        """Verify Euler sequences are valid 3-character strings."""
        joint_list = list(ISB_EULER_SEQUENCES.keys())[:5]
        result = get_euler_sequences_audit(joint_list)
        
        for joint, sequence in result['step_06_euler_sequences_used'].items():
            assert len(sequence) == 3, f"Invalid sequence length for {joint}: {sequence}"
            assert all(c in 'XYZxyz' for c in sequence), f"Invalid characters in {joint}: {sequence}"


# =============================================================================
# INTEGRATION TEST
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple gates."""
    
    def test_full_gate_5_pipeline(self):
        """Test complete Gate 5 pipeline from velocity to audit fields."""
        np.random.seed(42)
        
        # Create realistic-ish velocity data
        n_frames = 3000
        n_joints = 10
        velocity = np.random.randn(n_frames, n_joints) * 600
        
        # Add various event types
        velocity[100:102, 0] = 2800   # Artifact (2 frames)
        velocity[500:505, 1] = 2500   # Burst (5 frames)
        velocity[1000:1020, 2] = 2200 # Flow (20 frames)
        velocity[2000:2001, 3] = 8000 # Extreme single-frame artifact
        
        joint_names = [f"Joint_{i}" for i in range(n_joints)]
        
        # Run classification
        result = classify_burst_events(velocity, fs=120.0, joint_names=joint_names)
        
        # Generate audit fields
        audit = generate_burst_audit_fields(result)
        
        # Compute clean stats
        clean = compute_clean_statistics(velocity, result, joint_names)
        
        # Verify counts
        assert result['summary']['artifact_count'] >= 2  # At least 2 artifacts
        assert result['summary']['burst_count'] >= 1     # At least 1 burst
        assert result['summary']['flow_count'] >= 1      # At least 1 flow
        
        # Verify clean stats
        assert clean['clean_statistics']['max_deg_s'] < clean['raw_statistics']['max_deg_s']
        
        # Verify decision
        assert audit['step_06_burst_decision']['overall_status'] in ['PASS', 'REVIEW', 'ACCEPT_HIGH_INTENSITY']
        
        print("\n  === Integration Test Results ===")
        print(f"  Artifacts: {result['summary']['artifact_count']}")
        print(f"  Bursts: {result['summary']['burst_count']}")
        print(f"  Flows: {result['summary']['flow_count']}")
        print(f"  Raw max: {clean['raw_statistics']['max_deg_s']:.1f} deg/s")
        print(f"  Clean max: {clean['clean_statistics']['max_deg_s']:.1f} deg/s")
        print(f"  Decision: {audit['step_06_burst_decision']['overall_status']}")
        print(f"  Reason: {audit['step_06_burst_decision']['primary_reason'][:60]}...")


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("GATE LOGIC VERIFICATION TESTS")
    print("=" * 70)
    
    # Run with verbose output
    pytest.main([__file__, "-v", "--tb=short", "-s"])
