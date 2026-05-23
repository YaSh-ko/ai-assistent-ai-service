#!/bin/bash
# Startup script for Python AI Service

# Activate virtual environment
source .venv/bin/activate

# Unset GIGACHAT_CREDENTIALS to avoid conflicts
unset GIGACHAT_CREDENTIALS

# Start the service
echo "Starting Python AI Service on port 8001..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001
