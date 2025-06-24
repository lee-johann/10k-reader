#!/bin/bash

echo "Starting Spring Boot Backend (Gradle)..."

# Check if Java is installed
if ! command -v java &> /dev/null; then
    echo "Error: Java is not installed. Please install Java 17 or later."
    exit 1
fi

# Check if Gradle is installed
if ! command -v gradle &> /dev/null; then
    echo "Installing Gradle..."
    # Install Gradle using Homebrew if available
    if command -v brew &> /dev/null; then
        brew install gradle
    else
        echo "Error: Gradle is not installed and Homebrew is not available."
        echo "Please install Gradle manually or run: brew install gradle"
        exit 1
    fi
fi

# Navigate to backend directory
cd backend

# Build the project
echo "Building the project..."
gradle build

# Start the application
echo "Starting the application on http://localhost:8080"
gradle bootRun 