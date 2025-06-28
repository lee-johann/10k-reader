#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill processes on specific ports
kill_port_processes() {
    local port=$1
    local process_name=$2
    
    if check_port $port; then
        print_warning "Port $port is in use. Stopping existing $process_name..."
        lsof -ti:$port | xargs kill -9 2>/dev/null
        sleep 2
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local port=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Waiting for $service_name to be ready on port $port..."
    
    while [ $attempt -le $max_attempts ]; do
        if check_port $port; then
            print_success "$service_name is ready on port $port!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start on port $port after $max_attempts attempts"
    return 1
}

# Function to start Python API server
start_python_api() {
    print_status "Starting Python PDF Processing API Server..."
    
    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3."
        return 1
    fi
    
    # Check if virtual environment exists, create if not
    if [ ! -d ".venv" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv .venv
        if [ $? -ne 0 ]; then
            print_error "Failed to create virtual environment"
            return 1
        fi
    fi
    
    # Activate virtual environment and install dependencies
    source .venv/bin/activate
    
    # Install required packages
    print_status "Installing Python dependencies..."
    pip install flask flask-cors > python-api.log 2>&1
    if [ $? -ne 0 ]; then
        print_error "Failed to install Python dependencies"
        return 1
    fi
    
    # Set environment variables
    export FLASK_DEBUG=True
    export PORT=5001
    
    # Start the API server
    python3 pdf_api_server.py > python-api.log 2>&1 &
    PYTHON_API_PID=$!
    
    # Wait for Python API to be ready
    if wait_for_service 5001 "Python API"; then
        print_success "Python API started successfully (PID: $PYTHON_API_PID)"
        return 0
    else
        print_error "Python API failed to start"
        return 1
    fi
}

# Function to start backend
start_backend() {
    print_status "Starting Spring Boot Backend..."
    
    # Check if Java is installed
    if ! command -v java &> /dev/null; then
        print_error "Java is not installed. Please install Java 17 or later."
        return 1
    fi
    
    # Try Maven first, then Gradle
    if command -v mvn &> /dev/null; then
        print_status "Using Maven to build and start backend..."
        cd backend
        mvn clean install -q
        if [ $? -eq 0 ]; then
            mvn spring-boot:run > ../backend.log 2>&1 &
            BACKEND_PID=$!
            cd ..
        else
            print_error "Maven build failed"
            return 1
        fi
    elif command -v gradle &> /dev/null; then
        print_status "Using Gradle to build and start backend..."
        cd backend
        gradle build -q
        if [ $? -eq 0 ]; then
            gradle bootRun > ../backend.log 2>&1 &
            BACKEND_PID=$!
            cd ..
        else
            print_error "Gradle build failed"
            return 1
        fi
    else
        print_error "Neither Maven nor Gradle is installed. Please install one of them."
        return 1
    fi
    
    # Wait for backend to be ready
    if wait_for_service 8080 "Backend"; then
        print_success "Backend started successfully (PID: $BACKEND_PID)"
        return 0
    else
        print_error "Backend failed to start"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    print_status "Starting React Frontend..."
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install Node.js."
        return 1
    fi
    
    # Check if npm is installed
    if ! command -v npm &> /dev/null; then
        print_error "npm is not installed. Please install npm."
        return 1
    fi
    
    cd frontend
    
    # Install dependencies if node_modules doesn't exist
    if [ ! -d "node_modules" ]; then
        print_status "Installing frontend dependencies..."
        npm install
        if [ $? -ne 0 ]; then
            print_error "Failed to install frontend dependencies"
            cd ..
            return 1
        fi
    fi
    
    # Explicitly set PORT to 3000 to avoid conflicts
    export PORT=3000
    
    # Start the development server
    npm start > ../frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    
    # Wait for frontend to be ready
    if wait_for_service 3000 "Frontend"; then
        print_success "Frontend started successfully (PID: $FRONTEND_PID)"
        return 0
    else
        print_error "Frontend failed to start"
        return 1
    fi
}

# Function to stop all services
stop_services() {
    print_status "Stopping all services..."
    
    # Kill processes on specific ports
    kill_port_processes 5001 "Python API"
    kill_port_processes 8080 "Backend"
    kill_port_processes 3000 "Frontend"
    
    # Kill any remaining processes
    if [ ! -z "$PYTHON_API_PID" ]; then
        kill $PYTHON_API_PID 2>/dev/null
    fi
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    
    # Clean up log files
    rm -f backend.log frontend.log python-api.log
    
    print_success "All services stopped"
}

# Function to show status
show_status() {
    echo ""
    print_status "Service Status:"
    echo "=================="
    
    if check_port 5001; then
        print_success "Python API: Running on port 5001"
    else
        print_error "Python API: Not running"
    fi
    
    if check_port 8080; then
        print_success "Backend: Running on port 8080"
    else
        print_error "Backend: Not running"
    fi
    
    if check_port 3000; then
        print_success "Frontend: Running on port 3000"
    else
        print_error "Frontend: Not running"
    fi
    
    echo ""
    print_status "Access URLs:"
    echo "============="
    print_status "Frontend: http://localhost:3000"
    print_status "Backend API: http://localhost:8080"
    print_status "Python API: http://localhost:5001"
    print_status "Health Checks:"
    print_status "  - Backend: http://localhost:8080/api/pdf/health"
    print_status "  - Python API: http://localhost:5001/health"
}

# Main script logic
main() {
    echo ""
    print_status "PDF Financial Statement Processor - Full Stack Application"
    echo "================================================================"
    
    # Check if this is a restart
    if [ "$1" = "restart" ]; then
        print_status "Restarting application..."
        stop_services
        sleep 3
    elif [ "$1" = "stop" ]; then
        stop_services
        exit 0
    elif [ "$1" = "status" ]; then
        show_status
        exit 0
    elif [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
        echo ""
        print_status "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  (no args)  - Start the application"
        echo "  restart    - Restart the application"
        echo "  stop       - Stop the application"
        echo "  status     - Show service status"
        echo "  help       - Show this help message"
        echo ""
        echo "Services:"
        echo "  - Python API Server (port 5001)"
        echo "  - Spring Boot Backend (port 8080)"
        echo "  - React Frontend (port 3000)"
        echo ""
        exit 0
    fi
    
    # Make scripts executable
    chmod +x start-backend.sh start-frontend.sh start-python-api.sh 2>/dev/null
    
    # Start Python API first (required by backend)
    if start_python_api; then
        # Start backend
        if start_backend; then
            # Start frontend
            if start_frontend; then
                echo ""
                print_success "🎉 Application started successfully!"
                show_status
                echo ""
                print_status "Press Ctrl+C to stop all services"
                
                # Wait for user to stop
                trap 'echo ""; print_status "Shutting down..."; stop_services; exit 0' INT
                wait
            else
                print_error "Failed to start frontend"
                stop_services
                exit 1
            fi
        else
            print_error "Failed to start backend"
            stop_services
            exit 1
        fi
    else
        print_error "Failed to start Python API"
        exit 1
    fi
}

# Run main function with all arguments
main "$@" 