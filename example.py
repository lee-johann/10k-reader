#!/usr/bin/env python3
"""
Example script demonstrating how to use the PDF processor programmatically.
"""

import sys
from pathlib import Path
from pdf_processor import find_page_with_text, extract_page, extract_table_to_excel


def main():
    """
    Example usage of the PDF processor functions.
    """
    # Example PDF path (replace with your actual PDF)
    pdf_path = "example_document.pdf"
    
    # Check if the PDF exists
    if not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        print("Please place your PDF file in the current directory or update the path.")
        return
    
    print("🔍 PDF Processor Example")
    print("=" * 50)
    
    # Step 1: Find the page with "CONSOLIDATED STATEMENTS OF INCOME"
    search_text = "CONSOLIDATED STATEMENTS OF INCOME"
    min_page = 10
    
    print(f"Searching for: '{search_text}' starting from page {min_page}")
    target_page = find_page_with_text(pdf_path, search_text, min_page)
    
    if target_page is None:
        print(f"❌ No page found with text '{search_text}' after page {min_page}")
        return
    
    print(f"✅ Found text on page {target_page}")
    
    # Step 2: Extract the page
    output_path = Path("./output")
    output_path.mkdir(exist_ok=True)
    
    print(f"Extracting page {target_page}...")
    extracted_pdf_path = extract_page(pdf_path, target_page, output_path)
    
    if extracted_pdf_path is None:
        print("❌ Failed to extract page")
        return
    
    print(f"✅ Page extracted to: {extracted_pdf_path}")
    
    # Step 3: Extract table to Excel
    print("Extracting table to Excel...")
    excel_path = extract_table_to_excel(extracted_pdf_path, output_path, method='camelot')
    
    if excel_path is None:
        print("❌ Failed to extract table")
        return
    
    print(f"✅ Table extracted to: {excel_path}")
    
    # Summary
    print("\n" + "=" * 50)
    print("🎉 Processing Complete!")
    print(f"📄 Target page number: {target_page}")
    print(f"📁 Output directory: {output_path.absolute()}")
    print(f"📊 Excel file: {excel_path}")


if __name__ == "__main__":
    main() 