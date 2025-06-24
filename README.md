# PDF Processor CLI Tool

A powerful command-line tool for processing PDF files, finding specific pages, extracting them, and converting tables to Excel format.

## Features

- 🔍 **Text Search**: Find pages containing specific text (case-insensitive)
- 📄 **Page Extraction**: Extract individual pages from PDFs
- 📊 **Table Extraction**: Convert PDF tables to Excel format
- 🛠️ **Multiple Methods**: Support for different table extraction methods
- 📁 **Organized Output**: Clean output directory structure

## Installation (with Virtual Environment)

1. **Run the setup script:**
   ```bash
   ./setup.sh
   ```
   This will:
   - Create a Python virtual environment in `.venv`
   - Install all Python dependencies inside the virtual environment
   - (On macOS/Linux) Prompt you to install system dependencies if needed

2. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

3. **(Optional) Test your installation:**
   ```bash
   python test_installation.py
   ```

## Usage

### Basic CLI Usage

```bash
python pdf_processor.py path/to/your/document.pdf
```

This will:
- Search for "CONSOLIDATED STATEMENTS OF INCOME" starting from page 10
- Extract the page containing this text
- Convert any tables on that page to Excel format
- Save results in the `./output` directory

### Demo Script

The demo script is pre-configured to use the sample file `documents/goog-10-k-2024.pdf`:

```bash
python demo.py
```

This will:
- Process `documents/goog-10-k-2024.pdf`
- Print the found page number prominently
- Extract the page and table as described above

### Advanced CLI Usage

```bash
python pdf_processor.py path/to/your/document.pdf \
  --search-text "CONSOLIDATED STATEMENTS OF INCOME" \
  --min-page 10 \
  --output-dir ./my_output \
  --method camelot
```

### Command Options

- `PDF_PATH`: Path to the PDF file to process
- `--search-text`: Text to search for (default: "CONSOLIDATED STATEMENTS OF INCOME")
- `--min-page`: Minimum page number to start searching from (default: 10)
- `--output-dir`: Output directory for extracted files (default: "./output")
- `--method`: Table extraction method (choices: tabula, camelot, pdfplumber, default: camelot)

### Table Extraction Methods

1. **camelot** (default): Best for complex tables with borders
2. **tabula**: Good for simple tables
3. **pdfplumber**: Versatile, works well with various table formats

## Output

The tool creates an organized output structure:

```
output/
├── page_X.pdf          # Extracted page
└── extracted_table.xlsx # Extracted table data
```

## Examples

### Example 1: Financial Document Processing
```bash
python pdf_processor.py financial_report.pdf
```

### Example 2: Custom Search
```bash
python pdf_processor.py report.pdf --search-text "BALANCE SHEET" --min-page 5
```

### Example 3: Different Table Extraction Method
```bash
python pdf_processor.py document.pdf --method pdfplumber
```

### Example 4: Run the Demo (uses documents/goog-10-k-2024.pdf)
```bash
python demo.py
```

## Troubleshooting

### Common Issues

1. **"No tables found"**: Try a different extraction method
2. **"No page found"**: Check if the search text exists in the PDF
3. **Installation errors**: Ensure all system dependencies are installed

### Performance Tips

- Use `camelot` for complex financial tables
- Use `pdfplumber` for simple data tables
- Use `tabula` for basic table extraction

## Requirements

- Python 3.7+
- All Python dependencies are installed in a virtual environment (`.venv`)
- Ghostscript (for table extraction)
- Tkinter (for some table extraction methods)

## License

This tool is provided as-is for educational and practical use. 