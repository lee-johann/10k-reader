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
import tabula
import camelot
import openpyxl
import functools


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
    excel_path = extract_table_to_excel(extracted_pdf_path, output_path, method, debug)
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
        if len(parts) < 2:
            if debug:
                print(f'SKIPPED (too few parts): {repr(row_str)}')
            continue
        number_parts = []
        i = len(parts) - 1
        while i >= 0:
            part = parts[i]
            is_number = False
            is_bracketed_number = False
            if part.startswith('(') and part.endswith(')') and len(part) > 2:
                bracket_content = part[1:-1]
                if re.match(r'^[\d,]+$', bracket_content):
                    idx = row_str.find(part)
                    if idx == 0 or row_str[idx - 1] == ' ':
                        is_bracketed_number = True
                        is_number = True
            elif not '(' in part and not ')' in part:
                clean_part = part.replace(',', '')
                if re.match(r'^-?[\d]+\.?[\d]*$', clean_part):
                    is_number = True
            if is_number:
                if is_bracketed_number:
                    number_str = bracket_content.replace(',', '')
                    number_parts.insert(0, f"-{number_str}")
                else:
                    number_parts.insert(0, part.replace(',', ''))
                i -= 1
            else:
                break
        text_parts = parts[:i+1]
        if not text_parts or not number_parts:
            if debug:
                print(f'SKIPPED (no text or numbers): {repr(row_str)}')
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


def extract_table_to_excel(pdf_path, output_path, method, debug=False):
    """
    Extract tables from the PDF and save to Excel.
    Returns the path to the Excel file.
    """
    excel_path = output_path / "extracted_table.xlsx"
    
    # First, try to extract header information
    header_years = extract_header_info(pdf_path, debug)
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
                    processed_df = process_table_data(combined_df, debug)
                    
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
                            processed_df = process_table_data(combined_df, debug)
                            
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
                        processed_df = process_table_data(combined_df, debug)
                        
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


def extract_all_statements_to_excel(pdf_path, output_path, pdf_name, debug=False):
    """
    Extract all financial statements from the PDF and save to Excel with multiple tabs.
    Returns the path to the Excel file.
    """
    output_path = Path(output_path)
    excel_path = output_path / f"{pdf_name}_extracted.xlsx"
    statements = [
        "CONSOLIDATED STATEMENTS OF INCOME",
        "CONSOLIDATED BALANCE SHEETS", 
        "CONSOLIDATED STATEMENTS OF CASH FLOWS"
    ]
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        extracted_count = 0
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
            table_df = extract_table_from_page(extracted_pdf_path, statement, debug=debug)
            if table_df is not None and not table_df.empty:
                tab_name = statement.replace("CONSOLIDATED STATEMENTS OF ", "").replace("'", "").replace(" ", "_")
                tab_name = tab_name[:31]
                table_df.to_excel(writer, sheet_name=tab_name, index=False)
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


def extract_table_from_page(pdf_path, statement_name, debug=False):
    header_years = extract_header_info(pdf_path, debug=debug)
    if header_years:
        click.echo(f"📅 Found year headers: {header_years}")
    else:
        click.echo("⚠️  No year headers found, using default column names")
    methods_to_try = ['pdfplumber', 'camelot', 'tabula']
    for current_method in methods_to_try:
        try:
            click.echo(f"Trying table extraction with {current_method}...")
            if current_method == 'tabula':
                tables = tabula.read_pdf(str(pdf_path), pages='all')
                if tables:
                    combined_df = pd.concat(tables, ignore_index=True)
                    processed_df = process_table_data(combined_df, debug=debug)
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
                            processed_df = process_table_data(combined_df, debug=debug)
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
                                    if df.columns.duplicated().any():
                                        df.columns = [f"{col}_{i}" if df.columns.duplicated()[i] else col for i, col in enumerate(df.columns)]
                                    df = df.replace('', pd.NA).dropna(how='all')
                                    all_tables.append(df)
                    if all_tables:
                        combined_df = pd.concat(all_tables, ignore_index=True)
                        processed_df = process_table_data(combined_df, debug=debug)
                        if header_years and len(header_years) >= len(processed_df.columns) - 1:
                            new_columns = ['Description'] + header_years[:len(processed_df.columns) - 1]
                            processed_df.columns = new_columns
                        return processed_df
        except Exception as e:
            click.echo(f"❌ Error with {current_method}: {e}")
            continue
    return None


def extract_all_statements_to_json(pdf_path, output_path, pdf_name):
    """
    Extract all financial statements from the PDF and return as JSON data.
    Also creates Excel file locally for reference.
    Returns JSON string with extracted statements.
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
    
    extracted_statements = []
    
    # Create Excel writer for local file
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
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
                # Create statement name from statement
                statement_name = statement.replace("CONSOLIDATED STATEMENTS OF ", "").replace("CONSOLIDATED ", "").replace("'", "").replace(" ", "_")
                
                # Convert DataFrame to JSON-serializable format
                statement_data = {
                    "name": statement_name,
                    "pageNumber": target_page,
                    "headers": table_df.columns.tolist(),
                    "tableData": []
                }
                
                # Convert DataFrame rows to list of dictionaries
                for _, row in table_df.iterrows():
                    row_dict = {}
                    for col in table_df.columns:
                        value = row[col]
                        if pd.isna(value):
                            row_dict[col] = ""
                        else:
                            row_dict[col] = str(value)
                    statement_data["tableData"].append(row_dict)
                
                extracted_statements.append(statement_data)
                
                # Also write to Excel for local reference
                tab_name = statement.replace("CONSOLIDATED STATEMENTS OF ", "").replace("'", "").replace(" ", "_")
                tab_name = tab_name[:31]  # Excel tab names limited to 31 characters
                
                # Write to Excel tab
                table_df.to_excel(writer, sheet_name=tab_name, index=False)
                
                # Add comment to cell A1 with source information
                worksheet = writer.sheets[tab_name]
                cell_a1 = worksheet['A1']
                comment_text = f"From page {target_page} of {Path(pdf_path).name}"
                cell_a1.comment = openpyxl.comments.Comment(comment_text, "PDF Processor")
                
                click.echo(f"✅ Extracted {statement} from page {target_page}")
                click.echo(f"📊 Added to Excel tab '{tab_name}' with source comment")
            else:
                click.echo(f"❌ No table found for {statement}")
    
    if not extracted_statements:
        click.echo("❌ No statements were successfully extracted")
        return None
    
    # Return JSON string
    result = {
        "pdfName": pdf_name,
        "statements": extracted_statements,
        "extractedCount": len(extracted_statements),
        "excelPath": str(excel_path)
    }
    
    click.echo(f"\n🎉 Successfully extracted {len(extracted_statements)} statements")
    click.echo(f"📁 Excel file created locally: {excel_path}")
    return json.dumps(result)


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
        result = extract_all_statements_to_json(pdf_path, output_path, pdf_name)
        if result:
            print(result)  # Print JSON to stdout for Java to capture
            sys.exit(0)
        else:
            print("Failed to extract statements", file=sys.stderr)
            sys.exit(1)
    else:
        # Use Click interface for CLI
        process_pdf() 