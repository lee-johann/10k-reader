#!/bin/bash

# Default parameters
DEFAULT_EDGE_TOLERANCE=100
DEFAULT_PDF_PATH="output/page_5.pdf"

# Check if arguments provided, otherwise use defaults
if [ $# -eq 0 ]; then
    EDGE_TOLERANCE=$DEFAULT_EDGE_TOLERANCE
    PDF_PATH=$DEFAULT_PDF_PATH
    echo "No arguments provided, using defaults:"
    echo "  Edge tolerance: $EDGE_TOLERANCE"
    echo "  PDF path: $PDF_PATH"
elif [ $# -eq 2 ]; then
    EDGE_TOLERANCE=$1
    PDF_PATH=$2
else
    echo "Usage: $0 [<edge_tolerance> <pdf_path>]"
    echo "If no arguments provided, uses defaults:"
    echo "  Edge tolerance: $DEFAULT_EDGE_TOLERANCE"
    echo "  PDF path: $DEFAULT_PDF_PATH"
    echo ""
    echo "Examples:"
    echo "  $0                    # Use defaults"
    echo "  $0 500 output/page_5.pdf"
    echo "  $0 100 documents/goog-10-k-2024.pdf"
    exit 1
fi

# Check if PDF file exists
if [ ! -f "$PDF_PATH" ]; then
    echo "Error: PDF file '$PDF_PATH' not found"
    exit 1
fi

echo "Running camelot stream with edge tolerance: $EDGE_TOLERANCE"
echo "PDF file: $PDF_PATH"

# Run camelot stream command
camelot stream -e "$EDGE_TOLERANCE" -plot contour "$PDF_PATH"