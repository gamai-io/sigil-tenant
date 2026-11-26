#!/bin/bash
# Install the API and watchdog as systemd units. Uses the directory this script
# lives in; no path is hardcoded.
set -e
BD=$(cd "$(dirname "$0")" && pwd)
TENANT_BASE=${TENANT_BASE:-/var/lib/sigil-tenant}
mkdir -p "$TENANT_BASE"

cat > /etc/systemd/system/sigil-tenant-api.service <<U
[Unit]
Description=SIGIL multi-tenant API
After=network.target
[Service]
Type=simple
Environment=TENANT_BASE=$TENANT_BASE
Environment=TENANT_API_HOST=${TENANT_API_HOST:-127.0.0.1}
Environment=TENANT_API_PORT=${TENANT_API_PORT:-18400}
ExecStart=/usr/bin/python3 $BD/tenant_api.py
Restart=always
RestartSec=3
Environment=PYTHONUNBUFFERED=1
[Install]
WantedBy=multi-user.target
U

cat > /etc/systemd/system/sigil-tenant-watchdog.service <<U
[Unit]
Description=SIGIL tenant watchdog
[Service]
Type=oneshot
Environment=TENANT_BASE=$TENANT_BASE
Environment=SIGIL_CODE=$BD
ExecStart=/usr/bin/python3 $BD/watchdog.py
U

cat > /etc/systemd/system/sigil-tenant-watchdog.timer <<'U'
[Unit]
Description=Run SIGIL tenant watchdog every 60s
[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
[Install]
WantedBy=timers.target
U

systemctl daemon-reload
systemctl enable --now sigil-tenant-api sigil-tenant-watchdog.timer
echo "installed; api=$(systemctl is-active sigil-tenant-api) watchdog=$(systemctl is-active sigil-tenant-watchdog.timer)"
