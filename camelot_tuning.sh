#!/bin/bash

# Default parameters
DEFAULT_EDGE_TOLERANCE=100
DEFAULT_ROW_TOL=10
DEFAULT_PDF_PATH="output/page_5.pdf"

# Check if arguments provided, otherwise use defaults
if [ $# -eq 0 ]; then
    EDGE_TOLERANCE=$DEFAULT_EDGE_TOLERANCE
    ROW_TOL=$DEFAULT_ROW_TOL
    PDF_PATH=$DEFAULT_PDF_PATH
    echo "No arguments provided, using defaults:"
    echo "  Edge tolerance: $EDGE_TOLERANCE"
    echo "  Row tolerance: $ROW_TOL"
    echo "  PDF path: $PDF_PATH"
elif [ $# -eq 3 ]; then
    EDGE_TOLERANCE=$1
    ROW_TOL=$2
    PDF_PATH=$3
elif [ $# -eq 2 ]; then
    EDGE_TOLERANCE=$1
    ROW_TOL=$DEFAULT_ROW_TOL
    PDF_PATH=$2
else
    echo "Usage: $0 [<edge_tolerance> [<row_tol>] <pdf_path>]"
    echo "If no arguments provided, uses defaults:"
    echo "  Edge tolerance: $DEFAULT_EDGE_TOLERANCE"
    echo "  Row tolerance: $DEFAULT_ROW_TOL"
    echo "  PDF path: $DEFAULT_PDF_PATH"
    echo ""
    echo "Examples:"
    echo "  $0                    # Use defaults"
    echo "  $0 500 output/page_5.pdf"
    echo "  $0 100 3 output/page_5.pdf"
    echo "  $0 100 4 documents/goog-10-k-2024.pdf"
    exit 1
fi

# Check if PDF file exists
if [ ! -f "$PDF_PATH" ]; then
    echo "Error: PDF file '$PDF_PATH' not found"
    exit 1
fi

echo "Running camelot stream with edge tolerance: $EDGE_TOLERANCE"
echo "Row tolerance: $ROW_TOL"
echo "PDF file: $PDF_PATH"

# Run camelot stream command for visual plotting
echo "=== Visual Plotting ==="
camelot stream -e "$EDGE_TOLERANCE" -plot contour "$PDF_PATH"

# Extract and print table data using Python
echo ""
echo "=== Extracted Table Data ==="
python3 -c "
import camelot
import sys

try:
    # Set DYLD_LIBRARY_PATH for macOS if needed
    import os
    if sys.platform == 'darwin':
        homebrew_lib = '/opt/homebrew/lib'
        if os.path.exists(homebrew_lib):
            current_dyld_path = os.environ.get('DYLD_LIBRARY_PATH', '')
            if homebrew_lib not in current_dyld_path:
                if current_dyld_path:
                    os.environ['DYLD_LIBRARY_PATH'] = f'{homebrew_lib}:{current_dyld_path}'
                else:
                    os.environ['DYLD_LIBRARY_PATH'] = homebrew_lib
    
    tables = camelot.read_pdf('$PDF_PATH', pages='1', flavor='stream', edge_tol=$EDGE_TOLERANCE, row_tol=$ROW_TOL, strip_text='\\n')
    
    if tables:
        print(f'Found {len(tables)} table(s)')
        for i, table in enumerate(tables):
            print(f'\\nTable {i}:')
            print(f'Shape: {table.df.shape}')
            print(f'Accuracy: {table.parsing_report[\"accuracy\"]:.2f}%')
            print(f'Whitespace: {table.parsing_report[\"whitespace\"]:.2f}%')
            print('\\nData:')
            print(table.df.to_string())
    else:
        print('No tables found')
        
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
"