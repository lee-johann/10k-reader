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
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState<number | null>(null);
  const pdfViewerRef = useRef<HTMLDivElement>(null);

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

  const loadAvailablePdfs = async () => {
    try {
      const response = await axios.get<string[]>('/api/pdf/documents');
      setAvailablePdfs(response.data);
    } catch (err) {
      console.error('Failed to load PDFs:', err);
      setError('Failed to load available PDFs');
    }
  };

  const handlePdfSelect = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedPdf(event.target.value);
    setError(null);
    setResult(null);
  };

  const handleProcess = async () => {
    if (!selectedPdf) return;

    setIsProcessing(true);
    setError(null);
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
        setError(response.data.message || 'Processing failed');
      }
    } catch (err) {
      setError('Failed to process PDF');
      console.error('Processing error:', err);
    } finally {
      setIsProcessing(false);
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
              disabled={isProcessing}
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
                disabled={isProcessing}
              >
                {isProcessing ? 'Processing...' : 'Process PDF'}
              </button>
            )}
          </div>

          {error && <div className="error">{error}</div>}
          {isProcessing && <div className="loading">Processing PDF... This may take a few moments.</div>}
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
                    renderTextLayer={false}
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
                                      <td key={colIndex}>{row[header] || ''}</td>
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
  );
}

export default App; 