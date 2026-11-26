#!/bin/bash
# Copy the tenant state to another disk or host. Point DST at a mounted backup
# volume or an rsync target you control.
set -e
TENANTS=${TENANT_TENANTS_DIR:-$HOME/sigil-tenants}
SRC=${1:-$TENANTS}
DST=${2:?usage: backup.sh [SRC] DST}
mkdir -p "$DST"
rsync -a --delete "$SRC"/ "$DST"/
echo "backup ok $SRC -> $DST $(date -u +%FT%TZ)"
