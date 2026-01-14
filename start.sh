#!/bin/bash

# Start backend
echo "Starting backend..."
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Save PIDs for stop script
echo $BACKEND_PID > .backend.pid
echo $FRONTEND_PID > .frontend.pid

echo ""
echo "================================"
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "================================"
echo ""
echo "Press Ctrl+C to stop, or run ./stop.sh"

# Wait for Ctrl+C
wait

