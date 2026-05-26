#!/bin/bash
set -e

# Start uvicorn in the background
uvicorn app.main:app --host 0.0.0.0 --port 8001 &
SERVER_PID=$!

# Wait up to 60s for the health endpoint to respond
echo "[entrypoint] Waiting for server to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        echo "[entrypoint] Server is ready."
        break
    fi
    sleep 2
done

# Check how many symbols have price data (0 = fresh volume)
SYMBOLS=$(curl -s http://localhost:8001/api/v1/screener/universe/status 2>/dev/null \
    | python3 -c "import sys,json; data=json.load(sys.stdin); print(data.get('total_symbols_in_db', 0))" 2>/dev/null \
    || echo "0")

if [ "$SYMBOLS" -lt "10" ]; then
    echo "[entrypoint] Fresh install detected - triggering bulk download in background..."
    curl -s -X POST http://localhost:8001/api/v1/screener/universe/download > /dev/null
    echo "[entrypoint] Download started. Data will populate over the next few minutes."
else
    echo "[entrypoint] $SYMBOLS symbols already in DB - skipping seed."
fi

# Hand control back to uvicorn
wait $SERVER_PID
