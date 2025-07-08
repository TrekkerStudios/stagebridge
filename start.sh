#!/bin/bash

cd ~/VSCode/stagebridge/bin
./backend &
PYTHON_PID=$!
./frontend &
BUN_PID=$!

# Function to handle cleanup on Ctrl+C
cleanup() {
    echo "Caught Ctrl+C. Stopping processes..."
    kill $PYTHON_PID 2>/dev/null
    kill $BUN_PID 2>/dev/null
    exit 0
}

# Trap SIGINT (Ctrl+C) and call cleanup
trap cleanup SIGINT

# Wait for both processes
wait $PYTHON_PID
wait $BUN_PID