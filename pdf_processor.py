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
import openpyxl


@click.command()
@click.argument('pdf_path', type=click.Path(exists=True))
@click.option('--search-text', default='CONSOLIDATED STATEMENTS OF INCOME', 
              help='Text to search for in PDF pages')
@click.option('--min-page', default=3, type=int,
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
    click.echo(f"Searching for text: '{search_text}' (excluding 'Equity')")
    click.echo(f"Starting from page: {min_page}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Step 1: Find the page with the specified text (and not the excluded text)
    target_page = find_page_with_text(pdf_path, search_text, min_page)
    
    if target_page is None:
        click.echo(f"❌ No page found with text '{search_text}' (excluding 'Equity') after page {min_page}")
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
    but NOT containing the excluded text, and has less than 350 words.
    Returns the page number (1-indexed) or None if not found.
    """
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Search from min_page onwards
            for page_num in range(min_page - 1, len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                if not text:
                    continue
                
                # Count words on the page
                word_count = len(text.split())
                
                # Only consider pages with less than 350 words
                if word_count >= 350:
                    continue
                
                upper_text = text.upper()
                # Exclude if there are two or more mentions of 'TABLE OF CONTENTS' or any mention of 'INDEX'
                if (upper_text.count('TABLE OF CONTENTS') >= 2 or 'INDEX' in upper_text):
                    continue
                if search_text.upper() in upper_text:
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


def extract_header_info(pdf_path):
    """
    Extract header information from the PDF page, specifically looking for year headers.
    Returns a list of year headers if found.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]  # We're working with a single extracted page
            
            # Extract all text from the page
            text = page.extract_text()
            
            # Look for year patterns in the text
            # Common patterns: "Year Ended December 31," followed by years
            year_pattern = r'Year Ended December 31,?\s*((?:\d{4}\s*)+)'
            match = re.search(year_pattern, text)
            
            if match:
                years_text = match.group(1)
                # Split by whitespace and clean up
                years = [year.strip() for year in years_text.split() if year.strip().isdigit()]
                
                # Create descriptive headers by concatenating with "Year Ended December 31"
                headers = []
                for year in years:
                    header = f"Year Ended December 31, {year}"
                    headers.append(header)
                
                return headers
            
            # Alternative: look for just years in sequence
            year_sequence = re.findall(r'\b(20\d{2})\b', text)
            if len(year_sequence) >= 2:  # At least 2 years to be meaningful
                # Create descriptive headers by concatenating with "Year Ended December 31"
                headers = []
                for year in year_sequence[:3]:  # Use up to 3 years
                    header = f"Year Ended December 31, {year}"
                    headers.append(header)
                return headers
            
            return None
            
    except Exception as e:
        click.echo(f"❌ Error extracting header info: {e}")
        return None


def extract_table_to_excel(pdf_path, output_path, method):
    """
    Extract tables from the PDF and save to Excel.
    Returns the path to the Excel file.
    """
    excel_path = output_path / "extracted_table.xlsx"
    
    # First, try to extract header information
    header_years = extract_header_info(pdf_path)
    if header_years:
        click.echo(f"📅 Found year headers: {header_years}")
    else:
        click.echo("⚠️  No year headers found, using default column names")
    
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
                    
                    # Update column names if we found year headers
                    if header_years and len(header_years) >= len(processed_df.columns) - 1:
                        new_columns = ['Description'] + header_years[:len(processed_df.columns) - 1]
                        processed_df.columns = new_columns
                    
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
                            
                            # Update column names if we found year headers
                            if header_years and len(header_years) >= len(processed_df.columns) - 1:
                                new_columns = ['Description'] + header_years[:len(processed_df.columns) - 1]
                                processed_df.columns = new_columns
                            
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
                                    # Ensure unique column names
                                    if df.columns.duplicated().any():
                                        df.columns = [f"{col}_{i}" if df.columns.duplicated()[i] else col for i, col in enumerate(df.columns)]
                                    df = df.replace('', pd.NA).dropna(how='all')
                                    all_tables.append(df)
                    
                    if all_tables:
                        combined_df = pd.concat(all_tables, ignore_index=True)
                        # Process the table data
                        processed_df = process_table_data(combined_df)
                        
                        # Update column names if we found year headers
                        if header_years and len(header_years) >= len(processed_df.columns) - 1:
                            new_columns = ['Description'] + header_years[:len(processed_df.columns) - 1]
                            processed_df.columns = new_columns
                        
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


def extract_all_statements_to_excel(pdf_path, output_path, pdf_name):
    """
    Extract all financial statements from the PDF and save to Excel with multiple tabs.
    Returns the path to the Excel file.
    """
    # Convert output_path to Path object if it's a string
    output_path = Path(output_path)
    excel_path = output_path / f"{pdf_name}_extracted.xlsx"
    
    # Define the statements to look for
    statements = [
        "CONSOLIDATED STATEMENTS OF INCOME",
        "CONSOLIDATED BALANCE SHEETS", 
        "CONSOLIDATED STATEMENTS OF CASH FLOWS"
    ]
    
    # Create Excel writer
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        extracted_count = 0
        
        for statement in statements:
            click.echo(f"\n🔍 Looking for: {statement}")
            
            # Find the page with this statement
            target_page = find_page_with_text(pdf_path, statement, 3)
            
            if target_page is None:
                click.echo(f"❌ No page found with text '{statement}'")
                continue
            
            click.echo(f"✅ Found {statement} on page {target_page}")
            
            # Extract the page
            extracted_pdf_path = extract_page(pdf_path, target_page, output_path)
            if extracted_pdf_path is None:
                click.echo(f"❌ Failed to extract page {target_page}")
                continue
            
            # Extract table from the page
            table_df = extract_table_from_page(extracted_pdf_path, statement)
            if table_df is not None and not table_df.empty:
                # Create tab name from statement
                tab_name = statement.replace("CONSOLIDATED STATEMENTS OF ", "").replace("'", "").replace(" ", "_")
                tab_name = tab_name[:31]  # Excel tab names limited to 31 characters
                
                # Write to Excel tab
                table_df.to_excel(writer, sheet_name=tab_name, index=False)
                
                # Add comment to cell A1 with source information
                worksheet = writer.sheets[tab_name]
                cell_a1 = worksheet['A1']
                comment_text = f"From page {target_page} of {Path(pdf_path).name}"
                cell_a1.comment = openpyxl.comments.Comment(comment_text, "PDF Processor")
                
                click.echo(f"✅ Added {statement} to tab '{tab_name}' with source comment")
                extracted_count += 1
            else:
                click.echo(f"❌ No table found for {statement}")
        
        if extracted_count == 0:
            click.echo("❌ No statements were successfully extracted")
            return None
        
        click.echo(f"\n🎉 Successfully extracted {extracted_count} statements to {excel_path}")
        return excel_path


def extract_table_from_page(pdf_path, statement_name):
    """
    Extract table from a specific page and return as DataFrame.
    """
    # First, try to extract header information
    header_years = extract_header_info(pdf_path)
    if header_years:
        click.echo(f"📅 Found year headers: {header_years}")
    else:
        click.echo("⚠️  No year headers found, using default column names")
    
    # Try different extraction methods
    methods_to_try = ['pdfplumber', 'camelot', 'tabula']
    
    for current_method in methods_to_try:
        try:
            click.echo(f"Trying table extraction with {current_method}...")
            
            if current_method == 'tabula':
                tables = tabula.read_pdf(str(pdf_path), pages='all')
                if tables:
                    combined_df = pd.concat(tables, ignore_index=True)
                    processed_df = process_table_data(combined_df)
                    if header_years and len(header_years) >= len(processed_df.columns) - 1:
                        new_columns = ['Description'] + header_years[:len(processed_df.columns) - 1]
                        processed_df.columns = new_columns
                    return processed_df
                    
            elif current_method == 'camelot':
                try:
                    tables = camelot.read_pdf(str(pdf_path), pages='all')
                    if tables:
                        dfs = []
                        for table in tables:
                            df = table.df
                            df = df.replace('', pd.NA).dropna(how='all')
                            dfs.append(df)
                        
                        if dfs:
                            combined_df = pd.concat(dfs, ignore_index=True)
                            processed_df = process_table_data(combined_df)
                            if header_years and len(header_years) >= len(processed_df.columns) - 1:
                                new_columns = ['Description'] + header_years[:len(processed_df.columns) - 1]
                                processed_df.columns = new_columns
                            return processed_df
                except Exception as e:
                    if "Ghostscript is not installed" in str(e):
                        click.echo("⚠️  Ghostscript not found for camelot, trying next method...")
                        continue
                    else:
                        raise e
                        
            elif current_method == 'pdfplumber':
                with pdfplumber.open(pdf_path) as pdf:
                    all_tables = []
                    for page in pdf.pages:
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                if table and len(table) > 1:
                                    df = pd.DataFrame(table[1:], columns=table[0])
                                    # Ensure unique column names
                                    if df.columns.duplicated().any():
                                        df.columns = [f"{col}_{i}" if df.columns.duplicated()[i] else col for i, col in enumerate(df.columns)]
                                    df = df.replace('', pd.NA).dropna(how='all')
                                    all_tables.append(df)
                    
                    if all_tables:
                        combined_df = pd.concat(all_tables, ignore_index=True)
                        processed_df = process_table_data(combined_df)
                        if header_years and len(header_years) >= len(processed_df.columns) - 1:
                            new_columns = ['Description'] + header_years[:len(processed_df.columns) - 1]
                            processed_df.columns = new_columns
                        return processed_df
        
        except Exception as e:
            click.echo(f"❌ Error with {current_method}: {e}")
            continue
    
    return None


if __name__ == '__main__':
    process_pdf() 