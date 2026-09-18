#!/usr/bin/env bash
# Launch the SynFinder app behind a reverse proxy (e.g. Snellius OnDemand).
# The origin check is relaxed because the proxy presents a different Origin
# header than the host Streamlit serves on; without this the page loads but
# the websocket is rejected and it spins forever.
exec "$HOME/venvs/synfinder/bin/streamlit" run \
  "$(dirname "$0")/app/streamlit_app.py" \
  --server.headless true \
  --server.port "${PORT:-8501}" \
  --server.address 0.0.0.0 \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false
