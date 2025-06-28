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
import json
from pathlib import Path
import functools
import subprocess
import signal
import contextlib
import io

# Fix for macOS: Set library path for Ghostscript detection
if sys.platform == "darwin":
    # Add Homebrew lib path to DYLD_LIBRARY_PATH for Ghostscript detection
    homebrew_lib = "/opt/homebrew/lib"
    if os.path.exists(homebrew_lib):
        current_dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
        if homebrew_lib not in current_dyld_path:
            if current_dyld_path:
                os.environ['DYLD_LIBRARY_PATH'] = f"{homebrew_lib}:{current_dyld_path}"
            else:
                os.environ['DYLD_LIBRARY_PATH'] = homebrew_lib

import camelot
import openpyxl

# Import the validation module
from table_validation import validate_financial_statements


class ConsoleOutputRedirector:
    """
    Context manager to redirect console output to a file.
    """
    def __init__(self, output_path):
        self.output_path = output_path
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.output_file = None
        
    def __enter__(self):
        # Create output directory if it doesn't exist
        self.output_path.parent.mkdir(exist_ok=True)
        
        # Open file for writing
        self.output_file = open(self.output_path, 'w', encoding='utf-8')
        
        # Create a custom stdout that writes to both file and original stdout
        class TeeOutput:
            def __init__(self, original, file):
                self.original = original
                self.file = file
                
            def write(self, text):
                self.original.write(text)
                self.file.write(text)
                self.file.flush()
                
            def flush(self):
                self.original.flush()
                self.file.flush()
        
        # Redirect stdout and stderr
        sys.stdout = TeeOutput(self.original_stdout, self.output_file)
        sys.stderr = TeeOutput(self.original_stderr, self.output_file)
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original stdout and stderr
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        
        # Close the file
        if self.output_file:
            self.output_file.close()


def redirect_output_to_file(output_path):
    """
    Decorator to redirect all output to a file during function execution.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            console_output_path = output_path / "console_output"
            with ConsoleOutputRedirector(console_output_path):
                return func(*args, **kwargs)
        return wrapper
    return decorator


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
@click.option('--debug', is_flag=True, default=False, help='Enable debug logging')
def process_pdf(pdf_path, search_text, min_page, output_dir, method, debug):
    """
    Process a PDF file to find specific pages and extract tables.
    
    PDF_PATH: Path to the PDF file to process
    """
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Redirect output to file
    console_output_path = output_path / "console_output"
    with ConsoleOutputRedirector(console_output_path):
        _process_pdf_internal(pdf_path, search_text, min_page, output_path, method, debug)


def _process_pdf_internal(pdf_path, search_text, min_page, output_path, method, debug):
    """
    Internal processing function that runs with output redirection.
    """
    click.echo(f"Processing PDF: {pdf_path}")
    click.echo(f"Searching for text: '{search_text}' (excluding 'Equity')")
    click.echo(f"Starting from page: {min_page}")
    
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
    table_df = extract_table_to_excel(extracted_pdf_path, output_path, method, debug)
    if table_df is not None and not table_df.empty:
        click.echo(f"✅ Table extracted successfully with {len(table_df)} rows")
        click.echo(f"📊 Table columns: {list(table_df.columns)}")
    else:
        click.echo(f"❌ Failed to extract table")
    
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


def process_table_data(df, debug=False):
    """
    Process the extracted table data to separate text from numbers and clean up formatting.
    Expects format like: "Sales and marketing $26,567 $27,917 $27,808"
    Returns: DataFrame with proper columns
    """
    if df.empty:
        return df

    if debug:
        print('RAW DF:')
        print(df)
    first_col = str(df.columns[0])
    if 'Revenues' in first_col:
        header_row = [first_col] + [str(col) for col in df.columns[1:]]
        if debug:
            print(f'HEADER AS ROW: {header_row}')
        df.loc[-1] = header_row
        df.index = df.index + 1
        df = df.sort_index()
        df.columns = [f'col_{i}' for i in range(len(df.columns))]

    processed_rows = []

    for index, row in df.iterrows():
        # Remove trailing None/empty/None_2 columns
        cells = [str(cell) for cell in row if pd.notna(cell) and str(cell).strip()]
        while cells and (cells[-1] == 'None' or cells[-1] == 'None_2' or cells[-1] == ''):
            cells.pop()
        row_str = ' '.join(cells)
        if debug:
            print(f'RAW ROW: {repr(row_str)}')
        if not row_str.strip():
            continue
        row_str = row_str.replace('$', '').strip()
        parts = row_str.split()
        if len(parts) < 1:  # Changed from < 2 to < 1 to allow single-word rows
            if debug:
                print(f'SKIPPED (too few parts): {repr(row_str)}')
            continue
        
        # Check if this row has any numbers
        has_numbers = False
        for part in parts:
            # Check for bracketed numbers like (3,514)
            if part.startswith('(') and part.endswith(')') and len(part) > 2:
                bracket_content = part[1:-1]
                if re.match(r'^[\d,]+$', bracket_content):
                    has_numbers = True
                    break
            # Check for regular numbers (including those with commas)
            elif not '(' in part and not ')' in part:
                clean_part = part.replace(',', '').replace('$', '').strip()
                if re.match(r'^-?[\d]+\.?[\d]*$', clean_part):
                    has_numbers = True
                    break
        
        # If no numbers found, treat as a section header and keep it
        if not has_numbers:
            # This is a section header or complex text row - keep all text in first column
            processed_row = [row_str] + [''] * (len(df.columns) - 1)  # Fill remaining columns with empty strings
            processed_rows.append(processed_row)
            if debug:
                print(f'KEPT TEXT ROW: {repr(row_str)}')
            continue
        
        # Process rows with numbers as before
        number_parts = []
        i = len(parts) - 1
        dash_values = {"—", "-", "--", "–", "―"}
        while i >= 0:
            part = parts[i]
            is_number = False
            is_bracketed_number = False
            if part in dash_values:
                number_parts.insert(0, "")  # Treat dash as empty value
                i -= 1
                continue
            if part.startswith('(') and part.endswith(')') and len(part) > 2:
                bracket_content = part[1:-1]
                if re.match(r'^[\d,]+$', bracket_content):
                    idx = row_str.find(part)
                    if idx == 0 or row_str[idx - 1] == ' ':
                        is_bracketed_number = True
                        is_number = True
            elif not '(' in part and not ')' in part:
                clean_part = part.replace(',', '').replace('$', '').strip()
                if re.match(r'^-?[\d]+\.?[\d]*$', clean_part):
                    is_number = True
            if is_number:
                if is_bracketed_number:
                    number_str = bracket_content.replace(',', '')
                    number_parts.insert(0, f"-{number_str}")
                else:
                    number_parts.insert(0, clean_part)
                i -= 1
            else:
                break
        text_parts = parts[:i+1]
        if not text_parts or not number_parts:
            # If we can't properly separate text and numbers, keep everything in first column
            processed_row = [row_str] + [''] * (len(df.columns) - 1)
            processed_rows.append(processed_row)
            if debug:
                print(f'KEPT COMPLEX ROW: {repr(row_str)}')
            continue
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


def extract_header_info(pdf_path, debug=False):
    """
    Extract header information from the PDF page, specifically looking for year or period headers.
    Returns a list of headers if found.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]  # We're working with a single extracted page
            text = page.extract_text()
            lines = text.split('\n')
            header_line = None
            for i, line in enumerate(lines):
                if re.search(r'(ended|as of)', line, re.IGNORECASE):
                    joined = line.strip()
                    next_lines = []
                    if i + 1 < len(lines):
                        next_lines.append(lines[i + 1].strip())
                    if i + 2 < len(lines):
                        if re.search(r'\b(20\d{2})\b', lines[i + 2]) or re.search(r'[A-Za-z]+ \d{1,2}, \d{4}', lines[i + 2]) or re.match(r'^(20\d{2}(\s+)?)+$', lines[i + 2]):
                            next_lines.append(lines[i + 2].strip())
                    header_line = joined + ' ' + ' '.join(next_lines)
                    if debug:
                        print(f'HEADER DEBUG: joined lines: {[line] + next_lines}')
                        print(f'HEADER DEBUG: header_line: {header_line}')
                    prefix_matches = re.findall(r'(As of|Ended)', joined, re.IGNORECASE)
                    date_matches = re.findall(r'([A-Za-z]+ \d{1,2}, \d{4})', ' '.join(next_lines))
                    # Only use paired headers logic if there are multiple prefixes and dates
                    if len(prefix_matches) > 1 and len(prefix_matches) == len(date_matches):
                        headers = [f"{prefix.strip()} {date.strip()}" for prefix, date in zip(prefix_matches, date_matches)]
                        if debug:
                            print(f'HEADER DEBUG: paired headers: {headers}')
                        return headers
                    # Special handling: if three lines, and the last line is just years, join first two as prefix
                    if len(next_lines) == 2:
                        prefix = f"{joined} {next_lines[0]}".strip()
                        years = re.findall(r'\b(20\d{2})\b', next_lines[1])
                        if years:
                            headers = [f"{prefix} {year}".strip() for year in years]
                            if debug:
                                print(f'HEADER DEBUG: prefix: {prefix}, years: {years}, headers: {headers}')
                            return headers
                    break
            if header_line:
                years = re.findall(r'\b(20\d{2})\b', header_line)
                if not years:
                    date_matches = re.findall(r'([A-Za-z]+ \d{1,2}, \d{4})', header_line)
                    if date_matches:
                        years = date_matches
                if years:
                    headers = []
                    first_year_idx = header_line.find(years[0])
                    if first_year_idx > 0:
                        prefix = header_line[:first_year_idx].strip()
                    else:
                        prefix = header_line.strip()
                    for year in years:
                        header = f"{prefix} {year}".strip()
                        headers.append(header)
                    if debug:
                        print(f'HEADER DEBUG: prefix: {prefix}, years: {years}, headers: {headers}')
                    return headers
                else:
                    if debug:
                        print(f'HEADER DEBUG: fallback header_line: {header_line.strip()}')
                    return [header_line.strip()]
            # Fallback to previous logic
            year_pattern = r'Year Ended December 31,?\s*((?:\d{4}\s*)+)'
            match = re.search(year_pattern, text)
            if match:
                years_text = match.group(1)
                years = [year.strip() for year in years_text.split() if year.strip().isdigit()]
                headers = []
                for year in years:
                    header = f"Year Ended December 31, {year}"
                    headers.append(header)
                if debug:
                    print(f'HEADER DEBUG: fallback year headers: {headers}')
                return headers
            year_sequence = re.findall(r'\b(20\d{2})\b', text)
            if len(year_sequence) >= 2:
                headers = []
                for year in year_sequence[:3]:
                    header = f"Year Ended December 31, {year}"
                    headers.append(header)
                if debug:
                    print(f'HEADER DEBUG: fallback year sequence headers: {headers}')
                return headers
            if debug:
                print('HEADER DEBUG: No headers found')
            return None
    except Exception as e:
        click.echo(f"❌ Error extracting header info: {e}")
        return None


