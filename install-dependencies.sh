#!/bin/bash

echo "Installing dependencies for PDF Processor Full-Stack Application..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "Homebrew is already installed"
fi

# Install Maven
echo "Installing Maven..."
brew install maven

# Install Node.js
echo "Installing Node.js..."
brew install node

# Verify installations
echo ""
echo "Verifying installations..."

if command -v mvn &> /dev/null; then
    echo "✅ Maven installed successfully"
    mvn -version
else
    echo "❌ Maven installation failed"
fi

if command -v node &> /dev/null; then
    echo "✅ Node.js installed successfully"
    node -v
    npm -v
else
    echo "❌ Node.js installation failed"
fi

echo ""
echo "Installation complete! You can now run the application with:"
echo "./start-app.sh" 