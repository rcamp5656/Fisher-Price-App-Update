#!/usr/bin/env bash
# Fisher-Price Record Maker - one-click local start (macOS / Linux)
# Dedicated To My Fiancée Barbara - (c) 2026 Russ Campbell
# macOS: double-click start-mac.command   Linux: ./start-linux.sh
set -e
cd "$(dirname "$0")"
echo
echo " ======================================================"
echo "  Fisher-Price Record Maker  -  one-click local start"
echo " ======================================================"
echo

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo " [!] Python 3.10+ not found. Install from https://www.python.org/downloads/ (or: brew install python)"; read -r -p "Press Enter to close"; exit 1
fi
if ! command -v node >/dev/null 2>&1; then
  echo " [!] Node.js not found. Install the LTS version from https://nodejs.org/ (or: brew install node)"; read -r -p "Press Enter to close"; exit 1
fi

echo " [1/4] MongoDB ..."
if pgrep -x mongod >/dev/null 2>&1; then
  echo "       already running"
elif command -v brew >/dev/null 2>&1 && brew list --formula 2>/dev/null | grep -q mongodb-community; then
  brew services start mongodb-community >/dev/null && echo "       started via Homebrew"
elif command -v mongod >/dev/null 2>&1; then
  mkdir -p data/db
  (mongod --dbpath data/db --port 27017 >data/mongod.log 2>&1 &)
  echo "       started (data/db)"
else
  echo "       mongod not found - install MongoDB Community: https://www.mongodb.com/docs/manual/administration/install-community/"
  echo "       (macOS: brew tap mongodb/brew && brew install mongodb-community)"
  echo "       Continuing - the app needs MongoDB on mongodb://localhost:27017 to save records."
fi

echo " [2/4] Backend: Python packages ..."
[ -d backend/.venv ] || "$PY" -m venv backend/.venv
# shellcheck disable=SC1091
source backend/.venv/bin/activate
python -m pip install --quiet --upgrade pip
pip install --quiet -r backend/requirements-local.txt
[ -f backend/.env ] || printf 'MONGO_URL=mongodb://localhost:27017\nDB_NAME=fisher_price\n' > backend/.env
(cd backend && uvicorn server:app --host 0.0.0.0 --port 8001 >../data-backend.log 2>&1 &)
echo "       backend on http://localhost:8001 (log: data-backend.log)"

echo " [3/4] Frontend: Node packages (first run takes a few minutes) ..."
[ -f frontend/.env ] || printf 'REACT_APP_BACKEND_URL=http://localhost:8001\n' > frontend/.env
cd frontend
[ -d node_modules ] || npm install --silent --legacy-peer-deps
echo " [4/4] Starting the web app - your browser opens at http://localhost:3000"
echo "       Press Ctrl+C here to stop."
echo
BROWSER=none npm start &
FE=$!
sleep 15
(command -v open >/dev/null && open http://localhost:3000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:3000) || true
trap 'kill $FE 2>/dev/null; pkill -f "uvicorn server:app" 2>/dev/null; exit 0' INT TERM
wait $FE
