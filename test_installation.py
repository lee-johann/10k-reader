#!/usr/bin/env python3
"""
Test script to verify that all dependencies are properly installed.
"""

import sys
import importlib


def test_import(module_name, package_name=None):
    """Test if a module can be imported."""
    try:
        importlib.import_module(module_name)
        print(f"✅ {package_name or module_name}")
        return True
    except ImportError as e:
        print(f"❌ {package_name or module_name}: {e}")
        return False


def main():
    """Test all required dependencies."""
    print("🔧 Testing PDF Processor Dependencies")
    print("=" * 50)
    
    # List of required modules and their display names
    modules = [
        ("click", "Click (CLI framework)"),
        ("PyPDF2", "PyPDF2 (PDF reading)"),
        ("pdfplumber", "PDFPlumber (PDF text extraction)"),
        ("pandas", "Pandas (Data manipulation)"),
        ("openpyxl", "OpenPyXL (Excel writing)"),
        ("tabula", "Tabula-py (Table extraction)"),
        ("camelot", "Camelot-py (Advanced table extraction)"),
        ("cv2", "OpenCV (Image processing)"),
    ]
    
    all_passed = True
    
    for module, name in modules:
        if not test_import(module, name):
            all_passed = False
    
    print("\n" + "=" * 50)
    
    if all_passed:
        print("🎉 All dependencies are installed correctly!")
        print("\nYou can now use the PDF processor:")
        print("  python pdf_processor.py your_document.pdf")
    else:
        print("❌ Some dependencies are missing.")
        print("\nPlease install missing dependencies:")
        print("  pip install -r requirements.txt")
        
        print("\nFor system dependencies on macOS:")
        print("  brew install ghostscript tcl-tk")
        
        print("\nFor system dependencies on Ubuntu/Debian:")
        print("  sudo apt-get install ghostscript python3-tk")


if __name__ == "__main__":
    main() 