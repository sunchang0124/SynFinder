#!/usr/bin/env bash
# Serve the SynFinder web interface.
#
#   ./run_web.sh              -> http://localhost:8501
#   PORT=9000 ./run_web.sh    -> a different port
#   PYTHON=/path/to/python ./run_web.sh
#
# From a clean clone:
#   python3 -m venv .venv && source .venv/bin/activate
#   pip install -e ".[web]"
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8501}"

# Prefer an explicit choice, then an active venv, then a local .venv, then
# whatever python3 is on PATH. A bare "python" is often an old system build.
pick_python() {
  [ -n "${PYTHON:-}" ] && { echo "$PYTHON"; return; }
  [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ] && { echo "$VIRTUAL_ENV/bin/python"; return; }
  [ -x "$HERE/.venv/bin/python" ] && { echo "$HERE/.venv/bin/python"; return; }
  command -v python3 || command -v python
}
PY="$(pick_python)"

if ! "$PY" -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "FastAPI and uvicorn are not installed for $PY" >&2
  echo "  python3 -m venv .venv && source .venv/bin/activate" >&2
  echo "  pip install -e \".[web]\"" >&2
  exit 1
fi

echo "SynFinder on http://localhost:${PORT}  (using $PY)"
exec "$PY" -m uvicorn synfinder.web:app \
  --host 0.0.0.0 --port "${PORT}" --app-dir "${HERE}/src"