def extract_best_camelot_table(pdf_path, page_num=1, debug=False):
    """
    Extract tables using Camelot in stream mode, return the table with the most rows.
    """
    import camelot
    best_table = None
    max_rows = 0
    best_df = None
    try:
        tables = camelot.read_pdf(str(pdf_path), pages=str(page_num), flavor="stream", edge_tol=100, strip_text='\n', row_tol=10)
        for i, table in enumerate(tables):
            nrows = table.df.shape[0]
            if debug:
                print(f"Camelot (stream) Table {i}: shape={table.df.shape}")
            if nrows > max_rows:
                max_rows = nrows
                best_table = table
                best_df = table.df
    except Exception as e:
        if debug:
            print(f"Camelot (stream) error: {e}")
    if debug and best_table is not None:
        print(f"Best Camelot table: rows={max_rows}")
    return best_df


def try_all_table_extractors(pdf_path, page_num=1, debug=False):
    print("=== Camelot (stream) ===")
    best_df = extract_best_camelot_table(pdf_path, page_num, debug=debug)
    if best_df is not None:
        print(best_df)
    else:
        print("No table found with Camelot.")

    print("=== pdfplumber ===")
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()
            for i, table in enumerate(tables):
                print(f"pdfplumber Table {i}:")
                for row in table:
                    print(row)
    except Exception as e:
        print(f"pdfplumber error: {e}")


def merge_extraction_results(pdfplumber_df, camelot_df, debug=False):
    """
    Merge pdfplumber and camelot extraction results.
    Insert camelot-only rows into pdfplumber results at the correct positions.
    Truncate camelot columns by merging text and removing unwanted columns.
    """
    if pdfplumber_df is None or pdfplumber_df.empty:
        return camelot_df
    if camelot_df is None or camelot_df.empty:
        return pdfplumber_df
    
    if debug:
        print("MERGING: pdfplumber rows:", len(pdfplumber_df))
        print("MERGING: camelot rows:", len(camelot_df))
        print("MERGING: pdfplumber columns:", len(pdfplumber_df.columns))
        print("MERGING: camelot columns:", len(camelot_df.columns))
    
    # Clean camelot DataFrame by removing unwanted columns and merging text
    cleaned_camelot_df = clean_camelot_dataframe(camelot_df, debug)
    
    if debug:
        print("\n=== CLEANED CAMELOT TABLE ===")
        print(cleaned_camelot_df)
        print("=== END CLEANED CAMELOT TABLE ===\n")
    
    # Convert both to list of rows for easier manipulation
    pdfplumber_rows = pdfplumber_df.values.tolist()
    camelot_rows = cleaned_camelot_df.values.tolist()
    
    # Create a mapping of camelot row content to their positions
    camelot_content_map = {}
    for i, row in enumerate(camelot_rows):
        row_content = ' '.join([str(cell) for cell in row if pd.notna(cell) and str(cell).strip()])
        if row_content.strip():
            camelot_content_map[row_content] = i
    
    # Create a mapping of pdfplumber row content to their positions
    pdfplumber_content_map = {}
    for i, row in enumerate(pdfplumber_rows):
        row_content = ' '.join([str(cell) for cell in row if pd.notna(cell) and str(cell).strip()])
        if row_content.strip():
            pdfplumber_content_map[row_content] = i
    
    # Find camelot-only rows
    camelot_only_rows = []
    for content, camelot_pos in camelot_content_map.items():
        if content not in pdfplumber_content_map:
            # Skip rows that contain alphabetically spelled months (dates)
            months = ['january', 'february', 'march', 'april', 'may', 'june', 
                     'july', 'august', 'september', 'october', 'november', 'december']
            content_lower = content.lower()
            contains_month = any(month in content_lower for month in months)
            
            if contains_month:
                if debug:
                    print(f"MERGING: Skipping camelot-only row with date: {content}")
                continue
            
            camelot_only_rows.append((camelot_pos, camelot_rows[camelot_pos]))
    
    if debug and camelot_only_rows:
        print(f"MERGING: Found {len(camelot_only_rows)} camelot-only rows")
        for pos, row in camelot_only_rows:
            print(f"MERGING: Camelot-only row at position {pos}: {row}")
    
    # Insert camelot-only rows into pdfplumber results
    merged_rows = pdfplumber_rows.copy()
    offset = 0  # Track position offset due to insertions
    
    for camelot_pos, camelot_row in camelot_only_rows:
        # Find the best insertion position in pdfplumber results
        # Try to insert at the same relative position
        insert_pos = min(camelot_pos, len(merged_rows))
        
        # Insert the row
        merged_rows.insert(insert_pos + offset, camelot_row)
        offset += 1
        
        if debug:
            print(f"MERGING: Inserted camelot row at position {insert_pos + offset - 1}")
    
    # Convert back to DataFrame with proper column names
    if merged_rows:
        # Use pdfplumber column names and extend if needed
        column_names = list(pdfplumber_df.columns)
        for i in range(len(column_names), len(merged_rows[0])):
            column_names.append(f'col_{i}')
        
        merged_df = pd.DataFrame(merged_rows, columns=column_names)
        
        # Remove columns that are empty or only contain None values
        columns_to_keep = []
        for col_idx, col_name in enumerate(merged_df.columns):
            col_values = merged_df.iloc[:, col_idx]
            # Check if column has any non-empty, non-None values
            has_meaningful_data = False
            for val in col_values:
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'None':
                    has_meaningful_data = True
                    break
            
            if has_meaningful_data:
                columns_to_keep.append(col_idx)
            else:
                if debug:
                    print(f"MERGING: Removing empty/None column {col_idx} ({col_name})")
        
        if columns_to_keep:
            merged_df = merged_df.iloc[:, columns_to_keep]
            if debug:
                print(f"MERGING: After removing empty columns: {len(merged_df.columns)} columns")
        else:
            if debug:
                print("MERGING: No meaningful columns found after filtering")
            return pd.DataFrame()
        
        if debug:
            print(f"MERGING: Final merged result has {len(merged_df)} rows and {len(merged_df.columns)} columns")
            print("\n=== FINAL MERGED TABLE ===")
            print(merged_df)
            print("=== END FINAL MERGED TABLE ===\n")
        return merged_df
    
    return pdfplumber_df


