# PDF Financial Statement Processor - Full Stack Application

A full-stack web application that processes PDF files to extract financial statements and displays them in an interactive web interface.

## Features

- **PDF Upload**: Drag and drop or click to upload PDF files
- **Automatic Processing**: Extracts financial statements using Python backend
- **Interactive Display**: View PDF on the left, extracted tables on the right
- **Tab Navigation**: Switch between different financial statements
- **Page Synchronization**: Clicking tabs automatically navigates to the corresponding PDF page
- **Modern UI**: Clean, responsive design with real-time feedback

## Architecture

- **Frontend**: React with TypeScript
- **Backend**: Spring Boot (Java)
- **PDF Processing**: Python script (existing)
- **File Storage**: Local file system
- **Communication**: REST API with CORS support

## Prerequisites

Before running the application, ensure you have the following installed:

### Backend Requirements
- Java 17 or later
- Maven 3.6+ or Gradle 7+ (either one is fine)
- Python 3.7+ (for PDF processing)
- Python dependencies (from requirements.txt)

### Frontend Requirements
- Node.js 16 or later
- npm 8 or later

## Installation

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd 10k-reader
   ```

2. **Install Python dependencies**:
   ```bash
   # Activate virtual environment
   source .venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Install system dependencies** (Maven, Node.js, etc.):
   ```bash
   ./install-dependencies.sh
   ```

4. **Make startup scripts executable**:
   ```bash
   chmod +x start-app.sh install-dependencies.sh
   ```

## Running the Application

### Quick Start (Recommended)
```bash
./start-app.sh
```

This will automatically:
- Check for required dependencies
- Install frontend dependencies if needed
- Start both backend and frontend
- Show service status and access URLs

### Application Management Commands

```bash
# Start the application
./start-app.sh

# Restart the application (stops and starts again)
./start-app.sh restart

# Stop the application
./start-app.sh stop

# Check service status
./start-app.sh status

# Show help
./start-app.sh help
```

### Manual Start (Alternative)

If you prefer to start services separately:

**Start Backend:**
```bash
./start-backend.sh        # Using Maven
# OR
./start-backend-gradle.sh # Using Gradle
```

**Start Frontend (in a new terminal):**
```bash
./start-frontend.sh
```

## Accessing the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8080
- **Health Check**: http://localhost:8080/api/pdf/health

## Usage

1. **Upload PDF**: 
   - Drag and drop a PDF file onto the upload area, or
   - Click the upload area to select a file

2. **Processing**:
   - The system will automatically process the PDF
   - Progress is shown with a loading indicator
   - Processing time depends on PDF size and complexity

3. **View Results**:
   - PDF viewer shows the document on the left
   - Extracted tables are displayed on the right
   - Tabs allow switching between different financial statements
   - Clicking a tab automatically navigates to the corresponding PDF page

## API Endpoints

### POST /api/pdf/upload
Upload and process a PDF file.

**Request:**
- Content-Type: multipart/form-data
- Body: PDF file

**Response:**
```json
{
  "pdfUrl": "/uploads/1234567890_document.pdf",
  "statements": [
    {
      "name": "CONSOLIDATED STATEMENTS OF INCOME",
      "pageNumber": 25,
      "tableData": [...],
      "headers": ["Description", "2023", "2022", "2021"]
    }
  ],
  "message": "Processing completed successfully",
  "success": true
}
```

### GET /api/pdf/health
Health check endpoint.

**Response:**
```
Backend is running!
```

## Project Structure

```
10k-reader/
├── backend/                          # Spring Boot backend
│   ├── src/main/java/com/pdfreader/
│   │   ├── PdfProcessorApplication.java
│   │   ├── controller/
│   │   │   └── PdfController.java
│   │   ├── service/
│   │   │   └── PdfProcessingService.java
│   │   ├── model/
│   │   │   └── ProcessingResult.java
│   │   └── config/
│   │       └── WebConfig.java
│   ├── src/main/resources/
│   │   └── application.properties
│   ├── pom.xml                       # Maven config
│   └── build.gradle                  # Gradle config
├── frontend/                         # React frontend
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── App.tsx
│   │   ├── index.tsx
│   │   └── index.css
│   ├── package.json
│   └── tsconfig.json
├── pdf_processor.py                  # Python PDF processing script
├── requirements.txt                  # Python dependencies
├── install-dependencies.sh           # System dependency installer
├── start-app.sh                      # Main application manager
├── start-backend.sh                  # Backend startup (Maven)
├── start-backend-gradle.sh           # Backend startup (Gradle)
├── start-frontend.sh                 # Frontend startup
└── README-FULLSTACK.md              # This file
```

## Development

### Backend Development
- The backend is built with Spring Boot 3.2.0
- Uses Apache POI for Excel file processing
- Uses Apache PDFBox for PDF operations
- Integrates with the existing Python script for PDF processing

### Frontend Development
- Built with React 18 and TypeScript
- Uses react-pdf for PDF viewing
- Uses axios for API communication
- Responsive design with CSS

### Adding New Features
1. **Backend**: Add new endpoints in `PdfController.java`
2. **Frontend**: Add new components in `src/` directory
3. **Styling**: Modify `src/index.css` for styling changes

## Troubleshooting

### Common Issues

1. **Port Already in Use**:
   ```bash
   # Check what's using the ports
   ./start-app.sh status
   
   # Stop the application
   ./start-app.sh stop
   
   # Restart
   ./start-app.sh restart
   ```

2. **Python Script Not Found**:
   - Ensure the Python script path is correct in `PdfProcessingService.java`
   - Verify Python dependencies are installed

3. **CORS Issues**:
   - Backend is configured to allow requests from `http://localhost:3000`
   - Check the `@CrossOrigin` annotation in `PdfController.java`

4. **File Upload Size**:
   - Default limit is 50MB
   - Modify `spring.servlet.multipart.max-file-size` in `application.properties`

5. **Dependencies Missing**:
   ```bash
   # Reinstall system dependencies
   ./install-dependencies.sh
   
   # Reinstall frontend dependencies
   cd frontend && rm -rf node_modules && npm install
   ```

### Logs
- Backend logs: `backend.log` (created by start-app.sh)
- Frontend logs: `frontend.log` (created by start-app.sh)
- Browser developer tools show frontend errors and network requests

### Service Status
```bash
./start-app.sh status
```

## Security Considerations

- File uploads are restricted to PDF files
- Uploaded files are stored locally with timestamped names
- No authentication is implemented (add as needed for production)
- CORS is configured for development only

## Production Deployment

For production deployment, consider:

1. **Security**: Add authentication and authorization
2. **File Storage**: Use cloud storage (AWS S3, Google Cloud Storage)
3. **Database**: Add database for storing processing results
4. **Monitoring**: Add logging and monitoring
5. **HTTPS**: Configure SSL/TLS certificates
6. **Environment Variables**: Use environment variables for configuration

## License

This project is part of the 10k-reader application suite. 