#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER="${SUDO_USER:-$USER}"

echo "Climate Monitor — Systemd Service Installer"
echo "==========================================="
echo ""
echo "Project: $PROJECT_DIR"
echo "User:    $USER"

# ----- Detect venv ---------------------------------------------------------
if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
elif [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    VENV_PYTHON="$(command -v python3)"
else
    echo "ERROR: Cannot find Python. Create a venv first:"
    echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

echo "Venv:    $VENV_PYTHON"
echo ""

# ----- Choose mode ---------------------------------------------------------
echo "Select deployment mode:"
echo "  1) recorder  — sensor Pi, writes data (installs sync timer)"
echo "  2) webserver — dashboard machine, serves charts"
echo "  3) combined  — single machine, runs both"
read -r -p "Choice [1]: " CHOICE
CHOICE="${CHOICE:-1}"

SERVICES_DIR="$PROJECT_DIR/services"

case "$CHOICE" in
    1)
        MODE="recorder"
        SERVICE_FILES="climate-monitor-recorder.service climate-monitor-sync.service climate-monitor-sync.timer"
        ;;
    2)
        MODE="webserver"
        SERVICE_FILES="climate-monitor-webserver.service"
        ;;
    3)
        MODE="combined"
        SERVICE_FILES="climate-monitor.service"
        ;;
    *)
        echo "Invalid choice."
        exit 1
        ;;
esac

echo ""
echo "Mode: $MODE"

# ----- Install service files -----------------------------------------------
for src in $SERVICE_FILES; do
    name="$(basename "$src")"
    dst="/etc/systemd/system/$name"

    # Substitute placeholders
    sed -e "s|{PROJECT_DIR}|$PROJECT_DIR|g" \
        -e "s|{VENV_PYTHON}|$VENV_PYTHON|g" \
        -e "s|{USER}|$USER|g" \
        "$SERVICES_DIR/$src" | sudo tee "$dst" > /dev/null

    echo "  Installed $name"
done

# ----- Reload and enable ---------------------------------------------------
sudo systemctl daemon-reload

for src in $SERVICE_FILES; do
    name="$(basename "$src")"
    sudo systemctl enable "$name"
    sudo systemctl restart "$name"
    echo "  Enabled $name"
done

echo ""
echo "Done. Service status:"
for src in $SERVICE_FILES; do
    name="$(basename "$src")"
    systemctl status "$name" --no-pager --lines=0 2>/dev/null || true
done

# ----- Start first sync (recorder) ----------------------------------------
if [ "$MODE" = "recorder" ]; then
    echo ""
    echo "Starting first sync..."
    sudo systemctl start climate-monitor-sync.service

    echo ""
    echo "---- Tailscale Sync Setup ----"
    echo "1. Edit scripts/sync_db.sh and set TARGET to your webserver's Tailscale hostname."
    echo "2. Copy your SSH key to the webserver:"
    echo "     ssh-copy-id <TARGET>"
    echo "3. On the webserver, create the data directory:"
    echo "     mkdir -p ~/climate-monitor/data"
    echo "4. On the webserver, install the webserver service:"
    echo "     bash scripts/install_services.sh  (choose 'webserver')"
    echo ""
    echo "Check sync timer: systemctl status climate-monitor-sync.timer"
    echo "Trigger sync now: sudo systemctl start climate-monitor-sync"
fi

echo ""
echo "View logs: journalctl -u climate-monitor-$MODE -f"
