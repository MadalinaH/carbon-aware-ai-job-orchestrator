#!/bin/bash
set -euo pipefail

echo "Starting port-forward for API service..."
echo "Open http://localhost:8000/health in your browser"
echo ""
echo "Press Ctrl+C to stop"
echo ""

kubectl port-forward svc/api 8000:8000

