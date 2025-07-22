#!/bin/bash

cd ~/VSCode/stagebridge/bin
./sb-beta &
#./stagebridge &
PYTHON_PID=$!

cleanup() {
    echo "Caught Ctrl+C. Stopping processes..."
    kill $PYTHON_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT

wait $PYTHON_PID