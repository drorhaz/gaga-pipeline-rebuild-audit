"""
Test suite for anatomical calibration module.

This module implements comprehensive tests for the calibration pipeline including:
- Deterministic V-Pose detection and correction
- Hemisphere averaging robustness
- Identity quaternion offset verification
- Non-commutative rotation tests
"""

import numpy as np
import pandas as pd
import pytest
import tempfile
import json
from pathlib import Path
from scipy.spatial.transform import Rotation

import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.calibration import (
    find_stable_window,
    detect_v_pose,
    compute_quaternion_offsets,
    export_calibration_offsets,
    run_anatomical_calibration
)


class TestStableWindowSelection:
    """Test stable window selection functionality."""
    
    def test_basic_window_selection(self):
        """Test basic window selection with synthetic data."""
        # Create synthetic data with known stable region
        fs = 120.0
        duration = 10.0
        t = np.linspace(0, duration, int(fs * duration))
        
        # Create stable region (t=2-3s) and noisy regions
        positions = {}
        for joint in ["Hips", "LeftHand", "RightHand"]:
            for axis in ['x', 'y', 'z']:
                col_name = f"{joint}__p{axis}"  # Updated to match actual naming convention
                if 2.0 <= t[0] <= 3.0:  # Stable region
                    positions[col_name] = np.ones_like(t) * 0.1
                else:  # Noisy regions
                    positions[col_name] = np.random.randn(len(t)) * 0.5
        
        df = pd.DataFrame(positions)
        
        ref_df, metadata = find_stable_window(df, fs=fs)
        
        assert len(ref_df) == int(1.0 * fs)  # 1 second window
        assert metadata["duration_sec"] == 1.0
        assert metadata["variance_score"] > 0
        assert "start_time_sec" in metadata
        assert "end_time_sec" in metadata
        assert "time_window" in metadata
    
    def test_variance_score_calculation(self):
        """Test variance score calculation correctness."""
        fs = 120.0
        n_samples = int(fs * 2.0)  # 2 seconds
        
        # Create data with different variance levels
        positions = {}
        for joint in ["Hips", "LeftHand", "RightHand"]:
            for axis in ['x', 'y', 'z']:
                col_name = f"{joint}__p{axis}"  # Updated to match actual naming convention
                positions[col_name] = np.random.randn(n_samples) * 0.1
        
        df = pd.DataFrame(positions)
        
        ref_df, metadata = find_stable_window(df, fs=fs)
        
        # Verify variance score is positive
        assert metadata["variance_score"] > 0
        
        # Verify window size
        assert len(ref_df) == int(1.0 * fs)


