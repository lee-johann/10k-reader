# PDF Processing API Architecture

This document explains the new API-based architecture for the PDF processing system, which replaces the previous console output approach with proper HTTP API communication.

## Overview

The system now uses a **three-tier architecture** with proper API communication instead of relying on console output and subprocess calls:

```
Frontend (React) ←→ Backend (Spring Boot) ←→ Python API Server (Flask)
```

## Architecture Components

### 1. **Python API Server** (Port 5001)
- **Purpose**: Handles PDF processing logic and provides HTTP API endpoints
- **Technology**: Flask with CORS support
- **Key Features**:
  - RESTful API endpoints for PDF processing
  - File upload handling
  - JSON response formatting
  - Error handling and validation
  - Health check endpoint

### 2. **Spring Boot Backend** (Port 8080)
- **Purpose**: Acts as a proxy/coordinator between frontend and Python API
- **Technology**: Spring Boot with RestTemplate
- **Key Features**:
  - HTTP client calls to Python API
  - Request/response transformation
  - Error handling and fallback logic
  - CORS configuration for frontend

### 3. **React Frontend** (Port 3000)
- **Purpose**: User interface for PDF processing
- **Technology**: React with TypeScript
- **Key Features**:
  - File upload interface
  - Real-time progress updates
  - Data visualization
  - Error handling and user feedback

## API Endpoints

### Python API Server Endpoints

#### Health Check
```
GET /health
```
Returns server status and version information.

#### Process PDF (File Upload)
```
POST /api/process-pdf
Content-Type: multipart/form-data

Parameters:
- file: PDF file to process
- output_dir: (optional) Output directory for files
```

#### Process PDF (From Path)
```
POST /api/process-pdf-from-path
Content-Type: application/json

Body:
{
  "pdf_path": "path/to/file.pdf",
  "output_dir": "output"
}
```

#### List Documents
```
GET /api/list-documents?dir=../documents
```
Returns list of available PDF files in the specified directory.

#### Download Excel
```
GET /api/download-excel/{filename}?output_dir=output
```
Downloads the generated Excel file.

## Data Flow

### Current Flow (API-Based)
1. **Frontend** sends PDF processing request to **Backend**
2. **Backend** forwards request to **Python API Server**
3. **Python API Server** processes PDF and returns JSON response
4. **Backend** transforms response and sends to **Frontend**
5. **Frontend** displays results to user

### Previous Flow (Console Output)
1. **Frontend** sends request to **Backend**
2. **Backend** calls Python script as subprocess
3. **Python script** outputs JSON to stdout, logs to stderr
4. **Backend** captures stdout and parses JSON
5. **Backend** sends parsed data to **Frontend**

## Benefits of API-Based Approach

### 1. **Better Error Handling**
- **Before**: Errors mixed with data in console output
- **After**: Proper HTTP status codes and error messages

### 2. **Improved Reliability**
- **Before**: Fragile stdout/stderr redirection
- **After**: Standard HTTP request/response protocol

### 3. **Enhanced Debugging**
- **Before**: Difficult to debug subprocess communication
- **After**: Standard HTTP logging and monitoring

### 4. **Scalability**
- **Before**: Tightly coupled subprocess calls
- **After**: Loosely coupled HTTP services

### 5. **Real-time Communication**
- **Before**: No progress updates during processing
- **After**: Can implement WebSocket for real-time updates

## Alternative: WebSocket Server

For real-time communication, we also provide a WebSocket server (`pdf_websocket_server.py`) that offers:

### WebSocket Endpoints
- **Progress Updates**: Real-time processing status
- **Task Management**: Async task handling with IDs
- **Connection Health**: Ping/pong for connection monitoring

### WebSocket Message Types
```json
{
  "type": "process_pdf",
  "pdf_path": "path/to/file.pdf",
  "output_dir": "output",
  "pdf_name": "filename"
}
```

## Setup and Installation

### 1. Install Python Dependencies
```bash
# For Flask API Server
pip install flask flask-cors

# For WebSocket Server (optional)
pip install websockets
```

### 2. Start Services
```bash
# Start all services (recommended)
./start-app.sh

# Or start individually
./start-python-api.sh    # Python API Server
./start-backend.sh       # Spring Boot Backend
./start-frontend.sh      # React Frontend
```

### 3. Verify Services
```bash
# Check service status
./start-app.sh status

# Health checks
curl http://localhost:5001/health          # Python API
curl http://localhost:8080/api/pdf/health  # Backend
```

## Configuration

### Environment Variables
```bash
# Python API Server
export FLASK_DEBUG=True
export PORT=5001

# WebSocket Server (optional)
export WS_PORT=5002
```

### Service URLs
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8080
- **Python API**: http://localhost:5001
- **WebSocket**: ws://localhost:5002

## Migration from Console Output

### What Changed
1. **Python Script**: Now runs as HTTP server instead of CLI tool
2. **Backend**: Uses RestTemplate instead of ProcessBuilder
3. **Data Flow**: HTTP requests instead of stdout/stderr

### Backward Compatibility
- Original `pdf_processor.py` still works as CLI tool
- Console output functionality preserved for debugging
- Gradual migration possible

## Troubleshooting

### Common Issues

#### 1. Python API Server Not Starting
```bash
# Check if port 5001 is available
lsof -i :5001

# Check Python dependencies
pip list | grep flask
```

#### 2. Backend Can't Connect to Python API
```bash
# Verify Python API is running
curl http://localhost:5001/health

# Check network connectivity
telnet localhost 5001
```

#### 3. CORS Issues
- Ensure Flask-CORS is installed
- Check CORS configuration in Python API
- Verify frontend URL in backend CORS settings

### Logs
- **Python API**: `python-api.log`
- **Backend**: `backend.log`
- **Frontend**: `frontend.log`

## Performance Considerations

### API vs Console Output
- **API**: Slightly higher overhead due to HTTP protocol
- **Console**: Lower overhead but less reliable
- **Recommendation**: API approach for production, console for development

### Optimization Tips
1. Use connection pooling in RestTemplate
2. Implement request caching where appropriate
3. Consider async processing for large files
4. Monitor memory usage during PDF processing

## Future Enhancements

### Planned Features
1. **Streaming Responses**: For large PDF files
2. **Batch Processing**: Multiple PDFs in one request
3. **Authentication**: API key or JWT tokens
4. **Rate Limiting**: Prevent abuse
5. **Metrics**: Processing time, success rates
6. **Caching**: Store processed results

### WebSocket Enhancements
1. **Real-time Progress**: Processing status updates
2. **Live Validation**: Real-time data validation
3. **Collaborative Features**: Multiple users viewing same PDF
4. **Notifications**: Processing completion alerts

## Conclusion

The API-based architecture provides a more robust, scalable, and maintainable solution compared to the console output approach. It enables better error handling, real-time communication, and easier debugging while maintaining all existing functionality. 