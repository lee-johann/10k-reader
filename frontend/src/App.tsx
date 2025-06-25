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

interface ProcessingResult {
  pdfUrl?: string;
  statements: StatementData[];
  message: string;
  success: boolean;
}

function App() {
  const [availablePdfs, setAvailablePdfs] = useState<string[]>([]);
  const [selectedPdf, setSelectedPdf] = useState<string>('');
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<string>('');
  const [hoveredValue, setHoveredValue] = useState<string>('');
  const [hoveredPage, setHoveredPage] = useState<number | null>(null);
  const [showFloatingPage, setShowFloatingPage] = useState(false);
  const [floatingPageNumber, setFloatingPageNumber] = useState<number | null>(null);
  const [floatingPagePosition, setFloatingPagePosition] = useState({ x: 0, y: 0 });
  const pdfViewerRef = useRef<HTMLDivElement>(null);
  const floatingPageRef = useRef<HTMLDivElement>(null);
  const [debugMode, setDebugMode] = useState(false);
  const [markedCells, setMarkedCells] = useState<Set<string>>(new Set());

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
      console.log('Hovering over:', hoveredValue, 'on page:', hoveredPage);

      // Show floating page overlay instead of highlighting in scrollable PDF
      showFloatingPageOverlay(hoveredValue, hoveredPage);
    } else if (!hoveredValue) {
      // Hide floating page when not hovering
      hideFloatingPageOverlay();
    }
  }, [hoveredValue, hoveredPage]);

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

  // Show floating page overlay
  const showFloatingPageOverlay = async (value: string, pageNumber: number) => {
    try {
      console.log('Showing floating page overlay for:', value, 'on page:', pageNumber);

      // Get the PDF viewer's position in the viewport
      const viewerRect = pdfViewerRef.current?.getBoundingClientRect();
      if (!viewerRect) {
        console.log('Viewer rect not found');
        return;
      }

      // Calculate the position for the floating overlay
      // Place it above the PDF viewer, centered horizontally
      const overlayWidth = viewerRect.width;
      const overlayHeight = viewerRect.height / (numPages || 1); // Estimate height as one page tall
      const x = viewerRect.left;
      const y = Math.max(viewerRect.top - overlayHeight - 16, 0); // 16px gap above

      setFloatingPagePosition({ x, y });
      setFloatingPageNumber(pageNumber);
      setShowFloatingPage(true);

      // Wait for the floating page to render, then highlight
      setTimeout(() => {
        highlightInFloatingPage(value, pageNumber);
      }, 100);

    } catch (error) {
      console.error('Error showing floating page overlay:', error);
    }
  };

  // Hide floating page overlay
  const hideFloatingPageOverlay = () => {
    setShowFloatingPage(false);
    setFloatingPageNumber(null);
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

  // Highlight in the floating page
  const highlightInFloatingPage = async (value: string, pageNumber: number) => {
    try {
      if (!floatingPageRef.current) {
        console.log('Floating page ref not found');
        return;
      }
      removeHighlights(floatingPageRef.current);
      const textItems = await extractTextWithCoordinates(`/documents/${selectedPdf}`, pageNumber);
      const normalizedValue = normalizeNumber(value);
      // Debug: Log all text items
      console.log('All text items on page:', textItems.map(t => `${t.text} @ (${t.x}, ${t.y})`));
      const matchingItems = textItems.filter(item => {
        const normalizedText = normalizeNumber(item.text);
        return shouldHighlight(normalizedValue, normalizedText, value, item.text);
      });
      matchingItems.forEach((item, index) => {
        console.log(`Matched: "${item.text}" at (${item.x}, ${item.y})`);
      });
      const canvasElement = floatingPageRef.current.querySelector('canvas');
      if (!canvasElement) {
        console.log('Canvas element not found in floating page');
        return;
      }
      const canvasContainer = canvasElement.closest('.react-pdf__Page__canvas-container') || canvasElement.parentElement;
      if (!canvasContainer) {
        console.log('Canvas container not found in floating page');
        return;
      }
      const canvasWidth = canvasElement.width;
      const canvasHeight = canvasElement.height;
      const displayWidth = canvasElement.offsetWidth;
      const displayHeight = canvasElement.offsetHeight;
      // Get PDF page viewBox
      const { width: pdfWidth, height: pdfHeight } = await getPdfPageViewBox(`/documents/${selectedPdf}`, pageNumber);
      console.log(`Canvas: ${canvasWidth}x${canvasHeight}, Display: ${displayWidth}x${displayHeight}, PDF viewBox: ${pdfWidth}x${pdfHeight}`);
      // Use PDF viewBox for scaling
      const scaleX = displayWidth / pdfWidth;
      const scaleY = displayHeight / pdfHeight;
      console.log(`scaleX: ${scaleX}, scaleY: ${scaleY}`);
      // Debug mode: Draw boxes around all numbers
      if (debugMode) {
        textItems.forEach((item, index) => {
          if (/[-+]?\d[\d,\.]*$/.test(item.text)) {
            const [a, b, c, d, e, f] = item.transform;
            const x = e;
            const y = f;
            const width = a * item.width; // a is scale in X
            const height = Math.abs(d);   // d is scale in Y (may be negative)
            // Map PDF coordinates to display coordinates
            const displayX = x * scaleX;
            // Flip Y and account for text height
            const displayY = displayHeight - ((y + height) * scaleY);
            console.log(`DEBUG BOX: "${item.text}" PDF: (${x}, ${y}, ${width}, ${height}) -> Display: (${displayX}, ${displayY})`);
            const box = document.createElement('div');
            box.className = 'debug-number-box';
            box.style.position = 'absolute';
            box.style.left = `${displayX - 2}px`;
            box.style.top = `${displayY - 2}px`;
            box.style.width = `${width * scaleX + 4}px`;
            box.style.height = `${height * scaleY + 4}px`;
            box.style.border = '2px dashed #00f';
            box.style.backgroundColor = 'rgba(0,0,255,0.05)';
            box.style.pointerEvents = 'none';
            box.title = `Extracted: ${item.text}`;
            canvasContainer.appendChild(box);
          }
        });
      }
      // Create yellow highlight overlays for each matching item
      matchingItems.forEach((item, index) => {
        const [a, b, c, d, e, f] = item.transform;
        const x = e;
        const y = f;
        const width = a * item.width;
        const height = Math.abs(d);
        const displayX = x * scaleX;
        const displayY = displayHeight - ((y + height) * scaleY);
        console.log(`YELLOW BOX: "${item.text}" PDF: (${x}, ${y}, ${width}, ${height}) -> Display: (${displayX}, ${displayY})`);
        const highlight = document.createElement('div');
        highlight.className = 'yellow-highlight-overlay';
        highlight.style.position = 'absolute';
        highlight.style.left = `${displayX - 2}px`;
        highlight.style.top = `${displayY - 2}px`;
        highlight.style.width = `${width * scaleX + 4}px`;
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
        setResult(response.data);
        if (response.data.statements.length > 0) {
          setCurrentPage(response.data.statements[0].pageNumber);
        }
      } else {
        console.error('Processing failed:', response.data.message);
      }
    } catch (err) {
      console.error('Failed to process PDF:', err);
    } finally {
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
    setHoveredValue(value);
    setHoveredPage(pageNumber);

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

  // Handler for right-click (context menu) on a cell
  const handleCellRightClick = (e: React.MouseEvent, statementName: string, rowIdx: number, colIdx: number) => {
    e.preventDefault();
    const key = getCellKey(statementName, rowIdx, colIdx);
    setMarkedCells(prev => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
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
              {/* Debug Mode Toggle */}
              {/* <button onClick={() => setDebugMode(v => !v)} style={{marginBottom: 8}}>
                {debugMode ? 'Disable' : 'Enable'} Debug Mode
              </button> */}

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
                                          className={markedCells.has(getCellKey(activeStatement.name, rowIndex, colIndex)) ? 'green-marked-cell' : ''}
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
            left: `${floatingPagePosition.x}px`,
            top: `${floatingPagePosition.y}px`,
            width: pdfViewerRef.current?.offsetWidth || 'auto',
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
              width={undefined}
              scale={1}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </Document>
        </div>
      )}
    </div>
  );
}

export default App; 