#!/usr/bin/env python3
"""
Test script to verify Python PDF processor integration
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append('.')

try:
    from pdf_processor import extract_all_statements_to_excel
    
    # Test with a sample PDF if it exists
    test_pdf = "documents/goog-10-k-2024.pdf"
    
    if os.path.exists(test_pdf):
        print(f"Testing with {test_pdf}")
        output_dir = "test_output"
        os.makedirs(output_dir, exist_ok=True)
        
        extract_all_statements_to_excel(test_pdf, output_dir, "test")
        
        # Check if Excel file was created
        excel_files = list(Path(output_dir).glob("*.xlsx"))
        if excel_files:
            print(f"✅ Success! Created Excel file: {excel_files[0]}")
            
            # List sheets
            import pandas as pd
            excel_file = excel_files[0]
            xl = pd.ExcelFile(excel_file)
            print(f"📊 Sheets found: {xl.sheet_names}")
        else:
            print("❌ No Excel file created")
    else:
        print(f"Test PDF not found: {test_pdf}")
        print("Available PDFs in documents/:")
        if os.path.exists("documents"):
            for file in os.listdir("documents"):
                if file.endswith(".pdf"):
                    print(f"  - {file}")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}") 