#!/bin/bash

# PDF Processor Setup Script

echo "🚀 Setting up PDF Processor CLI Tool"
echo "======================================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7+ first."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Create virtual environment if it doesn't exist
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "🛠️  Creating virtual environment in $VENV_DIR ..."
    python3 -m venv $VENV_DIR
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment."
        exit 1
    fi
fi

echo "✅ Virtual environment ready"

# Activate virtual environment
source $VENV_DIR/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing Python dependencies in virtual environment..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Python dependencies installed successfully in virtual environment"
else
    echo "❌ Failed to install Python dependencies"
    exit 1
fi

# Check OS and install system dependencies
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "🍎 Detected macOS"
    
    if command -v brew &> /dev/null; then
        echo "📦 Installing system dependencies via Homebrew..."
        brew install ghostscript tcl-tk
    else
        echo "⚠️  Homebrew not found. Please install system dependencies manually:"
        echo "   brew install ghostscript tcl-tk"
    fi
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 Detected Linux"
    
    if command -v apt-get &> /dev/null; then
        echo "📦 Installing system dependencies via apt-get..."
        sudo apt-get update
        sudo apt-get install -y ghostscript python3-tk
    elif command -v yum &> /dev/null; then
        echo "📦 Installing system dependencies via yum..."
        sudo yum install -y ghostscript tkinter
    else
        echo "⚠️  Package manager not found. Please install system dependencies manually:"
        echo "   Ubuntu/Debian: sudo apt-get install ghostscript python3-tk"
        echo "   CentOS/RHEL: sudo yum install ghostscript tkinter"
    fi
else
    echo "⚠️  Unknown OS. Please install system dependencies manually."
fi

# Make scripts executable
chmod +x pdf_processor.py
chmod +x example.py
chmod +x test_installation.py
chmod +x demo.py

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Test installation: python test_installation.py"
echo "3. Run the tool: python pdf_processor.py your_document.pdf"
echo "4. See help: python pdf_processor.py --help"
echo ""
echo "For more information, see README.md" 