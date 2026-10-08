#!/usr/bin/env bash
# Start backend (127.0.0.1:8000) and frontend (127.0.0.1:5173). First run: ./start.sh --init
set -e
cd "$(dirname "$0")"
if [ "$1" = "--init" ]; then (cd backend && python -m app.cli init --demo); fi
(cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev) &
wait
