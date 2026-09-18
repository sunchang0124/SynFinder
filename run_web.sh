#!/usr/bin/env bash
# Serve the SynFinder web interface.
exec "$HOME/venvs/synfinder/bin/uvicorn" synfinder.web:app \
  --host 0.0.0.0 --port "${PORT:-8502}" --app-dir "$(dirname "$0")/src"
