"""
Biomechanical Guardrails for Winter Filtering - Usage Examples

This script demonstrates the new biomechanical guardrails features implemented
based on practical recommendations for dance biomechanics.

Key Features:
1. Minimum cutoff guardrails for trunk (6.0 Hz) and distal (8.0 Hz) markers
2. Trunk-based global cutoff strategy
3. Detailed logging of biomechanical decisions

CRITICAL: For dance/mocap, distal segments (hands/feet) need HIGHER cutoffs
than trunk because they contain faster real motion from expressive dance movements.
"""

import sys
import os
sys.path.insert(0, 'src')

from filtering import apply_winter_filter
import pandas as pd
import numpy as np

def example_biomechanical_guardrails():
    """Demonstrate different biomechanical guardrail strategies."""
    
    # Load your data here
    # df = pd.read_parquet('your_data.parquet')
    # pos_cols = [c for c in df.columns if c.endswith(('__px','__py','__pz'))]
    
    print("=== Biomechanical Guardrails Examples ===\n")
    
    # Example 1: Standard multi-signal with CORRECTED guardrails (RECOMMENDED)
    print("1. Standard Multi-signal with CORRECTED Biomechanical Guardrails:")
    print("   - Trunk markers: min_cutoff = 6.0 Hz (slower motion)")
    print("   - Distal markers: min_cutoff = 8.0 Hz (faster dance motion)")
    print("   - Preserves rapid hand/foot movements in choreography")
    
    """
    df_filtered, metadata = apply_winter_filter(
        df, 
        fs=120.0, 
        pos_cols=pos_cols, 
        fmax=12, 
        allow_fmax=True,
        min_cutoff_trunk=6.0,      # Trunk: slower, more stable motion
        min_cutoff_distal=8.0,     # Distal: faster, expressive dance motion
        use_trunk_global=False      # Use multi-signal analysis
    )
    """
    
    # Example 2: Trunk-based global cutoff (ALTERNATIVE)
    print("\n2. Trunk-based Global Cutoff Strategy:")
    print("   - Run Winter on trunk markers only")
    print("   - Apply trunk-based cutoff to ALL markers")
    print("   - Ensures consistent filtering across body")
    
    """
    df_filtered, metadata = apply_winter_filter(
        df, 
        fs=120.0, 
        pos_cols=pos_cols, 
        fmax=12, 
        allow_fmax=True,
        min_cutoff_trunk=6.0,      # Trunk markers minimum
        min_cutoff_distal=8.0,     # Distal markers minimum  
        use_trunk_global=True       # Use trunk-based global cutoff
    )
    """
    
    # Example 3: Conservative guardrails (HIGH QUALITY DATA)
    print("\n3. Conservative Guardrails (Maximum Motion Preservation):")
    print("   - Trunk markers: min_cutoff = 8.0 Hz")
    print("   - Distal markers: min_cutoff = 10.0 Hz")
    print("   - For applications requiring maximum motion preservation")
    
    """
    df_filtered, metadata = apply_winter_filter(
        df, 
        fs=120.0, 
        pos_cols=pos_cols, 
        fmax=12, 
        allow_fmax=True,
        min_cutoff_trunk=8.0,      # Conservative trunk minimum
        min_cutoff_distal=10.0,    # Conservative distal minimum
        use_trunk_global=False      # Multi-signal analysis
    )
    """
    
    print("\n=== Key Benefits ===")
    print("✅ Winter's algorithmic result respected when biomechanically appropriate")
    print("✅ Low cutoffs (e.g., 4 Hz) clamped with biomechanical reasoning")
    print("✅ Distal markers (hands/feet) protected from oversmoothing fast dance motion")
    print("✅ Trunk markers get appropriate filtering for stable core movement")
    print("✅ All decisions logged for reproducibility and audit trails")
    
    print("\n=== Biomechanical Rationale ===")
    print("• TRUNK (pelvis, spine, torso): Slower, more stable motion")
    print("  → Lower minimum cutoff (6 Hz) sufficient")
    print("• DISTAL (hands, feet, fingers): Faster, expressive dance motion") 
    print("  → Higher minimum cutoff (8 Hz) preserves choreographic details")
    print("• This reflects the biomechanics of dance where extremities move rapidly")
    
    print("\n=== Interpretation Guide ===")
    print("• If Winter returns 4 Hz → Clamped to 6.0 Hz (trunk) or 8.0 Hz (distal)")
    print("• If Winter returns 7 Hz → Used as-is for trunk, clamped to 8.0 Hz for distal")
    print("• If Winter returns 9 Hz → Used as-is (above both minima)")
    print("• If Winter returns 12 Hz → Algorithm failure (investigate pipeline)")
    print("• Guardrail warnings indicate biomechanical corrections were applied")

if __name__ == "__main__":
    example_biomechanical_guardrails()
