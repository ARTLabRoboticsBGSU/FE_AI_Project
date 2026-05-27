#!/usr/bin/env bash
# Simple launcher for running ChatISA on a specific network address/port
# Usage: ./start.sh [address] [port]

ADDRESS=${1:-0.0.0.0}
PORT=${2:-8501}

echo "Starting ChatISA on ${ADDRESS}:${PORT}..."
python -m streamlit run chatgpt.py --server.address "${ADDRESS}" --server.port "${PORT}" --server.enableCORS false