def merge_long_rows(camelot_df, debug=False, word_tolerance=15):
    """
    Merge rows that have word_tolerance words or more in the description field.
    Also merge up short, lowercase descriptions with the row above.
    This helps combine split rows that are part of the same logical row.
    """
    if camelot_df is None or camelot_df.empty or len(camelot_df) <= 1:
        return camelot_df

    if debug:
        print("MERGING LONG ROWS: Original shape:", camelot_df.shape)
        print("MERGING LONG ROWS: Raw DataFrame:")
        for idx, row in camelot_df.iterrows():
            desc = row.iloc[0]
            desc_clean = str(desc).replace('\n', ' ').replace('\r', ' ').strip()
            word_count = len(desc_clean.split())
            values = [repr(row.iloc[i]) for i in range(1, len(row))]
            # Number detection
            is_number = []
            for val in values:
                val_clean = str(val).replace('\n', ' ').replace('\r', ' ').strip()
                if val_clean and val_clean != 'nan':
                    if val_clean.startswith('(') and val_clean.endswith(')') and len(val_clean) > 2:
                        bracket_content = val_clean[1:-1]
                        is_number.append(bool(re.match(r'^[\d,]+$', bracket_content)))
                    elif re.match(r'^-?[\d,]+\.?[\d]*$', val_clean.replace(',', '').replace('$', '')):
                        is_number.append(True)
                    else:
                        is_number.append(False)
                else:
                    is_number.append(False)
            print(f"Row {idx}:")
            print(f"  Raw desc: {repr(desc)}")
            print(f"  Clean desc: {repr(desc_clean)}")
            print(f"  Word count: {word_count}")
            print(f"  Values: {values}")
            print(f"  Is number: {is_number}")

    # First pass: merge down long descriptions
    merged_rows = []
    i = 0
    
    while i < len(camelot_df):
        current_row = camelot_df.iloc[i].copy()
        current_text = str(current_row.iloc[0]).strip() if len(current_row) > 0 else ""
        
        # Check if this row has numbers in later columns
        has_numbers = False
        for col_idx in range(1, len(current_row)):
            val = current_row.iloc[col_idx]
            if pd.notna(val) and str(val).strip():
                # Check if it's a number
                val_str = str(val).strip()
                if val_str.startswith('(') and val_str.endswith(')') and len(val_str) > 2:
                    bracket_content = val_str[1:-1]
                    if re.match(r'^[\d,]+$', bracket_content):
                        has_numbers = True
                        break
                elif re.match(r'^-?[\d,]+\.?[\d]*$', val_str.replace(',', '').replace('$', '')):
                    has_numbers = True
                    break
        
        # If current row has numbers, keep it as is (don't merge)
        if has_numbers:
            merged_rows.append(current_row)
            i += 1
        else:
            # This row doesn't have numbers, check if it's a section header or should be merged down
            def is_section_header(text):
                if not text or text == 'nan':
                    return False
                
                text = text.strip()
                
                # Only accept if starts with a capitalized word
                if not text or not text[0].isupper():
                    return False
                
                # Check for colon ending (common in section headers)
                if text.endswith(':'):
                    return True
                
                # Check if it's a short, standalone phrase
                word_count = len(text.split())
                if word_count < word_tolerance:
                    # Check if it doesn't end with continuation words
                    continuation_words = ['and', 'or', 'the', 'of', 'in', 'to', 'for', 'with', 'by', 'from']
                    words = text.lower().split()
                    if words and words[-1] not in continuation_words:
                        # Check if it looks like a complete phrase
                        if not text.endswith(',') and not text.endswith(';'):
                            # Additional check: if it's just a single word, it's likely not a section header
                            if word_count == 1:
                                return False
                            return True
                
                # Check for specific patterns that indicate section headers
                header_patterns = [
                    r'^[A-Z][a-z\s]+:$',  # Capitalized words ending with colon
                    r'^[A-Z\s]+$',        # All caps (like "ASSETS")
                    r'^[A-Z][a-z\s]+assets?$',  # Ends with "asset" or "assets"
                    r'^[A-Z][a-z\s]+liabilities?$',  # Ends with "liability" or "liabilities"
                    r'^[A-Z][a-z\s]+equity$',  # Ends with "equity"
                ]
                
                for pattern in header_patterns:
                    if re.match(pattern, text, re.IGNORECASE):
                        return True
                
                return False
            
            if is_section_header(current_text):
                # This is a section header, keep it separate
                merged_rows.append(current_row)
                if debug:
                    print(f"MERGING LONG ROWS: Keeping section header: {current_text}")
                i += 1
            elif len(current_text.split()) >= word_tolerance:
                # This row has word_tolerance+ words but no numbers, look ahead to find the next row with numbers
                next_row_with_numbers = None
                next_row_idx = None
                
                for j in range(i + 1, len(camelot_df)):
                    test_row = camelot_df.iloc[j]
                    test_text = str(test_row.iloc[0]).strip() if len(test_row) > 0 else ""
                    
                    # Check if this test row is a section header
                    if is_section_header(test_text):
                        # Stop looking, we've hit another section header
                        break
                    
                    test_has_numbers = False
                    for col_idx in range(1, len(test_row)):
                        val = test_row.iloc[col_idx]
                        if pd.notna(val) and str(val).strip():
                            val_str = str(val).strip()
                            if val_str.startswith('(') and val_str.endswith(')') and len(val_str) > 2:
                                bracket_content = val_str[1:-1]
                                if re.match(r'^[\d,]+$', bracket_content):
                                    test_has_numbers = True
                                    break
                            elif re.match(r'^-?[\d,]+\.?[\d]*$', val_str.replace(',', '').replace('$', '')):
                                test_has_numbers = True
                                break
                    
                    if test_has_numbers:
                        next_row_with_numbers = test_row
                        next_row_idx = j
                        break
                
                if next_row_with_numbers is not None:
                    # Merge all rows from i to next_row_idx
                    merged_text_parts = []
                    merged_data = None
                    
                    for k in range(i, next_row_idx + 1):
                        row = camelot_df.iloc[k]
                        text_part = str(row.iloc[0]).strip() if len(row) > 0 else ""
                        if text_part and text_part != 'nan':
                            merged_text_parts.append(text_part)
                        
                        # Use the last row's data (which should have the numbers)
                        if k == next_row_idx:
                            merged_data = row.copy()
                    
                    if merged_text_parts and merged_data is not None:
                        # Combine the text parts
                        merged_text = ' '.join(merged_text_parts)
                        merged_data.iloc[0] = merged_text
                        merged_rows.append(merged_data)
                        
                        if debug:
                            print(f"MERGING LONG ROWS: Merged rows {i}-{next_row_idx} into: {merged_text}")
                        
                        i = next_row_idx + 1
                    else:
                        # Fallback: just add current row
                        merged_rows.append(current_row)
                        i += 1
                else:
                    # No next row with numbers found, just add current row
                    merged_rows.append(current_row)
                    i += 1
            else:
                # This row has less than word_tolerance words and no numbers, keep as is
                merged_rows.append(current_row)
                i += 1
    
    # Second pass: merge up short, lowercase descriptions
    final_rows = []
    i = 0
    
    while i < len(merged_rows):
        current_row = merged_rows[i].copy()
        current_text = str(current_row.iloc[0]).strip() if len(current_row) > 0 else ""
        
        # Check if this row should be merged up (short, lowercase description)
        def should_merge_up(text):
            if not text or text == 'nan':
                return False
            
            text = text.strip()
            word_count = len(text.split())
            
            # Check if it's a short, lowercase description
            if word_count < word_tolerance and not text.isupper():
                # Check if it doesn't start with a capital letter (indicating it's not a section header)
                if text and not text[0].isupper():
                    return True
                # Also check if it's all lowercase (common for continuation text)
                if text.islower():
                    return True
            
            return False
        
        if should_merge_up(current_text):
            # This row should be merged up with the previous row
            if final_rows:
                # Merge with the previous row
                prev_row = final_rows.pop()
                prev_text = str(prev_row.iloc[0]).strip() if len(prev_row) > 0 else ""
                
                # Combine the texts
                combined_text = f"{prev_text} {current_text}".strip()
                prev_row.iloc[0] = combined_text
                final_rows.append(prev_row)
                
                if debug:
                    print(f"MERGING LONG ROWS: Merged up row {i} into previous: {combined_text}")
            else:
                # No previous row to merge with, keep as is
                final_rows.append(current_row)
        else:
            # This row should not be merged up, keep as is
            final_rows.append(current_row)
        
        i += 1
    
    if debug:
        print("MERGING LONG ROWS: After merging:")
        for idx, row in enumerate(final_rows):
            desc = row.iloc[0]
            desc_clean = str(desc).replace('\n', ' ').replace('\r', ' ').strip()
            word_count = len(desc_clean.split())
            values = [repr(row.iloc[i]) for i in range(1, len(row))]
            print(f"Row {idx}:")
            print(f"  Raw desc: {repr(desc)}")
            print(f"  Clean desc: {repr(desc_clean)}")
            print(f"  Word count: {word_count}")
            print(f"  Values: {values}")

    if final_rows:
        result_df = pd.DataFrame(final_rows)
        if debug:
            print("MERGING LONG ROWS: Final shape:", result_df.shape)
        return result_df
    
    return camelot_df


