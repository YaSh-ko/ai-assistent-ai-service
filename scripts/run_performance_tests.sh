#!/bin/bash

# Performance Testing Script
# Runs comprehensive stress tests and generates report

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8001}"  # Changed default to 8001
RESULTS_DIR="stress_test_results"
REPORT_FILE="docs/performance_report.md"

echo -e "${GREEN}=== AI Service Performance Testing ===${NC}\n"
echo "Using service URL: ${BASE_URL}"
echo "(Set BASE_URL environment variable to use different URL)"
echo ""

# Check if service is running
echo -e "${YELLOW}Checking if service is running...${NC}"
if ! curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}Error: Service is not running at ${BASE_URL}${NC}"
    echo "Please start the service first:"
    echo "  python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001"
    exit 1
fi
echo -e "${GREEN}✓ Service is running${NC}\n"

# Create results directory
mkdir -p "${RESULTS_DIR}"

# Function to run a test
run_test() {
    local name=$1
    local users=$2
    local duration=$3
    local rps=$4
    local type=$5
    
    echo -e "${YELLOW}Running test: ${name}${NC}"
    echo "  Users: ${users}, Duration: ${duration}s, RPS: ${rps}, Type: ${type}"
    
    # Get script directory (parent of scripts dir)
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
    
    python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
        --url "${BASE_URL}" \
        --users "${users}" \
        --duration "${duration}" \
        --rps "${rps}" \
        --type "${type}" \
        --output "${RESULTS_DIR}/${name}.json"
    
    echo -e "${GREEN}✓ Test completed${NC}\n"
    
    # Cool down between tests
    echo "Cooling down for 5 seconds..."
    sleep 5
}

# Test Suite 1: Simple Requests
echo -e "${GREEN}=== Test Suite 1: Simple Requests ===${NC}\n"

run_test "simple_10users_10rps" 10 30 10 "simple"
run_test "simple_50users_50rps" 50 30 50 "simple"
run_test "simple_100users_100rps" 100 30 100 "simple"

# Test Suite 2: RAG Requests
echo -e "${GREEN}=== Test Suite 2: RAG Requests ===${NC}\n"

run_test "rag_10users_10rps" 10 30 10 "rag"
run_test "rag_50users_50rps" 50 30 50 "rag"

# Test Suite 3: Reasoning Requests
echo -e "${GREEN}=== Test Suite 3: Reasoning Requests ===${NC}\n"

run_test "reasoning_10users_5rps" 10 30 5 "reasoning"
run_test "reasoning_20users_10rps" 20 30 10 "reasoning"

# Test Suite 4: Streaming Requests
echo -e "${GREEN}=== Test Suite 4: Streaming Requests ===${NC}\n"

run_test "streaming_10users_10rps" 10 30 10 "streaming"
run_test "streaming_50users_50rps" 50 30 50 "streaming"

# Generate report
echo -e "${GREEN}=== Generating Performance Report ===${NC}\n"

# Get script directory (parent of scripts dir)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

python3 "${SCRIPT_DIR}/scripts/analyze_stress_results.py" \
    --results-dir "${RESULTS_DIR}" \
    --output "${REPORT_FILE}"

echo -e "${GREEN}✓ Report generated: ${REPORT_FILE}${NC}\n"

# Summary
echo -e "${GREEN}=== Test Summary ===${NC}\n"

total_tests=$(ls -1 "${RESULTS_DIR}"/*.json 2>/dev/null | wc -l)
echo "Total tests run: ${total_tests}"
echo "Results directory: ${RESULTS_DIR}"
echo "Report file: ${REPORT_FILE}"

echo -e "\n${GREEN}=== All tests completed successfully! ===${NC}"
echo -e "\nView the report:"
echo -e "  cat ${REPORT_FILE}"
echo -e "\nOr open in browser:"
echo -e "  xdg-open ${REPORT_FILE}  # Linux"
echo -e "  open ${REPORT_FILE}      # macOS"
