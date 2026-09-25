#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/ubuntu/telegram-monitor"
SERVICE_SOURCE="$APP_DIR/deploy/telegram-monitor.service"
SERVICE_TARGET="/etc/systemd/system/telegram-monitor.service"

if [[ "$(id -un)" != "ubuntu" ]]; then
    echo "Run this script as the ubuntu user." >&2
    exit 1
fi

cd "$APP_DIR"

sudo apt-get update
sudo apt-get install -y python3 python3-venv

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

chmod 600 .env telegram_session.session alert_monitor.db
sudo install -o root -g root -m 0644 "$SERVICE_SOURCE" "$SERVICE_TARGET"
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-monitor.service

echo
echo "Telegram monitor installed and started."
echo "Status: sudo systemctl status telegram-monitor --no-pager"
echo "Logs:   sudo journalctl -u telegram-monitor -f"
