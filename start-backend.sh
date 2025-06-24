#!/bin/bash

echo "Starting Spring Boot Backend..."

# Check if Java is installed
if ! command -v java &> /dev/null; then
    echo "Error: Java is not installed. Please install Java 17 or later."
    exit 1
fi

# Check if Maven is installed
if ! command -v mvn &> /dev/null; then
    echo "Error: Maven is not installed. Please install Maven."
    exit 1
fi

# Navigate to backend directory
cd backend

# Clean and build the project
echo "Building the project..."
mvn clean install

# Start the application
echo "Starting the application on http://localhost:8080"
mvn spring-boot:run 