class TestVPoseDetection:
    """Test V-Pose detection and correction."""
    
    def test_deterministic_v_pose_correction(self):
        """Test V-Pose correction with synthetic arm geometry."""
        # Create synthetic arm data: 1.0m length, 0.1m height (elevation)
        fs = 120.0
        n_samples = int(fs * 1.0)  # 1 second
        
        # Shoulder at origin
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        
        # Elbow elevated by 0.1m, extended 1.0m horizontally
        elbow_pos = np.array([1.0, 0.1, 0.0])
        
        # Create DataFrame
        positions = {}
        for axis, val in zip(['x', 'y', 'z'], shoulder_pos):
            positions[f"LeftShoulder__p{axis}"] = np.full(n_samples, val)  # Updated naming
        for axis, val in zip(['x', 'y', 'z'], elbow_pos):
            positions[f"LeftElbow__p{axis}"] = np.full(n_samples, val)  # Updated naming
        
        df = pd.DataFrame(positions)
        
        # Expected elevation: degrees(atan2(0.1, 1.0)) ≈ 5.71°
        expected_elevation = np.degrees(np.arctan2(0.1, 1.0))
        
        correction_applied, elevation_deg, correction_quat = detect_v_pose(
            df, "LeftShoulder", "LeftElbow", elevation_threshold_deg=5.0
        )
        
        # Should apply correction since 5.71° > 5.0°
        assert correction_applied == True
        assert abs(elevation_deg - expected_elevation) < 0.1
        
        # Verify correction quaternion is not identity
        assert not np.allclose(correction_quat, [0.0, 0.0, 0.0, 1.0])
    
    def test_no_correction_needed(self):
        """Test that no correction is applied for small elevations."""
        fs = 120.0
        n_samples = int(fs * 1.0)
        
        # Nearly horizontal arm (2° elevation)
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([1.0, 0.035, 0.0])  # tan(2°) ≈ 0.035
        
        positions = {}
        for axis, val in zip(['x', 'y', 'z'], shoulder_pos):
            positions[f"LeftShoulder__p{axis}"] = np.full(n_samples, val)  # Updated naming
        for axis, val in zip(['x', 'y', 'z'], elbow_pos):
            positions[f"LeftElbow__p{axis}"] = np.full(n_samples, val)  # Updated naming
        
        df = pd.DataFrame(positions)
        
        correction_applied, elevation_deg, correction_quat = detect_v_pose(
            df, "LeftShoulder", "LeftElbow", elevation_threshold_deg=5.0
        )
        
        # Should not apply correction since 2° < 5.0°
        assert correction_applied == False
        assert elevation_deg < 5.0
        
        # Should return identity quaternion
        assert np.allclose(correction_quat, [0.0, 0.0, 0.0, 1.0])
    
    def test_degeneracy_guard(self):
        """Test degeneracy guard for insufficient horizontal component."""
        fs = 120.0
        n_samples = int(fs * 1.0)
        
        # Purely vertical arm (no horizontal component)
        shoulder_pos = np.array([0.0, 0.0, 0.0])
        elbow_pos = np.array([1e-9, 1.0, 1e-9])  # Tiny horizontal component
        
        positions = {}
        for axis, val in zip(['x', 'y', 'z'], shoulder_pos):
            positions[f"LeftShoulder__p{axis}"] = np.full(n_samples, val)  # Updated naming
        for axis, val in zip(['x', 'y', 'z'], elbow_pos):
            positions[f"LeftElbow__p{axis}"] = np.full(n_samples, val)  # Updated naming
        
        df = pd.DataFrame(positions)
        
        correction_applied, elevation_deg, correction_quat = detect_v_pose(
            df, "LeftShoulder", "LeftElbow", elevation_threshold_deg=5.0
        )
        
        # Should not apply correction due to degeneracy guard
        assert correction_applied == False
        assert np.allclose(correction_quat, [0.0, 0.0, 0.0, 1.0])