def clean_camelot_dataframe(camelot_df, debug=False, word_tolerance=15):
    """
    Clean camelot DataFrame by:
    1. Merging rows with word_tolerance+ words in description
    2. Merging up short, lowercase descriptions
    3. Removing columns with only "..." or "$"
    4. Merging text columns into one column
    5. Keeping only meaningful data columns
    6. Only keeping rows where columns 2 and 3 have numbers in them
    """
    if camelot_df is None or camelot_df.empty:
        return camelot_df
    
    if debug:
        print("CLEANING: Original camelot shape:", camelot_df.shape)
    
    # First, merge rows with long descriptions
    camelot_df = merge_long_rows(camelot_df, debug, word_tolerance)
    
    if debug:
        print("CLEANING: After merging long rows:", camelot_df.shape)
    
    # Remove columns that contain only "..." or "$"
    columns_to_keep = []
    for col_idx, col_name in enumerate(camelot_df.columns):
        col_values = camelot_df.iloc[:, col_idx].astype(str)
        # Check if column contains only "..." or "$" or is empty
        unique_values = set(col_values.str.strip())
        if len(unique_values) <= 2 and all(val in ['...', '$', '', 'nan', 'None'] for val in unique_values):
            if debug:
                print(f"CLEANING: Removing column {col_idx} ({col_name}) with values: {unique_values}")
            continue
        columns_to_keep.append(col_idx)
    
    if not columns_to_keep:
        if debug:
            print("CLEANING: No meaningful columns found, returning original")
        return camelot_df
    
    # Keep only meaningful columns
    cleaned_df = camelot_df.iloc[:, columns_to_keep].copy()
    
    if debug:
        print("CLEANING: After removing unwanted columns:", cleaned_df.shape)
    
    # Merge text columns into one column
    if len(cleaned_df.columns) > 1:
        # Find the first column that contains mostly text (not numbers)
        text_col_idx = None
        for col_idx in range(len(cleaned_df.columns)):
            col_values = cleaned_df.iloc[:, col_idx].astype(str)
            # Count how many values look like text vs numbers
            text_count = 0
            total_count = 0
            for val in col_values:
                if pd.notna(val) and str(val).strip():
                    total_count += 1
                    # Check if it's mostly text (contains letters and not just numbers/symbols)
                    if re.search(r'[a-zA-Z]', str(val)) and not re.match(r'^[\d\s\-\+\(\)\$\,\.]+$', str(val)):
                        text_count += 1
            
            if total_count > 0 and text_count / total_count > 0.5:
                text_col_idx = col_idx
                break
        
        if text_col_idx is not None and text_col_idx > 0:
            # Merge text from earlier columns into the text column
            for row_idx in range(len(cleaned_df)):
                merged_text = []
                for col_idx in range(text_col_idx):
                    val = cleaned_df.iloc[row_idx, col_idx]
                    if pd.notna(val) and str(val).strip():
                        merged_text.append(str(val).strip())
                
                if merged_text:
                    current_text = cleaned_df.iloc[row_idx, text_col_idx]
                    if pd.notna(current_text) and str(current_text).strip():
                        merged_text.append(str(current_text).strip())
                    cleaned_df.iloc[row_idx, text_col_idx] = ' '.join(merged_text)
            
            # Remove the merged columns
            cleaned_df = cleaned_df.iloc[:, text_col_idx:]
            
            if debug:
                print("CLEANING: After merging text columns:", cleaned_df.shape)
    
    # Filter rows to only keep those where columns 2 and 3 (Value_1 and Value_2) have numbers
    if len(cleaned_df.columns) >= 3:
        rows_to_keep = []
        for row_idx in range(len(cleaned_df)):
            col2_val = cleaned_df.iloc[row_idx, 1] if len(cleaned_df.columns) > 1 else None  # Value_1
            col3_val = cleaned_df.iloc[row_idx, 2] if len(cleaned_df.columns) > 2 else None  # Value_2
            
            # Check if both columns have numbers
            has_numbers = False
            if pd.notna(col2_val) and pd.notna(col3_val):
                col2_str = str(col2_val).strip()
                col3_str = str(col3_val).strip()
                
                # Check for bracketed numbers like (3,514)
                def is_number(val):
                    if val.startswith('(') and val.endswith(')') and len(val) > 2:
                        bracket_content = val[1:-1]
                        return re.match(r'^[\d,]+$', bracket_content)
                    # Check for regular numbers
                    clean_val = val.replace(',', '').replace('$', '').strip()
                    return re.match(r'^-?[\d]+\.?[\d]*$', clean_val)
                
                if is_number(col2_str) and is_number(col3_str):
                    has_numbers = True
            
            if has_numbers:
                rows_to_keep.append(row_idx)
                if debug:
                    print(f"CLEANING: Keeping row {row_idx} with numbers: col2='{col2_val}', col3='{col3_val}'")
            else:
                if debug:
                    print(f"CLEANING: Removing row {row_idx} - no numbers in cols 2&3: col2='{col2_val}', col3='{col3_val}'")
        
        if rows_to_keep:
            cleaned_df = cleaned_df.iloc[rows_to_keep].reset_index(drop=True)
            if debug:
                print("CLEANING: After filtering rows with numbers:", cleaned_df.shape)
        else:
            if debug:
                print("CLEANING: No rows with numbers found, returning empty DataFrame")
            return pd.DataFrame()
    
    return cleaned_df


