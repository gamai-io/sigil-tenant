#!/bin/bash
# Start one tenant: gate, verify and anchor on BASE, BASE+1, BASE+2.
# SIGIL_CODE points at a checkout of the SIGIL runtime.
set -e
TENANT=${1:-acme}
BASE=${2:-18300}
ROOT=${SIGIL_CODE:?set SIGIL_CODE to the SIGIL runtime checkout}
PY=${PY:-python3}
TENANTS=${TENANT_TENANTS_DIR:-$HOME/sigil-tenants}
RT="$TENANTS/$TENANT"
mkdir -p "$RT"
SIGIL_RUNTIME="$RT" SIGIL_RESET=1 bash "$ROOT/deploy/init.sh" >/dev/null 2>&1
export PYTHONPATH="$ROOT"
B="SIGIL_DATA=$RT/data SIGIL_EFFECTS=$RT/effects SIGIL_PUB_DIR=$RT/keys/pub SIGIL_CONTROL_TOKEN_FILE=$RT/keys/control_token SIGIL_APPROVER_TOKEN_FILE=$RT/keys/approver_token SIGIL_CHAIN_ID=$TENANT-1"
env $B SIGIL_PORT=$BASE SIGIL_PRIV_PATH=$RT/keys/kms/gate-ed25519-1.pem SIGIL_KEY_ID=gate-ed25519-1 SIGIL_ANCHOR_KEY_ID=anchor-ed25519-1 nohup "$PY" -m sigil.gate >"$RT/gate.log" 2>&1 & echo $! >"$RT/gate.pid"
env $B SIGIL_PORT=$((BASE+1)) nohup "$PY" -m sigil.verify >"$RT/verify.log" 2>&1 & echo $! >"$RT/verify.pid"
env $B SIGIL_PORT=$((BASE+2)) SIGIL_PRIV_PATH=$RT/keys/kms/anchor-ed25519-1.pem SIGIL_KEY_ID=anchor-ed25519-1 SIGIL_ANCHOR_ALLOW_LOCAL=1 SIGIL_GATE=http://127.0.0.1:$BASE nohup "$PY" -m sigil.anchor >"$RT/anchor.log" 2>&1 & echo $! >"$RT/anchor.pid"
sleep 3
echo "tenant=$TENANT chain=$TENANT-1 gate=:$BASE verify=:$((BASE+1)) anchor=:$((BASE+2)) runtime=$RT"
for p in $BASE $((BASE+1)) $((BASE+2)); do printf "  :%s " $p; curl -s -m3 http://127.0.0.1:$p/health || echo FAIL; echo; done
