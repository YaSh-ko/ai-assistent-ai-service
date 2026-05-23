#!/bin/bash

# Conservative Stress Testing Script for GigaChat API
# Comprehensive test suite to collect all required metrics
# Uses low concurrency to avoid rate limits

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8001}"
RESULTS_DIR="stress_test_results"
MONITOR_PID=""

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Conservative Stress Testing - Complete Metrics Suite     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}\n"
echo "This script collects ALL required metrics:"
echo "  ✓ Latency p95 for simple, RAG, and reasoning requests"
echo "  ✓ Error rate measurements"
echo "  ✓ Throughput and RPS data"
echo "  ✓ Memory leak detection (long-running test)"
echo ""
echo "Using service URL: ${BASE_URL}"
echo "Results directory: ${RESULTS_DIR}"
echo ""

# Check service
echo -e "${YELLOW}Checking service health...${NC}"
if ! curl -s "${BASE_URL}/health" > /dev/null 2>&1; then
    echo -e "${RED}✗ Error: Service not running at ${BASE_URL}${NC}"
    echo "Start the service with: ./start_service.sh"
    exit 1
fi
echo -e "${GREEN}✓ Service is running${NC}\n"

mkdir -p "${RESULTS_DIR}"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

# Cleanup function
cleanup() {
    if [ ! -z "$MONITOR_PID" ] && kill -0 $MONITOR_PID 2>/dev/null; then
        echo -e "\n${YELLOW}Stopping performance monitor...${NC}"
        kill $MONITOR_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Start performance monitoring
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Starting Performance Monitor${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
python3 "${SCRIPT_DIR}/scripts/monitor_performance.py" \
    --interval 5 \
    --output "${RESULTS_DIR}/performance_monitoring.json" &
MONITOR_PID=$!
echo -e "${GREEN}✓ Monitor started (PID: $MONITOR_PID)${NC}\n"
sleep 2

# ============================================================================
# PHASE 1: SIMPLE REQUESTS (Latency p95 < 5s)
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}PHASE 1: Simple Requests (Target: p95 < 5000ms)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Test 1.1: Baseline (1 user, 1 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 1 \
    --duration 60 \
    --rps 1 \
    --type simple \
    --output "${RESULTS_DIR}/simple_1user_1rps.json"
echo -e "${GREEN}✓ Test 1.1 complete${NC}\n"
sleep 30

echo -e "${YELLOW}Test 1.2: Low load (3 users, 2 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 3 \
    --duration 60 \
    --rps 2 \
    --type simple \
    --output "${RESULTS_DIR}/simple_3users_2rps.json"
echo -e "${GREEN}✓ Test 1.2 complete${NC}\n"
sleep 30

echo -e "${YELLOW}Test 1.3: Medium load (5 users, 3 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 5 \
    --duration 60 \
    --rps 3 \
    --type simple \
    --output "${RESULTS_DIR}/simple_5users_3rps.json"
echo -e "${GREEN}✓ Test 1.3 complete${NC}\n"
sleep 30

# ============================================================================
# PHASE 2: RAG REQUESTS (Latency p95 < 5s)
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}PHASE 2: RAG Requests (Target: p95 < 5000ms)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Test 2.1: Baseline (1 user, 1 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 1 \
    --duration 60 \
    --rps 1 \
    --type rag \
    --output "${RESULTS_DIR}/rag_1user_1rps.json"
echo -e "${GREEN}✓ Test 2.1 complete${NC}\n"
sleep 30

echo -e "${YELLOW}Test 2.2: Low load (2 users, 1 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 2 \
    --duration 60 \
    --rps 1 \
    --type rag \
    --output "${RESULTS_DIR}/rag_2users_1rps.json"
echo -e "${GREEN}✓ Test 2.2 complete${NC}\n"
sleep 30

echo -e "${YELLOW}Test 2.3: Medium load (3 users, 2 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 3 \
    --duration 60 \
    --rps 2 \
    --type rag \
    --output "${RESULTS_DIR}/rag_3users_2rps.json"
echo -e "${GREEN}✓ Test 2.3 complete${NC}\n"
sleep 30

# ============================================================================
# PHASE 3: REASONING REQUESTS (Latency p95 < 15s)
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}PHASE 3: Reasoning Requests (Target: p95 < 15000ms)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Test 3.1: Baseline (1 user, 0.5 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 1 \
    --duration 60 \
    --rps 0.5 \
    --type reasoning \
    --output "${RESULTS_DIR}/reasoning_1user_0.5rps.json"
echo -e "${GREEN}✓ Test 3.1 complete${NC}\n"
sleep 30

echo -e "${YELLOW}Test 3.2: Low load (2 users, 1 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 2 \
    --duration 60 \
    --rps 1 \
    --type reasoning \
    --output "${RESULTS_DIR}/reasoning_2users_1rps.json"
echo -e "${GREEN}✓ Test 3.2 complete${NC}\n"
sleep 30

# ============================================================================
# PHASE 4: STREAMING REQUESTS
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}PHASE 4: Streaming Requests${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Test 4.1: Baseline (1 user, 1 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 1 \
    --duration 60 \
    --rps 1 \
    --type streaming \
    --output "${RESULTS_DIR}/streaming_1user_1rps.json"
echo -e "${GREEN}✓ Test 4.1 complete${NC}\n"
sleep 30

echo -e "${YELLOW}Test 4.2: Medium load (3 users, 2 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 3 \
    --duration 60 \
    --rps 2 \
    --type streaming \
    --output "${RESULTS_DIR}/streaming_3users_2rps.json"
echo -e "${GREEN}✓ Test 4.2 complete${NC}\n"
sleep 30

echo -e "${YELLOW}Test 4.3: Higher load (5 users, 3 RPS)${NC}"
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 5 \
    --duration 60 \
    --rps 3 \
    --type streaming \
    --output "${RESULTS_DIR}/streaming_5users_3rps.json"
echo -e "${GREEN}✓ Test 4.3 complete${NC}\n"
sleep 30

# ============================================================================
# PHASE 5: MEMORY LEAK TEST (Long-running)
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}PHASE 5: Memory Leak Detection (30 min test)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Test 5.1: Long-running streaming (30 minutes)${NC}"
echo "This test will run for 30 minutes to detect memory leaks"
echo "Monitor memory usage in: ${RESULTS_DIR}/performance_monitoring.json"
echo ""
python3 "${SCRIPT_DIR}/scripts/stress_test.py" \
    --url "${BASE_URL}" \
    --users 3 \
    --duration 1800 \
    --rps 2 \
    --type streaming \
    --output "${RESULTS_DIR}/memory_leak_test_30min.json"
echo -e "${GREEN}✓ Test 5.1 complete${NC}\n"

# Stop monitoring
if [ ! -z "$MONITOR_PID" ] && kill -0 $MONITOR_PID 2>/dev/null; then
    kill $MONITOR_PID 2>/dev/null || true
    MONITOR_PID=""
fi

# ============================================================================
# GENERATE REPORT
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Generating Performance Report${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

python3 "${SCRIPT_DIR}/scripts/analyze_stress_results.py"

# ============================================================================
# SUMMARY
# ============================================================================
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Test Suite Complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"

echo "Results saved in: ${RESULTS_DIR}/"
echo ""
echo -e "${GREEN}Files created:${NC}"
ls -lh "${RESULTS_DIR}/"*.json 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
echo ""

echo -e "${GREEN}Performance Report:${NC}"
if [ -f "docs/performance_report.md" ]; then
    echo "  docs/performance_report.md"
    echo ""
    echo "View report:"
    echo "  cat docs/performance_report.md"
else
    echo "  ${RED}Not generated - check for errors${NC}"
fi
echo ""

echo -e "${GREEN}Monitoring Data:${NC}"
if [ -f "${RESULTS_DIR}/performance_monitoring.json" ]; then
    echo "  ${RESULTS_DIR}/performance_monitoring.json"
    echo ""
    echo "Check for memory leaks:"
    echo "  python3 -c \"import json; data=json.load(open('${RESULTS_DIR}/performance_monitoring.json')); print('Memory samples:', len(data.get('memory_history', [])))\""
fi
echo ""

echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Review the performance report:"
echo "   cat docs/performance_report.md"
echo ""
echo "2. Check if requirements are met:"
echo "   - Simple requests: p95 < 5000ms"
echo "   - RAG requests: p95 < 5000ms"
echo "   - Reasoning requests: p95 < 15000ms"
echo "   - Error rate: < 1%"
echo "   - Memory: stable over 30 minutes"
echo ""
echo "3. If tests failed due to rate limits:"
echo "   - Check GigaChat credentials"
echo "   - Consider using OpenAI/Anthropic for testing"
echo "   - See: docs/GIGACHAT_AUTH_TROUBLESHOOTING.md"
echo ""

echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}All metrics collected successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}\n"
