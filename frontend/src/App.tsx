import React, { useState, useRef } from 'react';
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
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setError(null);
    } else {
      setError('Please select a valid PDF file');
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    event.preventDefault();
    event.currentTarget.classList.add('dragover');
  };

  const handleDragLeave = (event: React.DragEvent) => {
    event.preventDefault();
    event.currentTarget.classList.remove('dragover');
  };

  const handleDrop = (event: React.DragEvent) => {
    event.preventDefault();
    event.currentTarget.classList.remove('dragover');

    const droppedFile = event.dataTransfer.files[0];
    if (droppedFile && droppedFile.type === 'application/pdf') {
      setFile(droppedFile);
      setError(null);
    } else {
      setError('Please drop a valid PDF file');
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post<ProcessingResult>('/api/pdf/upload', formData, {
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
      setError('Failed to upload and process PDF');
      console.error('Upload error:', err);
    } finally {
      setIsUploading(false);
    }
  };

  const handleTabClick = (index: number) => {
    setActiveTab(index);
    if (result && result.statements[index]) {
      setCurrentPage(result.statements[index].pageNumber);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="app">
      <div className="container">
        <div className="upload-section">
          <h1>PDF Financial Statement Processor</h1>
          <p>Upload a PDF to extract financial statements and view them as tables</p>

          <div
            className="upload-area"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={triggerFileInput}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileSelect}
              style={{ display: 'none' }}
            />
            {file ? (
              <div>
                <p>Selected file: {file.name}</p>
                <button
                  className="upload-button"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleUpload();
                  }}
                  disabled={isUploading}
                >
                  {isUploading ? 'Processing...' : 'Process PDF'}
                </button>
              </div>
            ) : (
              <div>
                <p>Click to select a PDF file or drag and drop here</p>
                <p>Supported format: PDF</p>
              </div>
            )}
          </div>

          {error && <div className="error">{error}</div>}
          {isUploading && <div className="loading">Processing PDF... This may take a few moments.</div>}
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