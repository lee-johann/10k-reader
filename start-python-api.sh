#!/bin/bash

# Start Python PDF Processing API Server
echo "Starting Python PDF Processing API Server..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install required packages
echo "Installing required packages..."
pip install flask flask-cors

# Set environment variables
export FLASK_DEBUG=True
export PORT=5001

# Start the API server
echo "Starting API server on port 5001..."
python3 pdf_api_server.py 