def extract_table_to_excel(pdf_path, output_path, method, debug=False):
    """
    Extract tables from the PDF and return the DataFrame.
    Returns the DataFrame with extracted data.
    """
    # Extract metadata using intelligent parsing
    metadata = intelligent_financial_parser(pdf_path, debug=debug)
    if metadata:
        click.echo(f"📅 Intelligent parsing results:")
        if metadata.get('company'):
            click.echo(f"  Company: {metadata['company']}")
        if metadata.get('statement_type'):
            click.echo(f"  Statement Type: {metadata['statement_type']}")
        if metadata.get('periods'):
            click.echo(f"  Periods: {metadata['periods']}")
        if metadata.get('units'):
            click.echo(f"  Units: {metadata['units']}")
    
    # First, try to extract header information using original logic
    header_years = extract_header_info(pdf_path, debug)
    if header_years:
        click.echo(f"📅 Found year headers: {header_years}")
    else:
        click.echo("⚠️  No year headers found, using default column names")
    
    # Use hybrid approach: camelot for table rows
    table_df = extract_table_hybrid(pdf_path, debug=debug)
    
    if table_df is not None and not table_df.empty:
        # Update column names if we found year headers
        if header_years and len(header_years) >= len(table_df.columns) - 1:
            new_columns = ['Description'] + header_years[:len(table_df.columns) - 1]
            table_df.columns = new_columns
        
        # Add parsed result row with metadata information
        if metadata:
            table_df = add_parsed_result_row(table_df, metadata, debug=debug)
            if debug:
                print("Added parsed result row to table")
        
        click.echo(f"📊 Hybrid extraction completed successfully")
        return table_df
    
    click.echo("❌ All table extraction methods failed")
    return None


def extract_table_hybrid(pdf_path, debug=False):
    """
    Hybrid approach: Use camelot for table rows and original header logic.
    Returns a DataFrame with combined results.
    """
    # Extract table rows with camelot
    rows_df = extract_table_rows_with_camelot(pdf_path, debug)
    
    if rows_df is not None and not rows_df.empty:
        # Remove entirely empty columns
        if debug:
            print(f"HYBRID: Original shape: {rows_df.shape}")
        
        # Find columns that are entirely empty or contain only empty strings/None
        columns_to_keep = []
        for col_idx, col_name in enumerate(rows_df.columns):
            col_values = rows_df.iloc[:, col_idx]
            # Check if column has any non-empty, non-None values
            has_meaningful_data = False
            for val in col_values:
                if pd.notna(val) and str(val).strip() and str(val).strip() != 'None':
                    has_meaningful_data = True
                    break
            
            if has_meaningful_data:
                columns_to_keep.append(col_idx)
            else:
                if debug:
                    print(f"HYBRID: Removing empty column {col_idx} ({col_name})")
        
        if columns_to_keep:
            rows_df = rows_df.iloc[:, columns_to_keep]
            if debug:
                print(f"HYBRID: After removing empty columns: {rows_df.shape}")
        else:
            if debug:
                print("HYBRID: No meaningful columns found after filtering")
            return pd.DataFrame()
        
        # Filter out rows with parenthetical descriptions
        if len(rows_df.columns) > 0:
            description_col = rows_df.columns[0]  # First column is typically description
            rows_to_keep = []
            
            for idx, row in rows_df.iterrows():
                description = str(row[description_col]).strip()
                
                # Skip if description is empty
                if not description or description == 'nan':
                    continue
                
                # Skip if description starts with ( and ends with )
                if description.startswith('(') and description.endswith(')'):
                    if debug:
                        print(f"HYBRID: Removing parenthetical row: {description}")
                    continue
                
                # Skip if description contains "consolidated statement" or "consolidated statements"
                description_lower = description.lower()
                if 'consolidated statement' in description_lower:
                    if debug:
                        print(f"HYBRID: Removing consolidated statement row: {description}")
                    continue
                
                rows_to_keep.append(idx)
            
            if rows_to_keep:
                rows_df = rows_df.iloc[rows_to_keep].reset_index(drop=True)
                if debug:
                    print(f"HYBRID: After filtering parenthetical rows: {rows_df.shape}")
            else:
                if debug:
                    print("HYBRID: No rows remaining after filtering")
                return pd.DataFrame()
        
        return rows_df
    else:
        # Fallback to pdfplumber if camelot fails
        if debug:
            print("HYBRID: Camelot failed, falling back to pdfplumber")
        try:
            click.echo(f"Falling back to pdfplumber for table extraction...")
            with pdfplumber.open(pdf_path) as pdf:
                all_tables = []
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            if table and len(table) > 1:
                                df = pd.DataFrame(table[1:], columns=table[0])
                                if df.columns.duplicated().any():
                                    df.columns = [f"{col}_{i}" if df.columns.duplicated()[i] else col for i, col in enumerate(df.columns)]
                                df = df.replace('', pd.NA).dropna(how='all')
                                all_tables.append(df)
                if all_tables:
                    combined_df = pd.concat(all_tables, ignore_index=True)
                    pdfplumber_df = process_table_data(combined_df, debug)
                    click.echo(f"📊 Fallback: Extracted and processed {len(all_tables)} tables using pdfplumber")
                    return pdfplumber_df
        except Exception as e:
            click.echo(f"❌ Error with pdfplumber fallback: {e}")
    
    return None


def extract_table_from_page(pdf_path, statement_name, debug=False):
    # Extract metadata using intelligent parsing
    metadata = intelligent_financial_parser(pdf_path, debug=debug)
    if metadata:
        click.echo(f"📅 Intelligent parsing results:")
        if metadata.get('company'):
            click.echo(f"  Company: {metadata['company']}")
        if metadata.get('statement_type'):
            click.echo(f"  Statement Type: {metadata['statement_type']}")
        if metadata.get('periods'):
            click.echo(f"  Periods: {metadata['periods']}")
        if metadata.get('units'):
            click.echo(f"  Units: {metadata['units']}")
    
    # Extract header information using original logic as fallback
    header_years = extract_header_info(pdf_path, debug)
    if header_years:
        click.echo(f"📅 Found year headers: {header_years}")
    else:
        click.echo("⚠️  No year headers found, using default column names")
    
    if debug:
        print("\n=== DEBUG: Trying hybrid table extraction ===")
    
    # Use hybrid approach: camelot for table rows
    table_df = extract_table_hybrid(pdf_path, debug=debug)
    
    if table_df is not None and not table_df.empty:
        # Update column names if we found year headers
        if header_years and len(header_years) >= len(table_df.columns) - 1:
            new_columns = ['Description'] + header_years[:len(table_df.columns) - 1]
            table_df.columns = new_columns
        
        # Now filter out rows with header matches (after column names are updated)
        if len(table_df.columns) > 0:
            description_col = table_df.columns[0]  # First column is typically description
            rows_to_keep = []
            
            for idx, row in table_df.iterrows():
                description = str(row[description_col]).strip()
                
                # Skip if description is empty
                if not description or description == 'nan':
                    continue
                
                # Check for 50% word match with column headers
                description_words = set(description.lower().split())
                header_words = set()
                for col in table_df.columns:
                    header_words.update(col.lower().split())
                
                if description_words and header_words:
                    # Calculate word match percentage
                    common_words = description_words.intersection(header_words)
                    match_percentage = len(common_words) / len(description_words)
                    
                    if match_percentage >= 0.5:
                        if debug:
                            print(f"HEADER MATCH: Removing header match row ({match_percentage:.1%}): {description}")
                        continue
                
                # Skip if description contains "consolidated statement" or "consolidated statements"
                description_lower = description.lower()
                if 'consolidated statement' in description_lower:
                    if debug:
                        print(f"HEADER MATCH: Removing consolidated statement row: {description}")
                    continue
                
                rows_to_keep.append(idx)
            
            if rows_to_keep:
                table_df = table_df.iloc[rows_to_keep].reset_index(drop=True)
                if debug:
                    print(f"HEADER MATCH: After filtering header matches: {table_df.shape}")
            else:
                if debug:
                    print("HEADER MATCH: No rows remaining after filtering")
                return pd.DataFrame()
        
        # Add parsed result row with metadata information
        if metadata:
            table_df = add_parsed_result_row(table_df, metadata, debug=debug)
            if debug:
                print("Added parsed result row to table")
        
        return table_df
    
    return None


