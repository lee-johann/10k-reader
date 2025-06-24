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
import re
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
    click.echo(f"Searching for text: '{search_text}' (excluding 'INDEX')")
    click.echo(f"Starting from page: {min_page}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Step 1: Find the page with the specified text (and not the excluded text)
    target_page = find_page_with_text(pdf_path, search_text, min_page)
    
    if target_page is None:
        click.echo(f"❌ No page found with text '{search_text}' (excluding 'INDEX') after page {min_page}")
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
    Find the first page containing the specified text, starting from min_page,
    but NOT containing the excluded text.
    Returns the page number (1-indexed) or None if not found.
    """
    exclude_text = "INDEX"
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Search from min_page onwards
            for page_num in range(min_page - 1, len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if not text:
                    continue
                if (search_text.upper() in text.upper() and
                    exclude_text.upper() not in text.upper()):
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


def process_table_data(df):
    """
    Process the extracted table data to separate text from numbers and clean up formatting.
    Expects format like: "Sales and marketing $26,567 $27,917 $27,808"
    Returns: DataFrame with proper columns
    """
    if df.empty:
        return df
    
    processed_rows = []
    
    for index, row in df.iterrows():
        # Convert row to string and process each cell
        row_str = ' '.join(str(cell) for cell in row if pd.notna(cell) and str(cell).strip())
        if not row_str.strip():
            continue
        # Strip dollar signs and clean up
        row_str = row_str.replace('$', '').strip()
        parts = row_str.split()
        if len(parts) < 2:
            continue
        # Traverse from the end, collecting numbers or bracketed negatives
        number_parts = []
        i = len(parts) - 1
        while i >= 0:
            part = parts[i]
            
            # Check if this is a number according to our rules
            is_number = False
            is_bracketed_number = False
            
            # Rule 1: Immediately surrounded by brackets (like (3514))
            if part.startswith('(') and part.endswith(')') and len(part) > 2:
                bracket_content = part[1:-1]
                if re.match(r'^[\d,]+$', bracket_content):
                    # Check if there's a space before the opening bracket in original string
                    idx = row_str.find(part)
                    if idx == 0 or row_str[idx - 1] == ' ':
                        is_bracketed_number = True
                        is_number = True
            
            # Rule 2: No brackets at all (like 3514)
            elif not '(' in part and not ')' in part:
                clean_part = part.replace(',', '')
                if re.match(r'^-?[\d]+\.?[\d]*$', clean_part):
                    is_number = True
            
            # Rule 3: Starts with dollar sign (like $3514) - already handled by stripping $ above
            # This is covered by Rule 2 since we strip $ signs earlier
            
            if is_number:
                if is_bracketed_number:
                    number_str = bracket_content.replace(',', '')
                    number_parts.insert(0, f"-{number_str}")
                else:
                    number_parts.insert(0, part.replace(',', ''))
                i -= 1
            else:
                break
        # Everything before the numbers is the description
        text_parts = parts[:i+1]
        if text_parts and number_parts:
            text_column = ' '.join(text_parts)
            processed_row = [text_column] + number_parts
            processed_rows.append(processed_row)
    if not processed_rows:
        return df
    max_cols = max(len(row) for row in processed_rows)
    column_names = ['Description']
    for i in range(1, max_cols):
        column_names.append(f'Value_{i}')
    padded_rows = []
    for row in processed_rows:
        padded_row = row + [''] * (max_cols - len(row))
        padded_rows.append(padded_row)
    return pd.DataFrame(padded_rows, columns=column_names)


def extract_table_to_excel(pdf_path, output_path, method):
    """
    Extract tables from the PDF and save to Excel.
    Returns the path to the Excel file.
    """
    excel_path = output_path / "extracted_table.xlsx"
    
    # Try the specified method first, then fall back to others
    methods_to_try = [method]
    if method != 'pdfplumber':
        methods_to_try.append('pdfplumber')
    if method != 'tabula':
        methods_to_try.append('tabula')
    
    for current_method in methods_to_try:
        try:
            click.echo(f"Trying table extraction with {current_method}...")
            
            if current_method == 'tabula':
                # Use tabula-py for table extraction
                tables = tabula.read_pdf(str(pdf_path), pages='all')
                
                if tables:
                    # Combine all tables into one DataFrame
                    combined_df = pd.concat(tables, ignore_index=True)
                    # Process the table data
                    processed_df = process_table_data(combined_df)
                    processed_df.to_excel(excel_path, index=False)
                    click.echo(f"📊 Extracted and processed {len(tables)} tables using tabula")
                    return excel_path
                else:
                    click.echo("⚠️  No tables found using tabula")
                    
            elif current_method == 'camelot':
                # Use camelot-py for table extraction
                try:
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
                            # Process the table data
                            processed_df = process_table_data(combined_df)
                            processed_df.to_excel(excel_path, index=False)
                            click.echo(f"📊 Extracted and processed {len(tables)} tables using camelot")
                            return excel_path
                        else:
                            click.echo("⚠️  No valid tables found using camelot")
                    else:
                        click.echo("⚠️  No tables found using camelot")
                except Exception as e:
                    if "Ghostscript is not installed" in str(e):
                        click.echo("⚠️  Ghostscript not found for camelot, trying next method...")
                        continue
                    else:
                        raise e
                        
            elif current_method == 'pdfplumber':
                # Use pdfplumber for table extraction
                with pdfplumber.open(pdf_path) as pdf:
                    all_tables = []
                    for page in pdf.pages:
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                # Convert table to DataFrame
                                if table and len(table) > 1:  # Ensure we have headers and data
                                    df = pd.DataFrame(table[1:], columns=table[0])
                                    df = df.replace('', pd.NA).dropna(how='all')
                                    all_tables.append(df)
                    
                    if all_tables:
                        combined_df = pd.concat(all_tables, ignore_index=True)
                        # Process the table data
                        processed_df = process_table_data(combined_df)
                        processed_df.to_excel(excel_path, index=False)
                        click.echo(f"📊 Extracted and processed {len(all_tables)} tables using pdfplumber")
                        return excel_path
                    else:
                        click.echo("⚠️  No tables found using pdfplumber")
        
        except Exception as e:
            click.echo(f"❌ Error with {current_method}: {e}")
            continue
    
    click.echo("❌ All table extraction methods failed")
    return None


if __name__ == '__main__':
    process_pdf() 