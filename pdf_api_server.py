#!/usr/bin/env python3
"""
PDF Processing API Server
Provides HTTP endpoints for PDF processing instead of console output.
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import sys
import json
import tempfile
from pathlib import Path
import traceback
from werkzeug.utils import secure_filename

# Import the existing PDF processing functions
from pdf_processor import extract_all_statements_to_json, find_page_with_text, extract_page, extract_table_from_page

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'PDF Processing API',
        'version': '1.0.0'
    })

@app.route('/api/process-pdf', methods=['POST'])
def process_pdf():
    """
    Process a PDF file and return extracted data as JSON.
    
    Expected form data:
    - file: PDF file to process
    - output_dir: (optional) Output directory for files
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only PDF files are allowed.'
            }), 400
        
        # Get output directory from request or use default
        output_dir = request.form.get('output_dir', 'output')
        os.makedirs(output_dir, exist_ok=True)
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        pdf_name = filename.replace('.pdf', '')
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
        
        try:
            # Process the PDF using existing function
            result_json = extract_all_statements_to_json(temp_path, output_dir, pdf_name)
            
            if result_json:
                # Parse the JSON to add additional metadata
                result_data = json.loads(result_json)
                result_data['success'] = True
                result_data['message'] = 'PDF processed successfully'
                result_data['pdfUrl'] = f'/uploads/{filename}'
                
                return jsonify(result_data)
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to extract data from PDF'
                }), 500
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        app.logger.error(f"Error processing PDF: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/process-pdf-from-path', methods=['POST'])
def process_pdf_from_path():
    """
    Process a PDF file from a given path (for existing files in documents folder).
    
    Expected JSON data:
    {
        "pdf_path": "path/to/file.pdf",
        "output_dir": "output"
    }
    """
    try:
        data = request.get_json()
        if not data or 'pdf_path' not in data:
            return jsonify({
                'success': False,
                'error': 'PDF path not provided'
            }), 400
        
        pdf_path = data['pdf_path']
        output_dir = data.get('output_dir', 'output')
        
        # Handle relative paths by resolving them relative to the project root
        if pdf_path.startswith('../'):
            # Remove the '../' and use the path relative to project root
            pdf_path = pdf_path[3:]
        elif pdf_path.startswith('./'):
            # Remove the './' and use the path relative to project root
            pdf_path = pdf_path[2:]
        
        # Validate file exists
        if not os.path.exists(pdf_path):
            return jsonify({
                'success': False,
                'error': f'PDF file not found: {pdf_path}'
            }), 404
        
        # Validate it's a PDF file
        if not pdf_path.lower().endswith('.pdf'):
            return jsonify({
                'success': False,
                'error': 'File is not a PDF'
            }), 400
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract PDF name from path
        pdf_name = os.path.basename(pdf_path).replace('.pdf', '')
        
        # Process the PDF
        result_json = extract_all_statements_to_json(pdf_path, output_dir, pdf_name)
        
        if result_json:
            result_data = json.loads(result_json)
            result_data['success'] = True
            result_data['message'] = 'PDF processed successfully'
            result_data['pdfUrl'] = f'/uploads/{os.path.basename(pdf_path)}'
            
            return jsonify(result_data)
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to extract data from PDF'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error processing PDF from path: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/list-documents', methods=['GET'])
def list_documents():
    """List available PDF documents in the documents directory."""
    try:
        documents_dir = request.args.get('dir', 'documents')
        pdf_files = []
        
        if os.path.exists(documents_dir) and os.path.isdir(documents_dir):
            for filename in os.listdir(documents_dir):
                if filename.lower().endswith('.pdf'):
                    pdf_files.append(filename)
        
        return jsonify({
            'success': True,
            'documents': pdf_files
        })
        
    except Exception as e:
        app.logger.error(f"Error listing documents: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error listing documents: {str(e)}'
        }), 500

@app.route('/api/download-excel/<filename>', methods=['GET'])
def download_excel(filename):
    """Download the generated Excel file."""
    try:
        output_dir = request.args.get('output_dir', 'output')
        excel_path = os.path.join(output_dir, filename)
        
        if not os.path.exists(excel_path):
            return jsonify({
                'success': False,
                'error': 'Excel file not found'
            }), 404
        
        return send_file(excel_path, as_attachment=True)
        
    except Exception as e:
        app.logger.error(f"Error downloading Excel file: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error downloading file: {str(e)}'
        }), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded PDF files."""
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"Starting PDF Processing API Server on port {port}")
    print(f"Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug) 