def extract_all_statements_to_json(pdf_path, output_path, pdf_name):
    """
    Extract all financial statements from the PDF and return as JSON data.
    Returns JSON string with extracted statements.
    Also concatenates the extracted statement pages into a single PDF named with company and period.
    """
    output_path = Path(output_path)
    statements = [
        "CONSOLIDATED STATEMENTS OF INCOME",
        "CONSOLIDATED BALANCE SHEETS", 
        "CONSOLIDATED STATEMENTS OF CASH FLOWS"
    ]
    extracted_statements = []
    overall_metadata = {
        'company': None,
        'statement_types': [],
        'periods': [],
        'units': []
    }
    extracted_pdf_paths = []
    period_for_filename = None
    company_for_filename = None
    for statement in statements:
        click.echo(f"\n🔍 Looking for: {statement}")
        target_page = find_page_with_text(pdf_path, statement, 3)
        if target_page is None:
            click.echo(f"❌ No page found with text '{statement}'")
            continue
        click.echo(f"✅ Found {statement} on page {target_page}")
        extracted_pdf_path = extract_page(pdf_path, target_page, output_path)
        if extracted_pdf_path is None:
            click.echo(f"❌ Failed to extract page {target_page}")
            continue
        extracted_pdf_paths.append(str(extracted_pdf_path))
        table_df = extract_table_from_page(extracted_pdf_path, statement)
        if table_df is not None and not table_df.empty:
            statement_name = statement.replace("CONSOLIDATED STATEMENTS OF ", "").replace("CONSOLIDATED ", "").replace("'", "").replace(" ", "_")
            statement_metadata = intelligent_financial_parser(extracted_pdf_path)
            if statement_metadata:
                if statement_metadata.get('company') and not overall_metadata['company']:
                    overall_metadata['company'] = statement_metadata['company']
                if statement_metadata.get('statement_type'):
                    overall_metadata['statement_types'].append(statement_metadata['statement_type'])
                if statement_metadata.get('periods'):
                    overall_metadata['periods'].extend(statement_metadata['periods'])
                if statement_metadata.get('units'):
                    overall_metadata['units'].extend(statement_metadata['units'])
                # For filename: use first found period and company
                if not period_for_filename and statement_metadata.get('periods'):
                    period_for_filename = statement_metadata['periods'][0]
                if not company_for_filename and statement_metadata.get('company'):
                    company_for_filename = statement_metadata['company']
            statement_data = {
                "name": statement_name,
                "pageNumber": target_page,
                "headers": table_df.columns.tolist(),
                "tableData": [],
                "metadata": statement_metadata or {}
            }
            for _, row in table_df.iterrows():
                row_dict = {}
                for col in table_df.columns:
                    value = row[col]
                    if isinstance(value, pd.Series):
                        value = value.astype(str).to_list()
                        value = ", ".join(value)
                    if value is None or (isinstance(value, float) and pd.isna(value)):
                        row_dict[col] = ""
                    else:
                        row_dict[col] = str(value)
                statement_data["tableData"].append(row_dict)
            extracted_statements.append(statement_data)
            click.echo(f"✅ Extracted {statement} from page {target_page}")
        else:
            click.echo(f"❌ No table found for {statement}")
    if not extracted_statements:
        click.echo("❌ No statements were successfully extracted")
        return None
    # Clean up overall metadata (remove duplicates)
    overall_metadata['statement_types'] = list(set(overall_metadata['statement_types']))
    overall_metadata['periods'] = list(set(overall_metadata['periods']))
    overall_metadata['units'] = list(set(overall_metadata['units']))
    # --- Concatenate PDFs ---
    # Use "extracted_[raw_pdf_name]" format
    raw_pdf_name = Path(pdf_path).stem  # Get filename without extension
    concat_pdf_name = f"extracted_{raw_pdf_name}.pdf"
    concat_pdf_path = output_path / concat_pdf_name
    if extracted_pdf_paths:
        concatenate_pdfs(extracted_pdf_paths, concat_pdf_path)
        click.echo(f"📄 Concatenated PDF created: {concat_pdf_path}")
        
        # Delete individual PDF pages after concatenation
        for pdf_path_str in extracted_pdf_paths:
            try:
                Path(pdf_path_str).unlink()
                click.echo(f"🗑️  Deleted individual PDF: {Path(pdf_path_str).name}")
            except Exception as e:
                click.echo(f"⚠️  Failed to delete {Path(pdf_path_str).name}: {e}")
    else:
        concat_pdf_path = None
    # ---
    try:
        click.echo(f"🔍 Starting validation with {len(extracted_statements)} statements")
        validation_results = validate_financial_statements(extracted_statements)
        click.echo(f"✅ Validation completed: {validation_results['summary']['passed_checks']}/{validation_results['summary']['total_checks']} checks passed ({validation_results['summary']['pass_rate']}%)")
        click.echo(f"🔍 Validation results: {validation_results}")
    except Exception as e:
        click.echo(f"⚠️  Validation failed: {e}")
        import traceback
        click.echo(f"⚠️  Validation error details: {traceback.format_exc()}")
        validation_results = {
            'checklist_results': {},
            'summary': {'total_checks': 0, 'passed_checks': 0, 'failed_checks': 0, 'pass_rate': 0},
            'balance_sheet_totals': None
        }
    result = {
        "pdfName": pdf_name,
        "overallMetadata": overall_metadata,
        "statements": extracted_statements,
        "extractedCount": len(extracted_statements),
        "validation": validation_results,
        "concatenatedPdf": str(concat_pdf_path) if concat_pdf_path else None
    }
    click.echo(f"\n🎉 Successfully extracted {len(extracted_statements)} statements")
    return json.dumps(result)


def extract_headers_with_pdfplumber(pdf_path, debug=False):
    """
    Extract table headers using pdfplumber.
    Returns a DataFrame with just the header information.
    """
    try:
        click.echo(f"Extracting headers with pdfplumber...")
        with pdfplumber.open(pdf_path) as pdf:
            all_headers = []
            for page in pdf.pages:
                tables = page.extract_tables()
                if debug:
                    for t_idx, table in enumerate(tables):
                        print(f"PDFPLUMBER HEADERS DEBUG: TABLE {t_idx}")
                        if table and len(table) > 0:
                            print(f"PDFPLUMBER HEADERS DEBUG: HEADER ROW: {table[0]}")
                if tables:
                    for table in tables:
                        if table and len(table) > 0:
                            # Take just the header row (first row)
                            header_df = pd.DataFrame([table[0]], columns=table[0])
                            if header_df.columns.duplicated().any():
                                header_df.columns = [f"{col}_{i}" if header_df.columns.duplicated()[i] else col for i, col in enumerate(header_df.columns)]
                            all_headers.append(header_df)
            if all_headers:
                combined_headers = pd.concat(all_headers, ignore_index=True)
                click.echo(f"📊 Extracted headers using pdfplumber")
                return combined_headers
            else:
                click.echo("⚠️  No headers found using pdfplumber")
                return None
    except Exception as e:
        click.echo(f"❌ Error extracting headers with pdfplumber: {e}")
        return None


def extract_table_rows_with_camelot(pdf_path, debug=False):
    """
    Extract table rows using camelot as the primary method.
    Returns a DataFrame with the table data.
    """
    try:
        click.echo(f"Extracting table rows with camelot...")
        camelot_df = extract_best_camelot_table(pdf_path, page_num=1, debug=debug)
        if camelot_df is not None:
            # Apply merging logic BEFORE process_table_data to merge split rows
            if debug:
                print("CAMELOT: Applying merging logic before processing...")
            camelot_df = merge_long_rows(camelot_df, debug=debug)
            
            # Now process the merged data
            camelot_df = process_table_data(camelot_df, debug)
            click.echo(f"📊 Extracted and processed table rows using camelot")
            return camelot_df
        else:
            click.echo("⚠️  No valid tables found using camelot")
            return None
    except Exception as e:
        click.echo(f"❌ Error with camelot: {e}")
        return None


