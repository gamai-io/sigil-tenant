#!/bin/bash
# Pull tenant state from a previous host over SSH. Set the host and key in the
# environment; nothing is hardcoded.
set -e
: "${OLD_HOST:?set OLD_HOST=user@host}"
KEY=${OLD_KEY:-$HOME/.ssh/id_ed25519}
DST=${TENANT_TENANTS_DIR:-$HOME/sigil-tenants}
mkdir -p "$DST"
rsync -a -e "ssh -i $KEY -o IdentitiesOnly=yes" "$OLD_HOST:/var/lib/sigil-tenants/" "$DST"/
echo "pulled from $OLD_HOST into $DST"