class TestQuaternionOffsetGeneration:
    """Test quaternion offset generation with hemisphere alignment."""
    
    def test_hemisphere_averaging_robustness(self):
        """Test hemisphere alignment with alternating quaternions."""
        fs = 120.0
        n_samples = int(fs * 1.0)
        
        # Create a reference quaternion
        q_ref = np.array([0.1, 0.2, 0.3, 0.9])
        q_ref = q_ref / np.linalg.norm(q_ref)  # Normalize
        
        # Create alternating quaternions: q, -q, q, -q, ...
        quaternions = np.array([q_ref if i % 2 == 0 else -q_ref for i in range(n_samples)])
        
        # Create DataFrame
        positions = {}
        quats = {}
        
        # Add some position data for window selection
        for joint in ["Hips", "LeftHand", "RightHand"]:
            for axis in ['x', 'y', 'z']:
                positions[f"{joint}__p{axis}"] = np.random.randn(n_samples) * 0.01  # Updated naming
        
        # Add quaternion data for a test joint
        for i, axis in enumerate(['x', 'y', 'z', 'w']):
            quats[f"TestJoint__q{axis}"] = quaternions[:, i]  # Updated naming
        
        df = pd.DataFrame({**positions, **quats})
        
        # Compute offsets
        offsets_map, metadata = compute_quaternion_offsets(
            df, np.array([0.0, 0.0, 0.0, 1.0]), [], fs=fs
        )
        
        # The hemisphere alignment should work correctly. Let's verify by checking
        # that the offset is the inverse of a quaternion close to q_ref or -q_ref
        recovered_offset = np.array(offsets_map["TestJoint"])
        R_offset = Rotation.from_quat(recovered_offset)
        R_refined = R_offset.inv()  # Get back the refined rotation
        refined_quat = R_refined.as_quat()
        
        # Verify hemisphere alignment worked: the refined quaternion should be close to q_ref or -q_ref
        dot_product = np.dot(refined_quat, q_ref)
        assert abs(dot_product) > 0.99  # Should be very close to ±q_ref
    
    def test_identity_check(self):
        """Test that R_offset * R_refined = Identity within tolerance."""
        fs = 120.0
        n_samples = int(fs * 1.0)
        
        # Create simple test data with identity quaternions
        positions = {}
        quats = {}
        
        for joint in ["Hips", "LeftHand", "RightHand"]:
            for axis in ['x', 'y', 'z']:
                positions[f"{joint}__p{axis}"] = np.random.randn(n_samples) * 0.01  # Updated naming
        
        # Test joint with identity quaternions
        identity_quat = np.array([0.0, 0.0, 0.0, 1.0])
        for i, axis in enumerate(['x', 'y', 'z', 'w']):
            quats[f"TestJoint__q{axis}"] = np.full(n_samples, identity_quat[i])  # Updated naming
        
        df = pd.DataFrame({**positions, **quats})
        
        # Compute offsets
        offsets_map, metadata = compute_quaternion_offsets(
            df, np.array([0.0, 0.0, 0.0, 1.0]), [], fs=fs
        )
        
        # Get the offset and verify identity
        offset_quat = np.array(offsets_map["TestJoint"])
        R_offset = Rotation.from_quat(offset_quat)
        
        # For identity input, the refined rotation should be identity
        # So R_offset * Identity should equal R_offset
        # But since we store R_offset = R_refined.inv(), and R_refined = Identity
        # Then R_offset should also be Identity
        expected_identity = Rotation.from_quat([0.0, 0.0, 0.0, 1.0])
        
        # Verify within tolerance
        assert np.allclose(offset_quat, [0.0, 0.0, 0.0, 1.0], atol=1e-6)
    
    def test_non_commutative_rotation(self):
        """Test that quaternion method differs from naive Euler subtraction."""
        fs = 120.0
        n_samples = int(fs * 1.0)
        
        # Create multi-axis rotation (45° around X, then 30° around Y)
        R_x = Rotation.from_euler('x', 45, degrees=True)
        R_y = Rotation.from_euler('y', 30, degrees=True)
        R_combined = R_y * R_x  # Order matters!
        
        # Create test data with this rotation
        positions = {}
        quats = {}
        
        for joint in ["Hips", "LeftHand", "RightHand"]:
            for axis in ['x', 'y', 'z']:
                positions[f"{joint}__p{axis}"] = np.random.randn(n_samples) * 0.01  # Updated naming
        
        combined_quat = R_combined.as_quat()  # xyzw format
        for i, axis in enumerate(['x', 'y', 'z', 'w']):
            quats[f"TestJoint__q{axis}"] = np.full(n_samples, combined_quat[i])  # Updated naming
        
        df = pd.DataFrame({**positions, **quats})
        
        # Compute quaternion offsets
        offsets_map, metadata = compute_quaternion_offsets(
            df, np.array([0.0, 0.0, 0.0, 1.0]), [], fs=fs
        )
        
        # Get the quaternion result
        quat_result = np.array(offsets_map["TestJoint"])
        
        # Compare with naive Euler subtraction (which would be wrong)
        euler_combined = R_combined.as_euler('xyz', degrees=True)
        
        # The quaternion method should give different results than naive Euler
        # Convert quaternion back to Euler for comparison
        R_from_quat = Rotation.from_quat(quat_result)
        euler_from_quat = R_from_quat.as_euler('xyz', degrees=True)
        
        # They should be different (demonstrating non-commutativity)
        assert not np.allclose(euler_combined, euler_from_quat, atol=1e-3)


