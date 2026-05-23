#!/bin/bash

# Start test server for stress testing

PORT="${PORT:-8001}"  # Default to 8001 to avoid conflicts

echo "Starting AI service on port ${PORT}..."

# Check if server is already running
if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
    echo "Server is already running at http://localhost:${PORT}"
    exit 0
fi

# Start server in background
echo "Starting server..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT} > /tmp/test_server_${PORT}.log 2>&1 &
SERVER_PID=$!

echo "Server PID: $SERVER_PID"
echo "Waiting for server to start..."

# Wait for server to be ready
for i in {1..30}; do
    if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
        echo "✓ Server is ready at http://localhost:${PORT}!"
        echo "Server logs: /tmp/test_server_${PORT}.log"
        echo "To stop: kill $SERVER_PID"
        echo ""
        echo "Run tests with:"
        echo "  BASE_URL=http://localhost:${PORT} python3 scripts/quick_test.py"
        exit 0
    fi
    sleep 1
    echo -n "."
done

echo ""
echo "✗ Server failed to start within 30 seconds"
echo "Check logs: tail -f /tmp/test_server_${PORT}.log"
kill $SERVER_PID 2>/dev/null
exit 1
