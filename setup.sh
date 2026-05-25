#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  SETUP SCRIPT — Stock Analysis Trading System
#  Run this once to set up the project from scratch.
# ─────────────────────────────────────────────────────────
set -e

echo ""
echo "=========================================="
echo "  Stock Analysis Trading System — Setup"
echo "=========================================="
echo ""

# ── 1. Create directories ───────────────────────────────
echo "[1/5] Creating directories..."
mkdir -p data/db data/cache data/exports docs/daily_logs

# ── 2. Backend setup ────────────────────────────────────
echo "[2/5] Setting up Python backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  python3 -m venv venv
  echo "  ✓ Created Python virtual environment"
fi

# Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✓ Installed Python dependencies"

cd ..

# ── 3. Frontend setup ───────────────────────────────────
echo "[3/5] Setting up React frontend..."
cd frontend

if command -v node &>/dev/null; then
  npm install --silent
  echo "  ✓ Installed Node.js dependencies"
else
  echo "  ⚠ Node.js not found. Install from https://nodejs.org then run: cd frontend && npm install"
fi

cd ..

# ── 4. Environment file ──────────────────────────────────
echo "[4/5] Setting up environment file..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  ✓ Created .env from template"
  echo "  ℹ Edit .env to add optional API keys for richer data"
else
  echo "  ✓ .env already exists — skipping"
fi

# ── 5. Initialize database ───────────────────────────────
echo "[5/5] Initializing database..."
cd backend
source venv/bin/activate
python -c "
from app.database.database import init_db
init_db()
print('  ✓ Database initialized')
"
cd ..

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "To start the system:"
echo ""
echo "  Terminal 1 (backend):"
echo "    cd backend"
echo "    source venv/bin/activate"
echo "    uvicorn app.main:app --reload --port 8000"
echo ""
echo "  Terminal 2 (frontend):"
echo "    cd frontend"
echo "    npm run dev"
echo ""
echo "  Then open http://localhost:5173 in your browser."
echo ""