def extract_period_info(text):
    """Extract period information with flexible pattern matching"""
    
    # Multiple period patterns
    period_patterns = [
        # Three Months Ended patterns
        r'(Three\s+Months?\s+Ended)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(Quarter\s+Ended)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(Q[1-4]\s+Ended)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        
        # Year Ended patterns
        r'(Year\s+Ended)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(Fiscal\s+Year\s+Ended)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(Twelve\s+Months?\s+Ended)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        
        # As of patterns
        r'(As\s+of)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(At\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        
        # Simple year patterns
        r'\b(20\d{2})\b',
        r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})'
    ]
    
    periods = []
    for pattern in period_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                period_type, date = match
                periods.append(f"{period_type.strip()} {date.strip()}")
            else:
                periods.append(match.strip())
    
    return list(set(periods))  # Remove duplicates


def extract_units_info(text):
    """Extract unit information with context awareness"""
    
    unit_patterns = [
        # Standard patterns
        r'\(in\s+([^)]+)\)',
        r'\(([^)]*millions?[^)]*)\)',
        r'\(([^)]*thousands?[^)]*)\)',
        r'\(([^)]*billions?[^)]*)\)',
        
        # With exceptions
        r'\(([^)]*except[^)]*per\s+share[^)]*)\)',
        r'\(([^)]*unaudited[^)]*)\)',
        r'\(([^)]*audited[^)]*)\)',
        
        # Currency patterns
        r'\(([^)]*dollars?[^)]*)\)',
        r'\(([^)]*USD[^)]*)\)',
        r'\(([^)]*\$[^)]*)\)'
    ]
    
    units = []
    for pattern in unit_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        units.extend(matches)
    
    return list(set(units))


def classify_statement_type(text):
    """Classify the type of financial statement"""
    
    statement_patterns = {
        'income_statement': [
            r'CONSOLIDATED\s+STATEMENTS?\s+OF\s+INCOME',
            r'CONSOLIDATED\s+STATEMENTS?\s+OF\s+OPERATIONS',
            r'INCOME\s+STATEMENT',
            r'STATEMENT\s+OF\s+OPERATIONS',
            r'STATEMENT\s+OF\s+INCOME',
            r'PROFIT\s+AND\s+LOSS',
            r'P&L\s+STATEMENT'
        ],
        'balance_sheet': [
            r'CONSOLIDATED\s+BALANCE\s+SHEETS?',
            r'BALANCE\s+SHEET',
            r'STATEMENT\s+OF\s+FINANCIAL\s+POSITION',
            r'STATEMENT\s+OF\s+ASSETS?\s+AND\s+LIABILITIES?'
        ],
        'cash_flow': [
            r'CONSOLIDATED\s+STATEMENTS?\s+OF\s+CASH\s+FLOWS?',
            r'STATEMENT\s+OF\s+CASH\s+FLOWS?',
            r'STATEMENT\s+OF\s+CASH\s+AND\s+CASH\s+EQUIVALENTS?'
        ],
        'equity': [
            r'CONSOLIDATED\s+STATEMENTS?\s+OF\s+STOCKHOLDERS?\s+EQUITY',
            r'STATEMENT\s+OF\s+STOCKHOLDERS?\s+EQUITY',
            r'STATEMENT\s+OF\s+SHAREHOLDERS?\s+EQUITY',
            r'STATEMENT\s+OF\s+CHANGES\s+IN\s+EQUITY'
        ]
    }
    
    for statement_type, patterns in statement_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return statement_type
    
    return 'unknown'


def extract_company_info(text):
    """Extract company name and related information"""
    
    # Look for company name at the beginning
    company_patterns = [
        r'^([A-Z][A-Za-z\s&.,]+?)(?:\n|$)',
        r'^([A-Z][A-Za-z\s&.,]+?)\s+CONSOLIDATED',
        r'^([A-Z][A-Za-z\s&.,]+?)\s+INC\.',
        r'^([A-Z][A-Za-z\s&.,]+?)\s+CORP\.',
        r'^([A-Z][A-Za-z\s&.,]+?)\s+LLC',
        r'^([A-Z][A-Za-z\s&.,]+?)\s+LTD\.'
    ]
    
    for pattern in company_patterns:
        match = re.search(pattern, text)
        if match:
            company_name = match.group(1).strip()
            # Clean up common artifacts
            company_name = re.sub(r'\s+', ' ', company_name)
            return company_name
    
    return None


def detect_table_headers(text_lines):
    """Intelligently detect table headers from text lines"""
    
    headers = []
    for i, line in enumerate(text_lines):
        line_clean = line.strip()
        
        # Look for lines that contain date patterns
        if re.search(r'\b(20\d{2})\b', line_clean):
            # Check if this looks like a header row
            if re.search(r'(ended|as of|march|june|september|december)', line_clean, re.IGNORECASE):
                # Look ahead for more date information
                header_parts = [line_clean]
                
                # Check next few lines for additional dates
                for j in range(1, 4):
                    if i + j < len(text_lines):
                        next_line = text_lines[i + j].strip()
                        if re.search(r'\b(20\d{2})\b', next_line):
                            header_parts.append(next_line)
                        elif re.search(r'[A-Za-z]+\s+\d{1,2},?\s+\d{4}', next_line):
                            header_parts.append(next_line)
                
                # Combine header parts
                full_header = ' '.join(header_parts)
                headers.append(full_header)
    
    return headers


def extract_financial_data_with_context(text, statement_type):
    """Extract financial data with context awareness"""
    
    # Define context-specific patterns
    context_patterns = {
        'income_statement': {
            'revenue': [r'revenue[s]?', r'sales', r'net\s+revenue[s]?'],
            'expenses': [r'expense[s]?', r'cost[s]?', r'operating\s+expense[s]?'],
            'net_income': [r'net\s+income', r'net\s+earnings', r'net\s+profit']
        },
        'balance_sheet': {
            'assets': [r'asset[s]?', r'total\s+asset[s]?'],
            'liabilities': [r'liabilit[y|ies]', r'total\s+liabilit[y|ies]'],
            'equity': [r'equity', r'shareholders?\s+equity', r'stockholders?\s+equity']
        },
        'cash_flow': {
            'operating': [r'operating\s+activities', r'cash\s+from\s+operations'],
            'investing': [r'investing\s+activities', r'cash\s+used\s+in\s+investing'],
            'financing': [r'financing\s+activities', r'cash\s+from\s+financing']
        }
    }
    
    # Extract data based on statement type
    if statement_type in context_patterns:
        extracted_data = {}
        for category, patterns in context_patterns[statement_type].items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    extracted_data[category] = matches
        return extracted_data
    
    return {}


def validate_extracted_data(metadata, table_data):
    """Validate extracted data for consistency"""
    
    validation_results = {
        'periods_consistent': False,
        'units_consistent': False,
        'data_complete': False,
        'warnings': []
    }
    
    # Check if periods are consistent
    if metadata.get('periods'):
        period_count = len(metadata['periods'])
        if table_data is not None and len(table_data.columns) > 1:
            expected_columns = period_count + 1  # +1 for description column
            if len(table_data.columns) >= expected_columns:
                validation_results['periods_consistent'] = True
            else:
                validation_results['warnings'].append(
                    f"Expected {expected_columns} columns but found {len(table_data.columns)}"
                )
    
    # Check if units are consistent
    if metadata.get('units'):
        validation_results['units_consistent'] = True
    
    # Check if data is complete
    if table_data is not None and not table_data.empty:
        validation_results['data_complete'] = True
    
    return validation_results


def intelligent_financial_parser(pdf_path, debug=False):
    """Main intelligent parsing function"""
    
    # Extract text using pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[0]  # We're working with a single extracted page
            text = page.extract_text()
            text_lines = text.split('\n')
    except Exception as e:
        if debug:
            print(f"Error extracting text: {e}")
        return None
    
    # Extract metadata
    metadata = {
        'company': extract_company_info(text),
        'statement_type': classify_statement_type(text),
        'periods': extract_period_info(text),
        'units': extract_units_info(text)
    }
    
    if debug:
        print(f"Extracted metadata: {metadata}")
    
    return metadata


