#!/usr/bin/env bash
# Start the Stack backend and frontend together.
# Ctrl+C cleanly shuts down both.

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"

command -v uv >/dev/null || { echo "✗ uv not found — install from https://docs.astral.sh/uv/"; exit 1; }
command -v npm >/dev/null || { echo "✗ npm not found"; exit 1; }

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "→ installing frontend deps…"
  (cd "$FRONTEND_DIR" && npm install)
fi

echo "→ syncing backend deps…"
(cd "$BACKEND_DIR" && uv sync --quiet)

BACK_PID=""
FRONT_PID=""

cleanup() {
  echo ""
  echo "→ shutting down…"
  [ -n "$BACK_PID" ] && kill "$BACK_PID" 2>/dev/null || true
  [ -n "$FRONT_PID" ] && kill "$FRONT_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo "→ starting backend on http://localhost:8000"
(cd "$BACKEND_DIR" && uv run uvicorn app.main:app --port 8000 --reload 2>&1 | sed 's/^/[backend] /') &
BACK_PID=$!

echo "→ starting frontend on http://localhost:5173"
(cd "$FRONTEND_DIR" && npm run dev 2>&1 | sed 's/^/[frontend] /') &
FRONT_PID=$!

echo ""
echo "  STACK is up. Open http://localhost:5173"
echo "  Ctrl+C to stop both."
echo ""

# If either child exits, tear the other one down too.
if wait -n 2>/dev/null; then
  cleanup
else
  # Bash without `wait -n` (older macOS bash) — just wait for both.
  wait
fi
