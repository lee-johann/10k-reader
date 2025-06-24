#!/usr/bin/env python3
"""
Demo script that emphasizes the page number output.
"""

import sys
from pathlib import Path
from pdf_processor import find_page_with_text, extract_page, extract_table_to_excel


def main():
    """
    Demo script with prominent page number display.
    """
    # Use the specified PDF in the documents folder
    pdf_path = Path("documents/goog-10-k-2024.pdf")
    
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        sys.exit(1)
    
    print("🔍 PDF Processor Demo")
    print("=" * 60)
    
    # Step 1: Find the page with "CONSOLIDATED STATEMENTS OF INCOME" but not "INDEX"
    search_text = "CONSOLIDATED STATEMENTS OF INCOME"
    exclude_text = "INDEX"
    min_page = 10
    
    print(f"Searching for: '{search_text}' (excluding '{exclude_text}') starting from page {min_page}")
    target_page = find_page_with_text(str(pdf_path), search_text, min_page)
    
    if target_page is None:
        print(f"❌ No page found with text '{search_text}' (excluding '{exclude_text}') after page {min_page}")
        sys.exit(1)
    
    # PROMINENT PAGE NUMBER DISPLAY
    print("\n" + "=" * 60)
    print("🎯 TARGET PAGE FOUND!")
    print("=" * 60)
    print(f"📄 PAGE NUMBER: {target_page}")
    print("=" * 60)
    
    # Step 2: Extract the page
    output_path = Path("./output")
    output_path.mkdir(exist_ok=True)
    
    print(f"\nExtracting page {target_page}...")
    extracted_pdf_path = extract_page(str(pdf_path), target_page, output_path)
    
    if extracted_pdf_path is None:
        print("❌ Failed to extract page")
        sys.exit(1)
    
    print(f"✅ Page extracted to: {extracted_pdf_path}")
    
    # Step 3: Extract table to Excel
    print("Extracting table to Excel...")
    excel_path = extract_table_to_excel(extracted_pdf_path, output_path, method='camelot')
    
    if excel_path is None:
        print("❌ Failed to extract table")
        sys.exit(1)
    
    print(f"✅ Table extracted to: {excel_path}")
    
    # Final summary with page number
    print("\n" + "=" * 60)
    print("🎉 PROCESSING COMPLETE!")
    print("=" * 60)
    print(f"📄 PAGE NUMBER: {target_page}")
    print(f"📁 Output directory: {output_path.absolute()}")
    print(f"📊 Excel file: {excel_path}")
    print("=" * 60)


if __name__ == "__main__":
    main() 