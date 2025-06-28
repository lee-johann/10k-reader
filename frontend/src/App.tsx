import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/esm/Page/AnnotationLayer.css';
import 'react-pdf/dist/esm/Page/TextLayer.css';

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;

interface StatementData {
  name: string;
  pageNumber: number;
  tableData: Array<{ [key: string]: string }>;
  headers: string[];
}

interface ValidationResults {
  checklistResults: { [key: string]: boolean };
  summary: {
    totalChecks: number;
    passedChecks: number;
    failedChecks: number;
    passRate: number;
  };
  balanceSheetTotals?: {
    assets?: {
      calculated: number;
      reported: number;
      difference: number;
      matches: boolean;
    };
    liabilitiesEquity?: {
      calculated: number;
      reported: number;
      difference: number;
      matches: boolean;
    };
  };
}

interface ProcessingResult {
  pdfUrl?: string;
  statements: StatementData[];
  message: string;
  success: boolean;
  validation?: ValidationResults;
}

function App() {
  const [availablePdfs, setAvailablePdfs] = useState<string[]>([]);
  const [selectedPdf, setSelectedPdf] = useState<string>('');
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [extractingTables, setExtractingTables] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<string>('');
  const [hoveredValue, setHoveredValue] = useState<string>('');
  const [hoveredPage, setHoveredPage] = useState<number | null>(null);
  const [showFloatingPage, setShowFloatingPage] = useState(false);
  const [floatingPageNumber, setFloatingPageNumber] = useState<number | null>(null);
  const [floatingPagePosition, setFloatingPagePosition] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const pdfViewerRef = useRef<HTMLDivElement>(null);
  const floatingPageRef = useRef<HTMLDivElement>(null);
  const [debugMode, setDebugMode] = useState(false);
  const [markedCells, setMarkedCells] = useState<Set<string>>(new Set());
  const [anchorCell, setAnchorCell] = useState<{ row: number, col: number } | null>(null);
  const [currentCell, setCurrentCell] = useState<{ row: number, col: number } | null>(null);
  const [isSelecting, setIsSelecting] = useState(false);
  const [selectedCells, setSelectedCells] = useState<Set<string>>(new Set());
  const [hoverToken, setHoverToken] = useState(0);
  const hoverTokenRef = useRef(0);

  // Load available PDFs on component mount
  useEffect(() => {
    loadAvailablePdfs();
  }, []);

  // Set initial active tab when result is loaded
  useEffect(() => {
    if (result && result.success && result.statements.length > 0) {
      setActiveTab(result.statements[0].name);
    }
  }, [result]);

  // Log extracted PDF and page numbers to console
  useEffect(() => {
    if (result && result.success && result.statements.length > 0) {
      console.log('Extracted PDF:', selectedPdf);
      result.statements.forEach(statement => {
        console.log(`Statement: ${statement.name}, Page: ${statement.pageNumber}`);
      });
    }
  }, [result, selectedPdf]);

  // Effect to highlight text in PDF when hovering over table cells
  useEffect(() => {
    if (hoveredValue && hoveredPage && pdfViewerRef.current) {
      hoverTokenRef.current += 1;
      const newToken = hoverTokenRef.current;
      setHoverToken(newToken);
      showFloatingPageOverlay(hoveredValue, hoveredPage, newToken);
    } else if (!hoveredValue) {
      if (pdfViewerRef.current) {
        removeHighlights(pdfViewerRef.current);
      }
      setShowFloatingPage(false);
      setFloatingPageNumber(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hoveredValue, hoveredPage]);

  // Update PDF highlight when multi-cell selection changes (e.g., after shift-click)
  useEffect(() => {
    if (
      selectedCells.size > 1 &&
      showFloatingPage &&
      floatingPageNumber &&
      activeTab &&
      anchorCell
    ) {
      const newToken = hoverTokenRef.current + 1;
      hoverTokenRef.current = newToken;
      setHoverToken(newToken);
      showFloatingPageOverlay(hoveredValue, floatingPageNumber, newToken);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCells, anchorCell]);

  // Function to remove all highlights
  const removeHighlights = (element: Element) => {
    element.querySelectorAll('.highlighted').forEach(el => {
      el.classList.remove('highlighted');
    });
    // Remove yellow highlight overlays
    element.querySelectorAll('.yellow-highlight-overlay').forEach(box => {
      box.remove();
    });
    // Remove debug number boxes if present
    element.querySelectorAll('.debug-number-box').forEach(box => {
      box.remove();
    });
  };

  // Helper to get all selected cell values for a given page
  const getSelectedValuesForPage = (statementName: string, pageNumber: number) => {
    if (!result || !result.statements) return [];
    const statement = result.statements.find(s => s.name === statementName && s.pageNumber === pageNumber);
    if (!statement) return [];
    const values: string[] = [];
    statement.tableData.forEach((row, rowIdx) => {
      statement.headers.forEach((header, colIdx) => {
        const key = getCellKey(statementName, rowIdx, colIdx);
        if (selectedCells.has(key)) {
          values.push(row[header] || '');
        }
      });
    });
    return values;
  };

  // Show floating page overlay (now takes hoverToken)
  const showFloatingPageOverlay = async (value: string, pageNumber: number, token: number) => {
    try {
      const pageElement = pdfViewerRef.current?.querySelector(`[data-page-number="${pageNumber}"]`);
      if (!pageElement) return;
      const rect = pageElement.getBoundingClientRect();
      setFloatingPagePosition({ x: rect.left, y: rect.top, width: rect.width, height: rect.height });
      setFloatingPageNumber(pageNumber);
      setShowFloatingPage(true);
      setTimeout(() => {
        let values: string[] = [];
        // Only use selectedCells if multi-cell selection is active
        if (selectedCells.size > 1 && activeTab) {
          values = getSelectedValuesForPage(activeTab, pageNumber);
        }
        // Always add hovered value if not already in the list
        if (value && !values.includes(value)) {
          values.push(value);
        }
        // Remove empty strings
        values = values.filter(v => v !== '');
        console.log('[DEBUG] Values to highlight in PDF:', values);
        highlightInFloatingPage(values, pageNumber, token);
      }, 100);
    } catch (error) {
      console.error('Error showing floating page overlay:', error);
    }
  };

  // Helper to get PDF page viewBox (width, height) from PDF.js
  const getPdfPageViewBox = async (pdfUrl: string, pageNumber: number) => {
    if (typeof pdfjs === 'undefined') return { width: 0, height: 0 };
    const loadingTask = pdfjs.getDocument(pdfUrl);
    const pdf = await loadingTask.promise;
    const page = await pdf.getPage(pageNumber);
    const view = page.view;
    return { width: view[2], height: view[3] };
  };

  // Highlight in the floating page (now takes an array of values)
  const highlightInFloatingPage = async (values: string[], pageNumber: number, token: number) => {
    if (token !== hoverTokenRef.current) return;
    try {
      if (!floatingPageRef.current) return;
      removeHighlights(floatingPageRef.current);
      const textItems = await extractTextWithCoordinates(`/documents/${selectedPdf}`, pageNumber);
      const normalizedValues = values.map(normalizeNumber).filter(v => v !== '');
      console.log('[DEBUG] All extracted text items for page', pageNumber, ':');
      textItems.forEach((item, idx) => {
        console.log(`  [${idx}] text: "${item.text}", normalized: "${normalizeNumber(item.text)}"`);
      });
      const matchingItems = textItems.filter(item => {
        const normalizedText = normalizeNumber(item.text);
        return normalizedValues.some(nv => shouldHighlight(nv, normalizedText, '', item.text));
      });
      console.log('[DEBUG] Highlighting items:', matchingItems.map(i => i.text));
      const canvasElement = floatingPageRef.current.querySelector('canvas');
      if (!canvasElement) return;
      const canvasContainer = canvasElement.closest('.react-pdf__Page__canvas-container') || canvasElement.parentElement;
      if (!canvasContainer) return;
      const canvasWidth = canvasElement.width;
      const canvasHeight = canvasElement.height;
      const displayWidth = canvasElement.offsetWidth;
      const displayHeight = canvasElement.offsetHeight;
      const { width: pdfWidth, height: pdfHeight } = await getPdfPageViewBox(`/documents/${selectedPdf}`, pageNumber);
      const scaleX = displayWidth / pdfWidth;
      const scaleY = displayHeight / pdfHeight;
      matchingItems.forEach((item, index) => {
        const [a, b, c, d, e, f] = item.transform;
        const x = e;
        const y = f;
        const width = a * item.width;
        const height = Math.abs(d);
        const displayX = x * scaleX;
        const displayY = displayHeight - ((y + height) * scaleY);
        // Estimate highlight width using font size and a character width ratio
        const fontSize = Math.abs(d); // d is usually the font size, may be negative
        const charWidthRatio = 0.5; // Adjust this value as needed for best fit
        const matchedValue = values.find(v => normalizeNumber(v) === normalizeNumber(item.text)) || item.text;
        const valueLength = matchedValue.length;
        const highlightWidth = fontSize * charWidthRatio * valueLength * scaleX;
        const highlightLeft = displayX - 2;
        console.log('[DEBUG] Creating highlight overlay:', {
          text: item.text,
          left: highlightLeft,
          top: displayY - 2,
          width: highlightWidth + 4,
          height: height * scaleY + 4
        });
        // If the highlight visually covers too much, adjust the calculation above
        const highlight = document.createElement('div');
        highlight.className = 'yellow-highlight-overlay';
        highlight.style.position = 'absolute';
        highlight.style.left = `${highlightLeft}px`;
        highlight.style.top = `${displayY - 2}px`;
        highlight.style.width = `${highlightWidth + 4}px`;
        highlight.style.height = `${height * scaleY + 4}px`;
        highlight.style.backgroundColor = 'rgba(255, 255, 0, 0.5)';
        highlight.style.borderRadius = '4px';
        highlight.style.pointerEvents = 'none';
        highlight.style.zIndex = '1001';
        highlight.title = `Matched: ${item.text}`;
        canvasContainer.appendChild(highlight);
      });
    } catch (error) {
      console.error('Error highlighting in floating page:', error);
    }
  };

  // Alternative method: Use PDF.js directly for better text extraction
  const extractTextWithCoordinates = async (pdfUrl: string, pageNumber: number) => {
    try {
      console.log('Extracting text with PDF.js from:', pdfUrl, 'page:', pageNumber);

      // Ensure PDF.js is loaded
      if (typeof pdfjs === 'undefined') {
        console.error('PDF.js is not loaded');
        return [];
      }

      // Load PDF using PDF.js
      const loadingTask = pdfjs.getDocument(pdfUrl);
      const pdf = await loadingTask.promise;
      console.log('PDF loaded, pages:', pdf.numPages);

      const page = await pdf.getPage(pageNumber);
      console.log('Page loaded:', pageNumber);

      // Get text content with positioning
      const textContent = await page.getTextContent();
      console.log('Text content extracted, items:', textContent.items.length);

      // Extract text items with coordinates
      const textItems = textContent.items.map((item: any) => ({
        text: item.str,
        x: item.transform[4], // x coordinate
        y: item.transform[5], // y coordinate
        width: item.width,
        height: item.height,
        fontName: item.fontName,
        transform: item.transform // include the full transform for accurate positioning
      }));

      console.log('PDF.js extracted text items:', textItems.length);
      // Log first few items for debugging
      textItems.slice(0, 5).forEach((item, index) => {
        console.log(`Item ${index}: "${item.text}" at (${item.x}, ${item.y})`);
      });

      return textItems;
    } catch (error) {
      console.error('PDF.js extraction error:', error);
      return [];
    }
  };

  // Function to normalize numbers for comparison
  const normalizeNumber = (value: string): string => {
    if (!value) return '';

    // Remove all non-numeric characters except minus sign and decimal point
    let normalized = value.replace(/[^\d.-]/g, '');

    // Handle negative numbers in brackets like (3,154) -> -3154
    if (value.includes('(') && value.includes(')')) {
      normalized = '-' + normalized.replace(/[()]/g, '');
    }

    // Remove leading zeros but keep decimal numbers
    normalized = normalized.replace(/^0+(\d)/, '$1');

    return normalized;
  };

  // Function to determine if text should be highlighted
  const shouldHighlight = (normalizedHovered: string, normalizedText: string, originalHovered: string, originalText: string): boolean => {
    // Only allow exact match after normalization
    return normalizedHovered === normalizedText && normalizedHovered !== '';
  };

  const loadAvailablePdfs = async () => {
    try {
      const response = await axios.get<string[]>('/api/pdf/documents');
      setAvailablePdfs(response.data);
    } catch (err) {
      console.error('Failed to load PDFs:', err);
    }
  };

  const handlePdfSelect = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedPdf(event.target.value);
    setResult(null);
  };

  const handleProcess = async () => {
    if (!selectedPdf) return;

    setLoading(true);
    setValidating(false);
    setExtractingTables(false);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('filename', selectedPdf);

      const response = await axios.post<ProcessingResult>('/api/pdf/process-document', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.success) {
        // Phase 1: Show PDF immediately (without tables or validation)
        const resultWithPdfOnly = {
          ...response.data,
          statements: [], // Remove statements initially
          validation: undefined // Remove validation data initially
        };
        setResult(resultWithPdfOnly);
        setLoading(false);

        // Phase 2: Show table extraction loading
        setExtractingTables(true);

        // Simulate table extraction time for better UX
        setTimeout(() => {
          // Show result with tables but no validation
          const resultWithTables = {
            ...response.data,
            validation: undefined // Remove validation data initially
          };
          setResult(resultWithTables);
          setExtractingTables(false);

          if (response.data.statements.length > 0) {
            setCurrentPage(response.data.statements[0].pageNumber);
          }

          // Phase 3: If validation data exists, show it after a brief delay
          if (response.data.validation) {
            console.log('Validation data found:', response.data.validation);
            setValidating(true);
            // Simulate validation processing time for better UX
            setTimeout(() => {
              console.log('Setting full result with validation');
              setResult(response.data); // Show full result with validation
              setValidating(false);
            }, 1000);
          } else {
            console.log('No validation data found in response');
          }
        }, 1500); // Table extraction takes longer than validation
      } else {
        console.error('Processing failed:', response.data.message);
        setLoading(false);
      }
    } catch (err) {
      console.error('Failed to process PDF:', err);
      setLoading(false);
    }
  };

  const handleTabClick = (statementName: string, pageNumber: number) => {
    setActiveTab(statementName);
    setCurrentPage(pageNumber);

    // Scroll to the specific page in the PDF with faster scrolling
    if (pdfViewerRef.current && numPages) {
      const pageElement = pdfViewerRef.current.querySelector(`[data-page-number="${pageNumber}"]`);
      if (pageElement) {
        pageElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
          inline: 'nearest'
        });
      }
    }
  };

  const handleTableCellHover = (value: string, pageNumber: number) => {
    console.log('[DEBUG] Hovered cell value:', value, 'Page:', pageNumber);
    setHoveredValue(value);
    setHoveredPage(pageNumber);

    // If not multi-selecting, clear selectedCells so only hovered cell is considered
    if (!isSelecting && selectedCells.size <= 1) {
      setSelectedCells(new Set());
    }
    console.log('[DEBUG] selectedCells after hover:', Array.from(selectedCells));

    // Scroll to the specific page in the PDF
    if (pdfViewerRef.current && numPages) {
      const pageElement = pdfViewerRef.current.querySelector(`[data-page-number="${pageNumber}"]`);
      if (pageElement) {
        const rect = pageElement.getBoundingClientRect();
        const containerRect = pdfViewerRef.current.getBoundingClientRect();

        // If page is not visible, scroll to it
        if (rect.top < containerRect.top || rect.bottom > containerRect.bottom) {
          pageElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
            inline: 'nearest'
          });
        }
      }
    }
  };

  const handleTableCellLeave = () => {
    setHoveredValue('');
    setHoveredPage(null);
  };

  // Helper to generate a unique key for a cell
  const getCellKey = (statementName: string, rowIdx: number, colIdx: number) => `${statementName}|${rowIdx}|${colIdx}`;

  // Helper to get all cell keys in a rectangle
  const getCellRangeKeys = (statementName: string, start: { row: number, col: number }, end: { row: number, col: number }) => {
    const keys: string[] = [];
    const rowMin = Math.min(start.row, end.row);
    const rowMax = Math.max(start.row, end.row);
    const colMin = Math.min(start.col, end.col);
    const colMax = Math.max(start.col, end.col);
    for (let r = rowMin; r <= rowMax; r++) {
      for (let c = colMin; c <= colMax; c++) {
        keys.push(getCellKey(statementName, r, c));
      }
    }
    return keys;
  };

  // Handler for mouse down (start selection or shift-click selection)
  const handleCellMouseDown = (e: React.MouseEvent, statementName: string, rowIdx: number, colIdx: number) => {
    if (e.button !== 0) return; // Only left click
    if (e.shiftKey && anchorCell) {
      // Shift-click: select rectangle from anchor to this cell
      const keys = getCellRangeKeys(statementName, anchorCell, { row: rowIdx, col: colIdx });
      setSelectedCells(new Set(keys));
      // Do NOT update anchorCell here
    } else {
      // Normal click: set anchor and select just this cell
      setAnchorCell({ row: rowIdx, col: colIdx });
      setCurrentCell({ row: rowIdx, col: colIdx });
      setIsSelecting(true);
      setSelectedCells(new Set([getCellKey(statementName, rowIdx, colIdx)]));
    }
  };

  // Handler for mouse over (drag selection)
  const handleCellMouseOver = (e: React.MouseEvent, statementName: string, rowIdx: number, colIdx: number) => {
    if (!isSelecting || !anchorCell) return;
    setCurrentCell({ row: rowIdx, col: colIdx });
    const keys = getCellRangeKeys(statementName, anchorCell, { row: rowIdx, col: colIdx });
    setSelectedCells(new Set(keys));
  };

  // Handler for mouse up (end selection)
  const handleCellMouseUp = () => {
    setIsSelecting(false);
    setCurrentCell(null);
    // Do NOT clear anchorCell here
  };

  // Add event listeners to handle mouse up outside the table
  useEffect(() => {
    if (isSelecting) {
      window.addEventListener('mouseup', handleCellMouseUp);
      return () => window.removeEventListener('mouseup', handleCellMouseUp);
    }
  }, [isSelecting]);

  // Handler for right-click (context menu) on a cell
  const handleCellRightClick = (e: React.MouseEvent, statementName: string, rowIdx: number, colIdx: number) => {
    e.preventDefault();
    const key = getCellKey(statementName, rowIdx, colIdx);
    if (selectedCells.size > 1 && selectedCells.has(key)) {
      // If right-clicking a cell within the selection, mark/unmark the whole selection
      setMarkedCells(prev => {
        const newSet = new Set(prev);
        const allSelectedGreen = Array.from(selectedCells).every(k => newSet.has(k));
        if (allSelectedGreen) {
          selectedCells.forEach(k => newSet.delete(k));
        } else {
          selectedCells.forEach(k => newSet.add(k));
        }
        return newSet;
      });
      setSelectedCells(new Set());
    } else {
      // Otherwise, just toggle this cell
      setMarkedCells(prev => {
        const newSet = new Set(prev);
        if (newSet.has(key)) {
          newSet.delete(key);
        } else {
          newSet.add(key);
        }
        return newSet;
      });
      setSelectedCells(new Set());
    }
  };

  return (
    <div className="app">
      <div className="container">
        <div className="upload-section">
          <h1>PDF Financial Statement Processor</h1>
          <p>Select a PDF from the documents folder to extract financial statements</p>

          <div className="document-selector">
            <label htmlFor="pdf-select">Choose a PDF document:</label>
            <select
              id="pdf-select"
              value={selectedPdf}
              onChange={handlePdfSelect}
              disabled={loading}
            >
              <option value="">-- Select a PDF --</option>
              {availablePdfs.map((pdf, index) => (
                <option key={index} value={pdf}>
                  {pdf}
                </option>
              ))}
            </select>

            {selectedPdf && (
              <button
                className="process-button"
                onClick={handleProcess}
                disabled={loading}
              >
                {loading ? 'Processing...' : 'Process PDF'}
              </button>
            )}
          </div>

          {result && result.success && (
            <div className="results-section">
              <div className="pdf-viewer" ref={pdfViewerRef}>
                <h3>PDF Viewer</h3>
                <Document
                  file={`/documents/${selectedPdf}`}
                  onLoadSuccess={({ numPages }) => setNumPages(numPages)}
                >
                  {numPages && Array.from(new Array(numPages), (el, index) => (
                    <Page
                      key={`page_${index + 1}`}
                      pageNumber={index + 1}
                      renderTextLayer={true}
                      renderAnnotationLayer={false}
                      data-page-number={index + 1}
                    />
                  ))}
                </Document>
              </div>

              {/* Table Extraction Loading Indicator */}
              {extractingTables && (
                <div className="table-extraction-loading">
                  <h3>Extracting Financial Tables</h3>
                  <div className="loading-indicator">
                    <div className="spinner"></div>
                    <p>Analyzing PDF structure and extracting table data...</p>
                    <p className="loading-detail">Using hybrid extraction (Camelot + pdfplumber) for optimal results</p>
                  </div>
                </div>
              )}

              {/* Tables Section - Only show when tables are extracted */}
              {result.statements.length > 0 && !extractingTables && (
                <div className="tables-section">
                  <h3>Extracted Tables</h3>
                  <div className="tabs">
                    {result.statements.map((statement, index) => (
                      <button
                        key={statement.name}
                        className={`tab ${activeTab === statement.name ? 'active' : ''}`}
                        onClick={() => handleTabClick(statement.name, statement.pageNumber)}
                      >
                        {statement.name} (Page {statement.pageNumber})
                      </button>
                    ))}
                  </div>
                  <div className="table-content">
                    {result.statements.length > 0 && (
                      <div>
                        {(() => {
                          const activeStatement = result.statements.find(s => s.name === activeTab) || result.statements[0];
                          return (
                            <div>
                              <h4>{activeStatement.name} (Page {activeStatement.pageNumber})</h4>
                              <div className="table-container">
                                <table>
                                  <thead>
                                    <tr>
                                      {activeStatement.headers.map((header: string, index: number) => (
                                        <th key={index}>{header}</th>
                                      ))}
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {activeStatement.tableData.map((row: { [key: string]: string }, rowIndex: number) => (
                                      <tr key={rowIndex}>
                                        {activeStatement.headers.map((header: string, colIndex: number) => (
                                          <td
                                            key={colIndex}
                                            onMouseEnter={(e) => handleTableCellHover(row[header] || '', activeStatement.pageNumber)}
                                            onMouseLeave={handleTableCellLeave}
                                            onContextMenu={e => handleCellRightClick(e, activeStatement.name, rowIndex, colIndex)}
                                            onMouseDown={e => handleCellMouseDown(e, activeStatement.name, rowIndex, colIndex)}
                                            onMouseOver={e => handleCellMouseOver(e, activeStatement.name, rowIndex, colIndex)}
                                            className={
                                              (markedCells.has(getCellKey(activeStatement.name, rowIndex, colIndex)) ? 'green-marked-cell ' : '') +
                                              (selectedCells.has(getCellKey(activeStatement.name, rowIndex, colIndex)) ? 'blue-selected-cell' : '')
                                            }
                                            style={{ userSelect: 'none' }}
                                          >
                                            {row[header] || ''}
                                          </td>
                                        ))}
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Validation Loading Indicator */}
          {result && result.success && validating && (
            <div className="validation-loading">
              <h3>Financial Statement Validation</h3>
              <div className="loading-indicator">
                <div className="spinner"></div>
                <p>Running financial validation checks...</p>
                <p className="loading-detail">Analyzing balance sheet totals, income statement ratios, and cross-statement consistency</p>
              </div>
            </div>
          )}

          {/* Financial Statement Checklist Section */}
          {result && result.success && !validating && result.validation && (
            <div className="checklist-section">
              <h3>Financial Statement Checklist</h3>
              <div className="validation-summary">
                <p>
                  <strong>Validation Summary:</strong> {result.validation.summary.passedChecks}/{result.validation.summary.totalChecks} checks passed ({result.validation.summary.passRate}%)
                </p>
                {result.validation.balanceSheetTotals && (
                  <div className="balance-sheet-totals">
                    <p><strong>Balance Sheet Totals:</strong></p>
                    {result.validation.balanceSheetTotals.assets && (
                      <p>Assets: {result.validation.balanceSheetTotals.assets.matches ? '✅' : '❌'}
                        Calculated: ${result.validation.balanceSheetTotals.assets.calculated.toLocaleString()},
                        Reported: ${result.validation.balanceSheetTotals.assets.reported.toLocaleString()}
                        {!result.validation.balanceSheetTotals.assets.matches &&
                          ` (Difference: $${result.validation.balanceSheetTotals.assets.difference.toLocaleString()})`}
                      </p>
                    )}
                    {result.validation.balanceSheetTotals.liabilitiesEquity && (
                      <p>Liabilities + Equity: {result.validation.balanceSheetTotals.liabilitiesEquity.matches ? '✅' : '❌'}
                        Calculated: ${result.validation.balanceSheetTotals.liabilitiesEquity.calculated.toLocaleString()},
                        Reported: ${result.validation.balanceSheetTotals.liabilitiesEquity.reported.toLocaleString()}
                        {!result.validation.balanceSheetTotals.liabilitiesEquity.matches &&
                          ` (Difference: $${result.validation.balanceSheetTotals.liabilitiesEquity.difference.toLocaleString()})`}
                      </p>
                    )}
                  </div>
                )}
              </div>
              <div className="checklist-container">
                <div className="checklist-category">
                  <h4>Balance Sheet Checks</h4>
                  <div className="checklist-items">
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_1 || false} disabled />
                      <span>Assets = Liabilities + Stockholders' Equity</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_2 || false} disabled />
                      <span>Current assets &gt; Current liabilities (working capital positive)</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_3 || false} disabled />
                      <span>Cash and cash equivalents reasonable level</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_4 || false} disabled />
                      <span>Accounts receivable aging reasonable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_5 || false} disabled />
                      <span>Inventory levels appropriate</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_6 || false} disabled />
                      <span>Property, plant & equipment properly valued</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_7 || false} disabled />
                      <span>Goodwill and intangibles reasonable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_8 || false} disabled />
                      <span>Debt levels manageable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.balance_sheet_9 || false} disabled />
                      <span>Retained earnings consistent with history</span>
                    </label>
                  </div>
                </div>

                <div className="checklist-category">
                  <h4>Income Statement Checks</h4>
                  <div className="checklist-items">
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_1 || false} disabled />
                      <span>Revenue recognition appropriate</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_2 || false} disabled />
                      <span>Gross margin consistent with industry</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_3 || false} disabled />
                      <span>Operating expenses reasonable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_4 || false} disabled />
                      <span>EBITDA margins stable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_5 || false} disabled />
                      <span>Interest expense coverage adequate</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_6 || false} disabled />
                      <span>Tax rate reasonable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_7 || false} disabled />
                      <span>Net income growth sustainable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.income_statement_8 || false} disabled />
                      <span>EPS calculations accurate</span>
                    </label>
                  </div>
                </div>

                <div className="checklist-category">
                  <h4>Cash Flow Statement Checks</h4>
                  <div className="checklist-items">
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_1 || false} disabled />
                      <span>Operating cash flow positive</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_2 || false} disabled />
                      <span>Operating cash flow &gt; Net income</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_3 || false} disabled />
                      <span>Capital expenditures reasonable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_4 || false} disabled />
                      <span>Free cash flow positive</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_5 || false} disabled />
                      <span>Dividend payments sustainable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_6 || false} disabled />
                      <span>Share repurchases appropriate</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_7 || false} disabled />
                      <span>Debt issuance/repayment reasonable</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cash_flow_8 || false} disabled />
                      <span>Cash balance changes logical</span>
                    </label>
                  </div>
                </div>

                <div className="checklist-category">
                  <h4>Cross-Statement Checks</h4>
                  <div className="checklist-items">
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_1 || false} disabled />
                      <span>Net income flows to retained earnings</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_2 || false} disabled />
                      <span>Depreciation consistent across statements</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_3 || false} disabled />
                      <span>Dividends reduce retained earnings</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_4 || false} disabled />
                      <span>Capital expenditures increase PP&E</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_5 || false} disabled />
                      <span>Debt changes reflected in both statements</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_6 || false} disabled />
                      <span>Working capital changes consistent</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_7 || false} disabled />
                      <span>Tax payments align with tax expense</span>
                    </label>
                    <label className="checklist-item">
                      <input type="checkbox" checked={result.validation?.checklistResults.cross_statement_8 || false} disabled />
                      <span>Stock-based compensation properly recorded</span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Debug: Show validation status */}
          {result && result.success && debugMode && (
            <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#f0f0f0', borderRadius: '4px', fontSize: '12px' }}>
              <strong>DEBUG - Validation Status:</strong><br />
              Validating: {String(validating)}<br />
              Has validation data: {String(!!result.validation)}<br />
              Validation data: {result.validation ? JSON.stringify(result.validation, null, 2) : 'None'}
            </div>
          )}
        </div>
      </div>

      {/* Floating Page Overlay */}
      {showFloatingPage && floatingPageNumber && (
        <div
          className="floating-page-overlay"
          ref={floatingPageRef}
          style={{
            position: 'fixed',
            left: floatingPagePosition.x,
            top: floatingPagePosition.y,
            width: floatingPagePosition.width,
            height: floatingPagePosition.height,
            zIndex: 1000,
            pointerEvents: 'none',
            opacity: 0.97,
            filter: 'drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3))',
          }}
        >
          <Document
            file={`/documents/${selectedPdf}`}
            onLoadError={(error) => console.error('Floating page load error:', error)}
          >
            <Page
              pageNumber={floatingPageNumber}
              width={floatingPagePosition.width}
              scale={1}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </Document>
        </div>
      )}

      {/* Debug Mode Toggle at the bottom */}
      <div style={{ marginTop: 32, textAlign: 'center' }}>
        <button onClick={() => setDebugMode(v => !v)}>
          {debugMode ? 'Disable' : 'Enable'} Debug Mode
        </button>
      </div>
    </div>
  );
}

export default App;