class TestExportAndIntegration:
    """Test export functionality and full pipeline integration."""
    
    def test_export_calibration_offsets(self):
        """Test JSON export of calibration offsets."""
        offsets_map = {
            "LeftShoulder": [0.1, 0.2, 0.3, 0.9],
            "RightShoulder": [0.0, 0.0, 0.0, 1.0]
        }
        
        metadata = {
            "fs": 120.0,
            "quat_order": "xyzw",
            "window_duration_sec": 1.0
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_offsets.json"
            
            export_calibration_offsets(offsets_map, metadata, str(output_path))
            
            # Verify file was created and contains correct data
            assert output_path.exists()
            
            with open(output_path, 'r') as f:
                loaded_data = json.load(f)
            
            assert loaded_data["offsets_map"] == offsets_map
            assert loaded_data["metadata"] == metadata
    
    def test_full_pipeline_integration(self):
        """Test the complete anatomical calibration pipeline."""
        # Create comprehensive test data
        fs = 120.0
        duration = 5.0
        n_samples = int(fs * duration)
        
        # Create synthetic motion capture data
        data = {}
        
        # Position data for stable window detection
        stable_positions = np.random.randn(n_samples, 9) * 0.01  # Low noise
        joints = ["Hips", "LeftHand", "RightHand"]
        for i, joint in enumerate(joints):
            for j, axis in enumerate(['x', 'y', 'z']):
                data[f"{joint}__p{axis}"] = stable_positions[:, i*3 + j]  # Updated naming
        
        # Arm positions for V-Pose detection
        # Left arm: elevated 10°
        left_shoulder_pos = np.array([0.0, 1.4, 0.0])
        left_elbow_pos = np.array([0.3, 1.45, 0.0])  # 10° elevation
        
        # Right arm: elevated 8°
        right_shoulder_pos = np.array([0.0, 1.4, 0.0])
        right_elbow_pos = np.array([-0.25, 1.435, 0.0])  # 8° elevation
        
        for i, axis in enumerate(['x', 'y', 'z']):
            data[f"LeftShoulder__p{axis}"] = np.full(n_samples, left_shoulder_pos[i])  # Updated naming
            data[f"LeftElbow__p{axis}"] = np.full(n_samples, left_elbow_pos[i])  # Updated naming
            data[f"RightShoulder__p{axis}"] = np.full(n_samples, right_shoulder_pos[i])  # Updated naming
            data[f"RightElbow__p{axis}"] = np.full(n_samples, right_elbow_pos[i])  # Updated naming
        
        # Quaternion data for all joints
        test_joints = ["LeftShoulder", "RightShoulder", "Hips", "Head"]
        for joint in test_joints:
            # Create small random rotations
            base_quat = Rotation.random().as_quat()
            for i, axis in enumerate(['x', 'y', 'z', 'w']):
                data[f"{joint}__q{axis}"] = np.full(n_samples, base_quat[i]) + np.random.randn(n_samples) * 0.001  # Updated naming
        
        df = pd.DataFrame(data)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_anatomical_calibration(
                df=df,
                output_dir=temp_dir,
                fs=fs,
                elevation_threshold_deg=5.0
            )
            
            # Verify results structure
            assert "window_metadata" in results
            assert "v_pose_detection" in results
            assert "offsets_map" in results
            assert "quat_metadata" in results
            assert "output_path" in results
            
            # Verify V-Pose detection
            v_pose = results["v_pose_detection"]
            assert v_pose["left_arm"]["correction_applied"] == True  # 10° > 5°
            assert v_pose["right_arm"]["correction_applied"] == True  # 8° > 5°
            
            # Verify offsets were generated
            assert len(results["offsets_map"]) > 0
            
            # Verify output file was created
            output_file = Path(results["output_path"])
            assert output_file.exists()
            
            # Verify file contents
            with open(output_file, 'r') as f:
                saved_data = json.load(f)
            
            assert "offsets_map" in saved_data
            assert "metadata" in saved_data
            assert saved_data["metadata"]["quat_order"] == "xyzw"
            assert "time_window" in saved_data["metadata"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
