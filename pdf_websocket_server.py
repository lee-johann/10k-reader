#!/usr/bin/env python3
"""
PDF Processing WebSocket Server
Provides real-time communication for PDF processing with progress updates.
"""

import asyncio
import websockets
import json
import os
import sys
import traceback
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import uuid

# Import the existing PDF processing functions
from pdf_processor import extract_all_statements_to_json, find_page_with_text, extract_page, extract_table_from_page

# Global storage for active connections and processing tasks
active_connections = set()
processing_tasks = {}

class ProcessingProgress:
    def __init__(self, task_id):
        self.task_id = task_id
        self.status = "starting"
        self.progress = 0
        self.message = ""
        self.result = None
        self.error = None

    def update(self, status, progress, message):
        self.status = status
        self.progress = progress
        self.message = message
        return self.to_dict()

    def complete(self, result):
        self.status = "completed"
        self.progress = 100
        self.result = result
        return self.to_dict()

    def error(self, error_message):
        self.status = "error"
        self.error = error_message
        return self.to_dict()

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "result": self.result,
            "error": self.error
        }

def process_pdf_with_progress(pdf_path, output_dir, pdf_name, task_id):
    """Process PDF with progress updates sent via WebSocket"""
    progress = ProcessingProgress(task_id)
    
    try:
        # Step 1: Starting
        progress.update("starting", 0, "Initializing PDF processing...")
        broadcast_progress(progress.to_dict())
        
        # Step 2: Validating file
        progress.update("validating", 10, "Validating PDF file...")
        broadcast_progress(progress.to_dict())
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Step 3: Processing
        progress.update("processing", 30, "Extracting financial statements...")
        broadcast_progress(progress.to_dict())
        
        # Process the PDF using existing function
        result_json = extract_all_statements_to_json(pdf_path, output_dir, pdf_name)
        
        if not result_json:
            raise Exception("Failed to extract data from PDF")
        
        # Step 4: Parsing results
        progress.update("parsing", 80, "Parsing extracted data...")
        broadcast_progress(progress.to_dict())
        
        # Parse the JSON result
        result_data = json.loads(result_json)
        result_data['success'] = True
        result_data['message'] = 'PDF processed successfully'
        result_data['pdfUrl'] = f'/uploads/{os.path.basename(pdf_path)}'
        
        # Step 5: Completed
        progress.complete(result_data)
        broadcast_progress(progress.to_dict())
        
        return result_data
        
    except Exception as e:
        error_msg = f"Error processing PDF: {str(e)}"
        progress.error(error_msg)
        broadcast_progress(progress.to_dict())
        raise

def broadcast_progress(progress_data):
    """Broadcast progress update to all connected clients"""
    message = json.dumps({
        "type": "progress",
        "data": progress_data
    })
    
    # Send to all active connections
    for websocket in active_connections.copy():
        try:
            asyncio.create_task(websocket.send(message))
        except Exception as e:
            print(f"Error sending progress update: {e}")
            active_connections.discard(websocket)

async def handle_websocket(websocket, path):
    """Handle WebSocket connections"""
    connection_id = str(uuid.uuid4())
    active_connections.add(websocket)
    
    print(f"Client connected: {connection_id}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "process_pdf":
                    # Handle PDF processing request
                    await handle_process_pdf_request(websocket, data, connection_id)
                    
                elif message_type == "list_documents":
                    # Handle document listing request
                    await handle_list_documents_request(websocket, data)
                    
                elif message_type == "ping":
                    # Handle ping/pong for connection health
                    await websocket.send(json.dumps({"type": "pong"}))
                    
                else:
                    # Unknown message type
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": f"Server error: {str(e)}"
                }))
                
    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {connection_id}")
    except Exception as e:
        print(f"Error handling WebSocket connection: {e}")
    finally:
        active_connections.discard(websocket)

async def handle_process_pdf_request(websocket, data, connection_id):
    """Handle PDF processing request via WebSocket"""
    try:
        pdf_path = data.get("pdf_path")
        output_dir = data.get("output_dir", "output")
        pdf_name = data.get("pdf_name")
        
        if not pdf_path:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "PDF path not provided"
            }))
            return
        
        # Validate file exists
        if not os.path.exists(pdf_path):
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"PDF file not found: {pdf_path}"
            }))
            return
        
        # Create task ID
        task_id = str(uuid.uuid4())
        
        # Send task started confirmation
        await websocket.send(json.dumps({
            "type": "task_started",
            "task_id": task_id
        }))
        
        # Process PDF in background thread
        with ThreadPoolExecutor() as executor:
            future = executor.submit(process_pdf_with_progress, pdf_path, output_dir, pdf_name, task_id)
            
            try:
                result = future.result(timeout=300)  # 5 minute timeout
                await websocket.send(json.dumps({
                    "type": "task_completed",
                    "task_id": task_id,
                    "result": result
                }))
            except Exception as e:
                await websocket.send(json.dumps({
                    "type": "task_error",
                    "task_id": task_id,
                    "error": str(e)
                }))
                
    except Exception as e:
        await websocket.send(json.dumps({
            "type": "error",
            "message": f"Error handling PDF processing request: {str(e)}"
        }))

async def handle_list_documents_request(websocket, data):
    """Handle document listing request via WebSocket"""
    try:
        documents_dir = data.get("dir", "../documents")
        pdf_files = []
        
        if os.path.exists(documents_dir) and os.path.isdir(documents_dir):
            for filename in os.listdir(documents_dir):
                if filename.lower().endswith('.pdf'):
                    pdf_files.append(filename)
        
        await websocket.send(json.dumps({
            "type": "documents_list",
            "documents": pdf_files,
            "success": True
        }))
        
    except Exception as e:
        await websocket.send(json.dumps({
            "type": "error",
            "message": f"Error listing documents: {str(e)}"
        }))

async def main():
    """Main WebSocket server function"""
    port = int(os.environ.get('WS_PORT', 5002))
    
    print(f"Starting PDF Processing WebSocket Server on port {port}")
    print(f"WebSocket URL: ws://localhost:{port}")
    
    # Start WebSocket server
    async with websockets.serve(handle_websocket, "localhost", port):
        print(f"WebSocket server is running on ws://localhost:{port}")
        await asyncio.Future()  # Run forever

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down WebSocket server...")
    except Exception as e:
        print(f"Error starting WebSocket server: {e}")
        traceback.print_exc() 