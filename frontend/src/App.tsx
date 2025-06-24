import React, { useState, useEffect } from 'react';
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
  pdfUrl: string;
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
  const [activeTab, setActiveTab] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);

  // Load available PDFs on component mount
  useEffect(() => {
    loadAvailablePdfs();
  }, []);

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

  const handleTabClick = (index: number) => {
    setActiveTab(index);
    if (result && result.statements[index]) {
      setCurrentPage(result.statements[index].pageNumber);
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
            <div className="pdf-viewer">
              <h3>PDF Viewer (Page {currentPage})</h3>
              <Document file={`http://localhost:8080${result.pdfUrl}`}>
                <Page pageNumber={currentPage} width={400} />
              </Document>
            </div>

            <div className="table-viewer">
              <div className="tabs">
                {result.statements.map((statement, index) => (
                  <button
                    key={index}
                    className={`tab ${activeTab === index ? 'active' : ''}`}
                    onClick={() => handleTabClick(index)}
                  >
                    {statement.name} (Page {statement.pageNumber})
                  </button>
                ))}
              </div>

              <div className="table-container">
                {result.statements[activeTab] && (
                  <table className="table">
                    <thead>
                      <tr>
                        {result.statements[activeTab].headers.map((header, index) => (
                          <th key={index}>{header}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.statements[activeTab].tableData.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {result.statements[activeTab].headers.map((header, colIndex) => (
                            <td key={colIndex}>{row[header] || ''}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
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