def add_parsed_result_row(table_df, metadata, debug=False):
    """Add a 'parsed result' row to the table with metadata information"""
    
    if table_df is None or table_df.empty:
        return table_df
    
    # Create the parsed result row
    parsed_row = ['PARSED RESULT']
    
    # Add metadata information to each column
    for i in range(1, len(table_df.columns)):
        col_info = []
        
        # Add period information if available
        if metadata.get('periods') and i <= len(metadata['periods']):
            col_info.append(f"Period: {metadata['periods'][i-1]}")
        
        # Add units information if available
        if metadata.get('units'):
            units_str = '; '.join(metadata['units'])
            col_info.append(f"Units: {units_str}")
        
        # Add statement type
        if metadata.get('statement_type'):
            col_info.append(f"Type: {metadata['statement_type']}")
        
        # Add company name
        if metadata.get('company'):
            col_info.append(f"Company: {metadata['company']}")
        
        # Combine all information
        if col_info:
            parsed_row.append(' | '.join(col_info))
        else:
            parsed_row.append('')
    
    # Create a new DataFrame with the parsed result row
    new_df = pd.DataFrame([parsed_row], columns=table_df.columns)
    
    # Concatenate with original table
    result_df = pd.concat([new_df, table_df], ignore_index=True)
    
    if debug:
        print(f"Added parsed result row: {parsed_row}")
    
    return result_df


def extract_all_statements_to_json_only(pdf_path, output_path, pdf_name, debug=False):
    """
    Extract all financial statements from the PDF and return as JSON data.
    Returns JSON string with extracted statements.
    Also concatenates the extracted statement pages into a single PDF named with company and period.
    """
    output_path = Path(output_path)
    statements = [
        "CONSOLIDATED STATEMENTS OF INCOME",
        "CONSOLIDATED BALANCE SHEETS", 
        "CONSOLIDATED STATEMENTS OF CASH FLOWS"
    ]
    extracted_statements = []
    overall_metadata = {
        'company': None,
        'statement_types': [],
        'periods': [],
        'units': []
    }
    extracted_pdf_paths = []
    period_for_filename = None
    company_for_filename = None
    for statement in statements:
        click.echo(f"\n🔍 Looking for: {statement}")
        target_page = find_page_with_text(pdf_path, statement, 3)
        if target_page is None:
            click.echo(f"❌ No page found with text '{statement}'")
            continue
        click.echo(f"✅ Found {statement} on page {target_page}")
        extracted_pdf_path = extract_page(pdf_path, target_page, output_path)
        if extracted_pdf_path is None:
            click.echo(f"❌ Failed to extract page {target_page}")
            continue
        extracted_pdf_paths.append(str(extracted_pdf_path))
        table_df = extract_table_from_page(extracted_pdf_path, statement)
        if table_df is not None and not table_df.empty:
            statement_name = statement.replace("CONSOLIDATED STATEMENTS OF ", "").replace("CONSOLIDATED ", "").replace("'", "").replace(" ", "_")
            statement_metadata = intelligent_financial_parser(extracted_pdf_path)
            if statement_metadata:
                if statement_metadata.get('company') and not overall_metadata['company']:
                    overall_metadata['company'] = statement_metadata['company']
                if statement_metadata.get('statement_type'):
                    overall_metadata['statement_types'].append(statement_metadata['statement_type'])
                if statement_metadata.get('periods'):
                    overall_metadata['periods'].extend(statement_metadata['periods'])
                if statement_metadata.get('units'):
                    overall_metadata['units'].extend(statement_metadata['units'])
                # For filename: use first found period and company
                if not period_for_filename and statement_metadata.get('periods'):
                    period_for_filename = statement_metadata['periods'][0]
                if not company_for_filename and statement_metadata.get('company'):
                    company_for_filename = statement_metadata['company']
            statement_data = {
                "name": statement_name,
                "pageNumber": target_page,
                "headers": table_df.columns.tolist(),
                "tableData": [],
                "metadata": statement_metadata or {}
            }
            for _, row in table_df.iterrows():
                row_dict = {}
                for col in table_df.columns:
                    value = row[col]
                    if isinstance(value, pd.Series):
                        value = value.astype(str).to_list()
                        value = ", ".join(value)
                    if value is None or (isinstance(value, float) and pd.isna(value)):
                        row_dict[col] = ""
                    else:
                        row_dict[col] = str(value)
                statement_data["tableData"].append(row_dict)
            extracted_statements.append(statement_data)
            click.echo(f"✅ Extracted {statement} from page {target_page}")
        else:
            click.echo(f"❌ No table found for {statement}")
    if not extracted_statements:
        click.echo("❌ No statements were successfully extracted")
        return None
    # Clean up overall metadata (remove duplicates)
    overall_metadata['statement_types'] = list(set(overall_metadata['statement_types']))
    overall_metadata['periods'] = list(set(overall_metadata['periods']))
    overall_metadata['units'] = list(set(overall_metadata['units']))
    # --- Concatenate PDFs ---
    # Use "extracted_[raw_pdf_name]" format
    raw_pdf_name = Path(pdf_path).stem  # Get filename without extension
    concat_pdf_name = f"extracted_{raw_pdf_name}.pdf"
    concat_pdf_path = output_path / concat_pdf_name
    if extracted_pdf_paths:
        concatenate_pdfs(extracted_pdf_paths, concat_pdf_path)
        click.echo(f"📄 Concatenated PDF created: {concat_pdf_path}")
        
        # Delete individual PDF pages after concatenation
        for pdf_path_str in extracted_pdf_paths:
            try:
                Path(pdf_path_str).unlink()
                click.echo(f"🗑️  Deleted individual PDF: {Path(pdf_path_str).name}")
            except Exception as e:
                click.echo(f"⚠️  Failed to delete {Path(pdf_path_str).name}: {e}")
    else:
        concat_pdf_path = None
    # ---
    try:
        click.echo(f"🔍 Starting validation with {len(extracted_statements)} statements")
        validation_results = validate_financial_statements(extracted_statements)
        click.echo(f"✅ Validation completed: {validation_results['summary']['passed_checks']}/{validation_results['summary']['total_checks']} checks passed ({validation_results['summary']['pass_rate']}%)")
        click.echo(f"🔍 Validation results: {validation_results}")
    except Exception as e:
        click.echo(f"⚠️  Validation failed: {e}")
        import traceback
        click.echo(f"⚠️  Validation error details: {traceback.format_exc()}")
        validation_results = {
            'checklist_results': {},
            'summary': {'total_checks': 0, 'passed_checks': 0, 'failed_checks': 0, 'pass_rate': 0},
            'balance_sheet_totals': None
        }
    result = {
        "pdfName": pdf_name,
        "overallMetadata": overall_metadata,
        "statements": extracted_statements,
        "extractedCount": len(extracted_statements),
        "validation": validation_results,
        "concatenatedPdf": str(concat_pdf_path) if concat_pdf_path else None
    }
    click.echo(f"\n🎉 Successfully extracted {len(extracted_statements)} statements")
    return json.dumps(result)


def concatenate_pdfs(pdf_paths, output_path):
    """Concatenate multiple PDFs into a single PDF at output_path."""
    merger = PyPDF2.PdfWriter()
    for pdf_path in pdf_paths:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                merger.add_page(page)
    with open(output_path, 'wb') as fout:
        merger.write(fout)
    return output_path


if __name__ == '__main__':
    import sys
    
    # Check if called with arguments (from Java backend)
    if len(sys.argv) == 4:
        pdf_path = sys.argv[1]
        output_path = sys.argv[2]
        pdf_name = sys.argv[3]
        
        # Redirect click.echo to stderr so it doesn't interfere with JSON output
        import click
        original_echo = click.echo
        
        def stderr_echo(message):
            print(message, file=sys.stderr)
        
        click.echo = stderr_echo
        
        # Call the JSON function directly
        result = extract_all_statements_to_json_only(pdf_path, output_path, pdf_name)
        if result:
            print(result)  # Print JSON to stdout for Java to capture
            sys.exit(0)
        else:
            print("Failed to extract statements", file=sys.stderr)
            sys.exit(1)
    else:
        # Use Click interface for CLI
        process_pdf() 