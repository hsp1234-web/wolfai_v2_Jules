#!/bin/bash
set -e
echo "DEBUG: Changing to /app/frontend"
cd /app/frontend

echo "DEBUG: Running npm run dev with timeout and redirection"
timeout 15s npm run dev -- -p 3000 -H 0.0.0.0 > ../test_frontend_log.txt 2>&1
NPM_EXIT_CODE=$?

echo "DEBUG: npm run dev finished or timed out. Exit code: ${NPM_EXIT_CODE}"
echo "DEBUG: Creating flag file ../test_frontend_flag.txt"
touch ../test_frontend_flag.txt

echo "DEBUG: test_frontend_startup.sh finished."
