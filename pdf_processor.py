#!/usr/bin/env python3
"""
PDF Processor CLI Tool
Reads a PDF, finds pages with specific text, extracts them, and converts tables to Excel.
"""

import click
import PyPDF2
import pdfplumber
import pandas as pd
import os
import sys
from pathlib import Path
import tabula
import camelot


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--search-text', default='CONSOLIDATED STATEMENTS OF INCOME', 
              help='Text to search for in PDF pages')
@click.option('--min-page', default=10, type=int,
              help='Minimum page number to search from')
@click.option('--output-dir', default='./output',
              help='Output directory for extracted files')
@click.option('--method', type=click.Choice(['tabula', 'camelot', 'pdfplumber']), 
              default='camelot', help='Table extraction method')
def process_pdf(pdf_path, search_text, min_page, output_dir, method):
    """
    Process a PDF file to find specific pages and extract tables.
    
    PDF_PATH: Path to the PDF file to process
    """
    click.echo(f"Processing PDF: {pdf_path}")
    click.echo(f"Searching for text: '{search_text}'")
    click.echo(f"Starting from page: {min_page}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Step 1: Find the page with the specified text
    target_page = find_page_with_text(pdf_path, search_text, min_page)
    
    if target_page is None:
        click.echo(f"❌ No page found with text '{search_text}' after page {min_page}")
        sys.exit(1)
    
    click.echo(f"✅ Found text on page {target_page}")
    
    # Step 2: Extract the target page
    extracted_pdf_path = extract_page(pdf_path, target_page, output_path)
    click.echo(f"✅ Extracted page to: {extracted_pdf_path}")
    
    # Step 3: Extract table from the page
    excel_path = extract_table_to_excel(extracted_pdf_path, output_path, method)
    click.echo(f"✅ Table extracted to Excel: {excel_path}")
    
    click.echo(f"\n🎉 Processing complete!")
    click.echo(f"📄 Target page number: {target_page}")
    click.echo(f"📁 Output directory: {output_path.absolute()}")


def find_page_with_text(pdf_path, search_text, min_page):
    """
    Find the first page containing the specified text, starting from min_page.
    Returns the page number (1-indexed) or None if not found.
    """
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Search from min_page onwards
            for page_num in range(min_page - 1, len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                if search_text.upper() in text.upper():
                    return page_num + 1  # Return 1-indexed page number
                    
    except Exception as e:
        click.echo(f"❌ Error reading PDF: {e}")
        return None
    
    return None


def extract_page(pdf_path, page_number, output_path):
    """
    Extract a single page from the PDF and save it as a new PDF.
    Returns the path to the extracted PDF.
    """
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            pdf_writer = PyPDF2.PdfWriter()
            
            # Add the target page (convert to 0-indexed)
            pdf_writer.add_page(pdf_reader.pages[page_number - 1])
            
            # Save the extracted page
            extracted_path = output_path / f"page_{page_number}.pdf"
            with open(extracted_path, 'wb') as output_file:
                pdf_writer.write(output_file)
                
            return extracted_path
            
    except Exception as e:
        click.echo(f"❌ Error extracting page: {e}")
        return None


def extract_table_to_excel(pdf_path, output_path, method):
    """
    Extract tables from the PDF and save to Excel.
    Returns the path to the Excel file.
    """
    excel_path = output_path / "extracted_table.xlsx"
    
    try:
        if method == 'tabula':
            # Use tabula-py for table extraction
            tables = tabula.read_pdf(str(pdf_path), pages='all')
            
            if tables:
                # Combine all tables into one DataFrame
                combined_df = pd.concat(tables, ignore_index=True)
                combined_df.to_excel(excel_path, index=False)
                click.echo(f"📊 Extracted {len(tables)} tables using tabula")
            else:
                click.echo("⚠️  No tables found using tabula")
                return None
                
        elif method == 'camelot':
            # Use camelot-py for table extraction
            tables = camelot.read_pdf(str(pdf_path), pages='all')
            
            if tables:
                # Combine all tables into one DataFrame
                dfs = []
                for table in tables:
                    df = table.df
                    # Clean up the DataFrame
                    df = df.replace('', pd.NA).dropna(how='all')
                    dfs.append(df)
                
                if dfs:
                    combined_df = pd.concat(dfs, ignore_index=True)
                    combined_df.to_excel(excel_path, index=False)
                    click.echo(f"📊 Extracted {len(tables)} tables using camelot")
                else:
                    click.echo("⚠️  No valid tables found using camelot")
                    return None
            else:
                click.echo("⚠️  No tables found using camelot")
                return None
                
        elif method == 'pdfplumber':
            # Use pdfplumber for table extraction
            with pdfplumber.open(pdf_path) as pdf:
                all_tables = []
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            # Convert table to DataFrame
                            df = pd.DataFrame(table[1:], columns=table[0])
                            df = df.replace('', pd.NA).dropna(how='all')
                            all_tables.append(df)
                
                if all_tables:
                    combined_df = pd.concat(all_tables, ignore_index=True)
                    combined_df.to_excel(excel_path, index=False)
                    click.echo(f"📊 Extracted {len(all_tables)} tables using pdfplumber")
                else:
                    click.echo("⚠️  No tables found using pdfplumber")
                    return None
        
        return excel_path
        
    except Exception as e:
        click.echo(f"❌ Error extracting tables: {e}")
        return None


if __name__ == '__main__':
    process_pdf() 