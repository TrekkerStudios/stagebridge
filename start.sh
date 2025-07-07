#!/bin/bash

source .venv/bin/activate

cd ~/VSCode/stagebridge/backend
python main.py &
PYTHON_PID=$!

cd ~/VSCode/stagebridge/frontend
bun dev &
BUN_PID=$!

# Function to handle cleanup on Ctrl+C
cleanup() {
    echo "Caught Ctrl+C. Stopping processes..."
    kill $PYTHON_PID 2>/dev/null
    kill $BUN_PID 2>/dev/null
    deactivate
    exit 0
}

# Trap SIGINT (Ctrl+C) and call cleanup
trap cleanup SIGINT

# Wait for both processes
wait $PYTHON_PID
wait $BUN_PID

deactivate