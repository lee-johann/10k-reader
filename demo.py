#!/usr/bin/env python3
"""
Demo script that emphasizes the page number output.
"""

import sys
from pathlib import Path
from pdf_processor import find_page_with_text, extract_page, extract_table_to_excel, extract_header_info, process_table_data
import click
import pandas as pd
import tabula
import camelot
import pdfplumber


def run_demo_for_pdf(pdf_path):
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return
    print(f"\n{'='*80}\n🔍 PDF Processor Demo for {pdf_path.name}\n{'='*80}")
    search_text = "CONSOLIDATED STATEMENTS OF INCOME"
    exclude_text = "Equity"
    min_page = 3
    print(f"Searching for: '{search_text}' (excluding '{exclude_text}') starting from page {min_page}")
    target_page = find_page_with_text(str(pdf_path), search_text, min_page)
    if target_page is None:
        print(f"❌ No page found with text '{search_text}' (excluding '{exclude_text}') after page {min_page}")
        return
    print(f"\n{'='*60}\n🎯 TARGET PAGE FOUND!\n{'='*60}\n📄 PAGE NUMBER: {target_page}\n{'='*60}")
    output_path = Path("./output")
    output_path.mkdir(exist_ok=True)
    print(f"\nExtracting page {target_page}...")
    extracted_pdf_path = extract_page(str(pdf_path), target_page, output_path)
    if extracted_pdf_path is None:
        print("❌ Failed to extract page")
        return
    print(f"✅ Page extracted to: {extracted_pdf_path}")
    print("Extracting table to Excel...")
    excel_path = extract_table_to_excel_custom(extracted_pdf_path, output_path, pdf_path.stem)
    if excel_path is None:
        print("❌ Failed to extract table")
        return
    print(f"✅ Table extracted to: {excel_path}")
    print(f"\n{'='*60}\n🎉 PROCESSING COMPLETE!\n{'='*60}\n📄 PAGE NUMBER: {target_page}\n📁 Output directory: {output_path.absolute()}\n📊 Excel file: {excel_path}\n{'='*60}")

def main():
    pdfs = [
        Path("documents/goog-10-k-2024.pdf"),
        Path("documents/goog-10-q-q1-2025.pdf")
    ]
    for pdf_path in pdfs:
        run_demo_for_pdf(pdf_path)


def extract_table_to_excel_custom(pdf_path, output_path, pdf_name):
    """
    Extract tables from the PDF and save to Excel with custom naming.
    Returns the path to the Excel file.
    """
    # Use the existing function but with custom naming
    excel_path = output_path / f"{pdf_name}_extracted.xlsx"
    
    # First, try to extract header information
    header_years = extract_header_info(pdf_path)
    if header_years:
        click.echo(f"📅 Found year headers: {header_years}")
    else:
        click.echo("⚠️  No year headers found, using default column names")
    
    # Use the existing extract_table_to_excel function
    temp_excel_path = extract_table_to_excel(pdf_path, output_path, 'pdfplumber')
    
    if temp_excel_path:
        # Rename the file to include the PDF name
        temp_excel_path.rename(excel_path)
        return excel_path
    
    return None


if __name__ == "__main__":
    main() 