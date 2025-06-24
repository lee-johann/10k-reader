#!/usr/bin/env python3
"""
Script to view the processed table results.
"""

import pandas as pd
from pathlib import Path


def main():
    """Display the processed table data."""
    excel_path = Path("output/extracted_table.xlsx")
    
    if not excel_path.exists():
        print("❌ Excel file not found. Please run the demo first.")
        return
    
    print("📊 Processed Table Data")
    print("=" * 80)
    
    # Read the Excel file
    df = pd.read_excel(excel_path)
    
    # Display basic info
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print()
    
    # Display the data
    print("Data Preview:")
    print("-" * 80)
    print(df.to_string(index=False))
    print("-" * 80)
    
    # Show example of how data was processed
    print("\n📋 Data Processing Example:")
    print("Original format: 'Sales and marketing $26,567 $27,917 $27,808'")
    print("Processed format:")
    print("  Description: 'Sales and marketing'")
    print("  Value_1: '26,567'")
    print("  Value_2: '27,917'")
    print("  Value_3: '27,808'")


if __name__ == "__main__":
    main() 