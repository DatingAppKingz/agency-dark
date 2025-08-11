#!/bin/bash

# OAuth Load Testing Script
# Run comprehensive load tests for OAuth implementation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
HOST="${HOST:-http://localhost:8000}"
NUM_USERS="${NUM_USERS:-100}"
SPAWN_RATE="${SPAWN_RATE:-10}"
RUN_TIME="${RUN_TIME:-300}"  # 5 minutes default
TEST_TYPE="${TEST_TYPE:-standard}"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}         OAuth Load Testing Suite${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Function to check dependencies
check_dependencies() {
    echo -e "\n${YELLOW}Checking dependencies...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Check Locust
    if ! python3 -c "import locust" 2>/dev/null; then
        echo -e "${YELLOW}Installing Locust...${NC}"
        pip3 install locust
    fi
    
    # Check other dependencies
    for pkg in aiohttp psutil numpy redis; do
        if ! python3 -c "import $pkg" 2>/dev/null; then
            echo -e "${YELLOW}Installing $pkg...${NC}"
            pip3 install $pkg
        fi
    done
    
    echo -e "${GREEN}✓ All dependencies installed${NC}"
}

# Function to check if services are running
check_services() {
    echo -e "\n${YELLOW}Checking services...${NC}"
    
    # Check if backend is running
    if curl -f -s -o /dev/null "$HOST/docs"; then
        echo -e "${GREEN}✓ Backend is running at $HOST${NC}"
    else
        echo -e "${RED}✗ Backend is not running at $HOST${NC}"
        echo -e "${YELLOW}Please start the backend first${NC}"
        exit 1
    fi
    
    # Check Redis
    if redis-cli ping &>/dev/null; then
        echo -e "${GREEN}✓ Redis is running${NC}"
    else
        echo -e "${RED}✗ Redis is not running${NC}"
        echo -e "${YELLOW}Please start Redis first${NC}"
        exit 1
    fi
    
    # Check PostgreSQL
    if pg_isready &>/dev/null; then
        echo -e "${GREEN}✓ PostgreSQL is running${NC}"
    else
        echo -e "${RED}✗ PostgreSQL is not running${NC}"
        echo -e "${YELLOW}Please start PostgreSQL first${NC}"
        exit 1
    fi
}

# Function to run Python load tests
run_python_tests() {
    echo -e "\n${YELLOW}Running Python load tests...${NC}"
    
    # Run OAuth performance tests
    echo -e "\n${GREEN}1. OAuth Performance Tests${NC}"
    python3 test_oauth_performance.py || true
    
    # Run connection pool tests
    echo -e "\n${GREEN}2. Connection Pool Tests${NC}"
    python3 test_connection_pools.py || true
}

# Function to run Locust tests
run_locust_tests() {
    echo -e "\n${YELLOW}Running Locust load tests...${NC}"
    
    case "$TEST_TYPE" in
        "standard")
            echo -e "${GREEN}Running Standard Load Test${NC}"
            ;;
        "high-load")
            echo -e "${GREEN}Running High Load Stress Test${NC}"
            NUM_USERS=500
            SPAWN_RATE=50
            ;;
        "multi-tenant")
            echo -e "${GREEN}Running Multi-Tenant Load Test${NC}"
            NUM_USERS=200
            SPAWN_RATE=20
            ;;
    esac
    
    echo -e "Configuration:"
    echo -e "  Host: $HOST"
    echo -e "  Users: $NUM_USERS"
    echo -e "  Spawn Rate: $SPAWN_RATE/s"
    echo -e "  Run Time: ${RUN_TIME}s"
    
    # Run Locust in headless mode
    locust \
        -f oauth_locustfile.py \
        --host="$HOST" \
        --users="$NUM_USERS" \
        --spawn-rate="$SPAWN_RATE" \
        --run-time="${RUN_TIME}s" \
        --headless \
        --test-type="$TEST_TYPE" \
        --html="oauth_load_test_report.html" \
        --csv="oauth_load_test" \
        --logfile="oauth_load_test.log"
}

# Function to run K6 tests if available
run_k6_tests() {
    if command -v k6 &> /dev/null; then
        echo -e "\n${YELLOW}Running K6 load tests...${NC}"
        
        if [ -f "k6_load_test.js" ]; then
            k6 run \
                --vus "$NUM_USERS" \
                --duration "${RUN_TIME}s" \
                --out json=k6_results.json \
                k6_load_test.js || true
        else
            echo -e "${YELLOW}K6 test file not found, skipping...${NC}"
        fi
    else
        echo -e "\n${YELLOW}K6 not installed, skipping K6 tests${NC}"
    fi
}

