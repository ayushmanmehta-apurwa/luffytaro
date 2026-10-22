#!/usr/bin/env bash
# One-time setup for Linux/macOS: python venv + backend dependencies + frontend dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
[ -f backend/.env ] || cp .env.example backend/.env
(cd frontend && npm install)
(cd backend && python init_db.py)
echo
echo "Done. Start the app in two terminals:"
echo "  1) . .venv/bin/activate && cd backend && uvicorn app.main:app --reload --port 8000"
echo "  2) cd frontend && npm run dev        (then open http://localhost:5173)"
