#!/usr/bin/env python3
"""
Demo script that calls the same API endpoint as the web app.
"""

import sys
import requests
import json
from pathlib import Path
import contextlib
import io

# Configuration
PYTHON_API_URL = "http://localhost:5001"
OUTPUT_DIR = "output"

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

def test_api_health():
    """Test if the Python API is running"""
    try:
        response = requests.get(f"{PYTHON_API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Python API is running")
            return True
        else:
            print(f"❌ Python API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Python API health check error: {e}")
        return False

def print_table_data(statement, statement_number):
    """Print the complete table data for a statement"""
    print(f"\n{'='*80}")
    print(f"📊 COMPLETE TABLE DATA - Statement {statement_number}: {statement['name']}")
    print(f"{'='*80}")
    print(f"📄 Page: {statement['pageNumber']}")
    print(f"📋 Headers: {statement['headers']}")
    print(f"📈 Total Rows: {len(statement['tableData'])}")
    print(f"{'='*80}")
    
    # Print headers
    headers = statement['headers']
    header_line = " | ".join(f"{header:<30}" for header in headers)
    print(f"HEADERS: {header_line}")
    print("-" * len(header_line))
    
    # Print all rows
    for i, row in enumerate(statement['tableData'], 1):
        row_values = []
        for header in headers:
            value = row.get(header, "")
            # Truncate long values for better formatting
            if len(str(value)) > 30:
                value = str(value)[:27] + "..."
            row_values.append(f"{str(value):<30}")
        
        row_line = " | ".join(row_values)
        print(f"Row {i:2d}: {row_line}")
    
    print(f"{'='*80}")

def process_pdf_via_api(pdf_path, debug=False):
    """Process a PDF using the same API endpoint as the web app"""
    if not pdf_path.exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return None
    
    print(f"\n{'='*80}")
    print(f"🔍 Processing PDF via API: {pdf_path.name}")
    print(f"{'='*80}")
    
    try:
        # Prepare the request payload (same as what the backend sends)
        payload = {
            "pdf_path": str(pdf_path),
            "output_dir": OUTPUT_DIR
        }
        
        print(f"📤 Sending request to: {PYTHON_API_URL}/api/process-pdf-from-path")
        print(f"📁 PDF Path: {pdf_path}")
        print(f"📂 Output Directory: {OUTPUT_DIR}")
        
        # Make the API call (same endpoint as web app)
        response = requests.post(
            f"{PYTHON_API_URL}/api/process-pdf-from-path",
            json=payload,
            timeout=120  # 2 minutes timeout for processing
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"✅ PDF processed successfully!")
                
                # Extract and display results
                statements = data.get("statements", [])
                validation = data.get("validation")
                excel_path = data.get("excelPath")
                
                print(f"\n📊 Results:")
                print(f"   - Statements extracted: {len(statements)}")
                print(f"   - Excel file: {excel_path}")
                
                # Display statement details
                for i, statement in enumerate(statements, 1):
                    print(f"\n📋 Statement {i}: {statement['name']}")
                    print(f"   - Page: {statement['pageNumber']}")
                    print(f"   - Headers: {statement['headers']}")
                    print(f"   - Rows: {len(statement['tableData'])}")
                    
                    # Show first few rows if debug mode
                    if debug and statement['tableData']:
                        print(f"   - Sample data:")
                        for j, row in enumerate(statement['tableData'][:3]):  # Show first 3 rows
                            print(f"     Row {j+1}: {row}")
                
                # Print complete table data for each statement
                print(f"\n{'='*80}")
                print(f"📊 COMPLETE TABLE DATA FOR {pdf_path.name}")
                print(f"{'='*80}")
                
                for i, statement in enumerate(statements, 1):
                    print_table_data(statement, i)
                
                # Display validation results
                if validation:
                    summary = validation.get("summary", {})
                    print(f"\n🔍 Validation Results:")
                    print(f"   - Total checks: {summary.get('total_checks', 0)}")
                    print(f"   - Passed checks: {summary.get('passed_checks', 0)}")
                    print(f"   - Failed checks: {summary.get('failed_checks', 0)}")
                    print(f"   - Pass rate: {summary.get('pass_rate', 0)}%")
                    
                    # Show balance sheet totals if available
                    balance_sheet_totals = validation.get("balance_sheet_totals")
                    if balance_sheet_totals:
                        print(f"\n💰 Balance Sheet Totals:")
                        assets = balance_sheet_totals.get("assets")
                        if assets:
                            print(f"   - Assets: ${assets.get('reported', 0):,.0f} (calculated: ${assets.get('calculated', 0):,.0f})")
                            print(f"     - Matches: {'✅' if assets.get('matches') else '❌'}")
                        
                        liabilities = balance_sheet_totals.get("liabilities_equity")
                        if liabilities:
                            print(f"   - Liabilities & Equity: ${liabilities.get('reported', 0):,.0f} (calculated: ${liabilities.get('calculated', 0):,.0f})")
                            print(f"     - Matches: {'✅' if liabilities.get('matches') else '❌'}")
                
                print(f"\n{'='*60}")
                print(f"🎉 PROCESSING COMPLETE!")
                print(f"{'='*60}")
                return data
            else:
                print(f"❌ PDF processing failed: {data.get('error')}")
                return None
        else:
            print(f"❌ API request failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out - PDF processing took too long")
        return None
    except Exception as e:
        print(f"❌ Error processing PDF: {e}")
        return None

def main():
    # Create output directory
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    
    # Create console output file path
    console_output_path = output_path / "console_output"
    
    # Redirect all output to file
    with ConsoleOutputRedirector(console_output_path):
        # Check if Python API is running
        if not test_api_health():
            print("\n❌ Python API is not running. Please start the application with:")
            print("   ./start-app.sh")
            return
        
        # Find PDF files in documents directory
        docs_path = Path("documents")
        pdfs = sorted([p for p in docs_path.glob("*.pdf") if p.is_file()])
        
        if not pdfs:
            print(f"No PDF files found in {docs_path.resolve()}")
            return
        
        print(f"\n📁 Found {len(pdfs)} PDF file(s) in documents directory")
        
        # Parse --debug flag
        debug = '--debug' in sys.argv
        
        # Process each PDF
        for pdf_path in pdfs:
            result = process_pdf_via_api(pdf_path, debug=debug)
            if result:
                print(f"✅ Successfully processed: {pdf_path.name}")
            else:
                print(f"❌ Failed to process: {pdf_path.name}")
            
            # Add separator between files
            if pdf_path != pdfs[-1]:  # Not the last file
                print("\n" + "="*80 + "\n")
    
    print(f"\n📄 All console output has been saved to: {console_output_path}")

if __name__ == "__main__":
    main() 