# Function to generate report
generate_report() {
    echo -e "\n${YELLOW}Generating load test report...${NC}"
    
    REPORT_FILE="oauth_load_test_report_$(date +%Y%m%d_%H%M%S).txt"
    
    {
        echo "════════════════════════════════════════════════════════════"
        echo "           OAuth Load Test Report"
        echo "════════════════════════════════════════════════════════════"
        echo "Generated: $(date)"
        echo "Test Type: $TEST_TYPE"
        echo "Host: $HOST"
        echo "Users: $NUM_USERS"
        echo "Duration: ${RUN_TIME}s"
        echo ""
        
        # Include Python test results if available
        if [ -f "oauth_load_test_report.txt" ]; then
            echo "Python Test Results:"
            echo "────────────────────────────────────────────────────────────"
            cat oauth_load_test_report.txt
            echo ""
        fi
        
        # Include Locust CSV stats if available
        if [ -f "oauth_load_test_stats.csv" ]; then
            echo "Locust Statistics:"
            echo "────────────────────────────────────────────────────────────"
            python3 -c "
import csv
with open('oauth_load_test_stats.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('Name') and row['Name'] != 'Aggregated':
            print(f\"  {row['Name']}:\")
            print(f\"    Requests: {row.get('Request Count', 'N/A')}\")
            print(f\"    Failures: {row.get('Failure Count', 'N/A')}\")
            print(f\"    Avg Response: {row.get('Average Response Time', 'N/A')}ms\")
            print(f\"    95% Response: {row.get('95%', 'N/A')}ms\")
"
            echo ""
        fi
        
        # System resource usage
        echo "System Resources During Test:"
        echo "────────────────────────────────────────────────────────────"
        echo "  CPU Usage: $(top -l 1 | grep "CPU usage" | awk '{print $3}' 2>/dev/null || echo "N/A")"
        echo "  Memory Usage: $(vm_stat | grep "Pages active" | awk '{print $3}' 2>/dev/null || echo "N/A")"
        echo ""
        
        echo "════════════════════════════════════════════════════════════"
        echo "Test completed successfully!"
        echo "════════════════════════════════════════════════════════════"
    } > "$REPORT_FILE"
    
    echo -e "${GREEN}✓ Report saved to: $REPORT_FILE${NC}"
    
    # Display summary
    echo -e "\n${GREEN}Test Summary:${NC}"
    tail -n 20 "$REPORT_FILE"
}

# Function to clean up
cleanup() {
    echo -e "\n${YELLOW}Cleaning up...${NC}"
    
    # Archive results
    ARCHIVE_DIR="results_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$ARCHIVE_DIR"
    
    # Move all result files
    for file in oauth_load_test*; do
        if [ -f "$file" ]; then
            mv "$file" "$ARCHIVE_DIR/" 2>/dev/null || true
        fi
    done
    
    # Move K6 results if they exist
    [ -f "k6_results.json" ] && mv k6_results.json "$ARCHIVE_DIR/" 2>/dev/null || true
    
    echo -e "${GREEN}✓ Results archived to: $ARCHIVE_DIR${NC}"
}

# Main execution
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --host)
                HOST="$2"
                shift 2
                ;;
            --users)
                NUM_USERS="$2"
                shift 2
                ;;
            --spawn-rate)
                SPAWN_RATE="$2"
                shift 2
                ;;
            --time)
                RUN_TIME="$2"
                shift 2
                ;;
            --type)
                TEST_TYPE="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --host HOST           Target host (default: http://localhost:8000)"
                echo "  --users NUM           Number of users (default: 100)"
                echo "  --spawn-rate RATE     Spawn rate (default: 10)"
                echo "  --time SECONDS        Run time in seconds (default: 300)"
                echo "  --type TYPE           Test type: standard|high-load|multi-tenant"
                echo "  --help                Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run tests
    check_dependencies
    check_services
    
    # Create results directory
    mkdir -p results
    cd results
    
    # Run different test suites
    run_python_tests
    run_locust_tests
    run_k6_tests
    
    # Generate and display report
    generate_report
    
    # Clean up
    cleanup
    
    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}         Load testing completed successfully!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Trap errors and cleanup
trap cleanup EXIT

# Run main function
main "$@"