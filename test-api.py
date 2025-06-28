#!/usr/bin/env python3
"""
Test script for the new API-based PDF processing architecture.
"""

import requests
import json
import time
import sys
from pathlib import Path

# Configuration
PYTHON_API_URL = "http://localhost:5001"
BACKEND_API_URL = "http://localhost:8080"

def test_python_api_health():
    """Test Python API health endpoint"""
    print("🔍 Testing Python API health...")
    try:
        response = requests.get(f"{PYTHON_API_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Python API is healthy: {data}")
            return True
        else:
            print(f"❌ Python API health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Python API health check error: {e}")
        return False

def test_backend_health():
    """Test Backend health endpoint"""
    print("🔍 Testing Backend health...")
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/pdf/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Backend is healthy: {response.text}")
            return True
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend health check error: {e}")
        return False

def test_list_documents():
    """Test document listing endpoint"""
    print("🔍 Testing document listing...")
    try:
        response = requests.get(f"{PYTHON_API_URL}/api/list-documents", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                documents = data.get("documents", [])
                print(f"✅ Found {len(documents)} documents: {documents}")
                return documents
            else:
                print(f"❌ Document listing failed: {data.get('error')}")
                return []
        else:
            print(f"❌ Document listing failed: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Document listing error: {e}")
        return []

def test_process_pdf_from_path(pdf_path):
    """Test PDF processing from path"""
    print(f"🔍 Testing PDF processing: {pdf_path}")
    try:
        payload = {
            "pdf_path": str(pdf_path),
            "output_dir": "test_output"
        }
        
        response = requests.post(
            f"{PYTHON_API_URL}/api/process-pdf-from-path",
            json=payload,
            timeout=60  # Longer timeout for processing
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                statements = data.get("statements", [])
                validation = data.get("validation")
                print(f"✅ PDF processed successfully!")
                print(f"   - Statements extracted: {len(statements)}")
                if validation:
                    summary = validation.get("summary", {})
                    print(f"   - Validation: {summary.get('passed_checks')}/{summary.get('total_checks')} checks passed")
                return True
            else:
                print(f"❌ PDF processing failed: {data.get('error')}")
                return False
        else:
            print(f"❌ PDF processing failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ PDF processing error: {e}")
        return False

def test_backend_process_pdf(filename):
    """Test backend PDF processing endpoint"""
    print(f"🔍 Testing Backend PDF processing: {filename}")
    try:
        form_data = {"filename": filename}
        response = requests.post(
            f"{BACKEND_API_URL}/api/pdf/process-document",
            data=form_data,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                statements = data.get("statements", [])
                print(f"✅ Backend PDF processing successful!")
                print(f"   - Statements extracted: {len(statements)}")
                return True
            else:
                print(f"❌ Backend PDF processing failed: {data.get('message')}")
                return False
        else:
            print(f"❌ Backend PDF processing failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend PDF processing error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Testing API-based PDF Processing Architecture")
    print("=" * 50)
    
    # Test 1: Health checks
    print("\n📋 Test 1: Health Checks")
    print("-" * 30)
    
    python_healthy = test_python_api_health()
    backend_healthy = test_backend_health()
    
    if not python_healthy or not backend_healthy:
        print("❌ Health checks failed. Please ensure both services are running.")
        print("   Run: ./start-app.sh")
        sys.exit(1)
    
    # Test 2: Document listing
    print("\n📋 Test 2: Document Listing")
    print("-" * 30)
    
    documents = test_list_documents()
    if not documents:
        print("⚠️  No documents found. Please add PDF files to the documents directory.")
        return
    
    # Test 3: PDF processing (Python API)
    print("\n📋 Test 3: Python API PDF Processing")
    print("-" * 30)
    
    # Use the first available document
    test_document = documents[0]
    pdf_path = Path("documents") / test_document
    
    if not pdf_path.exists():
        print(f"❌ Test document not found: {pdf_path}")
        return
    
    python_success = test_process_pdf_from_path(pdf_path)
    
    # Test 4: Backend PDF processing
    print("\n📋 Test 4: Backend PDF Processing")
    print("-" * 30)
    
    backend_success = test_backend_process_pdf(test_document)
    
    # Summary
    print("\n📋 Test Summary")
    print("-" * 30)
    print(f"Python API Health: {'✅' if python_healthy else '❌'}")
    print(f"Backend Health: {'✅' if backend_healthy else '❌'}")
    print(f"Document Listing: {'✅' if documents else '❌'}")
    print(f"Python API Processing: {'✅' if python_success else '❌'}")
    print(f"Backend Processing: {'✅' if backend_success else '❌'}")
    
    if python_healthy and backend_healthy and python_success and backend_success:
        print("\n🎉 All tests passed! API-based architecture is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the logs and ensure all services are running properly.")

if __name__ == "__main__":
    main() 