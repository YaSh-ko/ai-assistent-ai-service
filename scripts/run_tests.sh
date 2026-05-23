#!/bin/bash
# Helper script to run tests properly with pytest

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Python AI Service - Test Runner${NC}"
echo "=========================================="
echo ""

# Check if pytest is installed
if ! python3 -m pytest --version &> /dev/null; then
    echo -e "${RED}✗ pytest is not installed${NC}"
    echo ""
    echo "Install it with:"
    echo "  pip install pytest pytest-asyncio"
    exit 1
fi

echo -e "${GREEN}✓ pytest is installed${NC}"
echo ""

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage:"
    echo "  $0 all                    # Run all tests"
    echo "  $0 unit                   # Run unit tests only"
    echo "  $0 e2e                    # Run e2e tests only"
    echo "  $0 services               # Run service tests"
    echo "  $0 providers              # Run provider tests"
    echo "  $0 reasoning              # Run reasoning tests"
    echo "  $0 <path>                 # Run specific test file"
    echo ""
    echo "Examples:"
    echo "  $0 all"
    echo "  $0 tests/services/test_reasoning_service.py"
    echo "  $0 tests/e2e/test_rag_reasoning.py"
    echo ""
    exit 0
fi

# Parse command
case "$1" in
    all)
        echo -e "${YELLOW}Running all tests...${NC}"
        python3 -m pytest -v
        ;;
    unit)
        echo -e "${YELLOW}Running unit tests...${NC}"
        python3 -m pytest tests/ -v --ignore=tests/e2e --ignore=tests/integration
        ;;
    e2e)
        echo -e "${YELLOW}Running e2e tests...${NC}"
        python3 -m pytest tests/e2e/ -v
        ;;
    services)
        echo -e "${YELLOW}Running service tests...${NC}"
        python3 -m pytest tests/services/ -v
        ;;
    providers)
        echo -e "${YELLOW}Running provider tests...${NC}"
        python3 -m pytest tests/providers/ -v
        ;;
    reasoning)
        echo -e "${YELLOW}Running reasoning tests...${NC}"
        python3 -m pytest tests/services/test_reasoning_service.py tests/providers/test_reasoning.py -v
        ;;
    *)
        # Assume it's a file path
        if [ -f "$1" ]; then
            echo -e "${YELLOW}Running test file: $1${NC}"
            python3 -m pytest "$1" -v
        else
            echo -e "${RED}✗ File not found: $1${NC}"
            echo ""
            echo "Make sure the file path is correct and relative to project root."
            exit 1
        fi
        ;;
esac

# Show result
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Tests completed successfully!${NC}"
else
    echo ""
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
