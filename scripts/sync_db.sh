#!/bin/bash
set -e

# --- Configuration ----------------------------------------------------------
# Set TARGET to the Tailscale hostname (or IP) of your webserver machine.
# Example: TARGET="my-webserver" or TARGET="my-webserver.tailnet-name.ts.net"
TARGET="webserver-hostname"

PROJECT_DIR="$HOME/climate-monitor"
# ---------------------------------------------------------------------------

DB_PATH="$PROJECT_DIR/data/sensor_data.db"
SNAPSHOT="/tmp/climate_sync.db"

mkdir -p "$(dirname "$SNAPSHOT")"
rm -f "$SNAPSHOT"

sqlite3 "$DB_PATH" "VACUUM INTO '$SNAPSHOT'"

rsync -az "$SNAPSHOT" "${TARGET}:${PROJECT_DIR}/data/sensor_data.db"
