# SIGIL Tenant API

A small, dependency-free HTTP API that puts a multi-tenant face on the SIGIL
proof runtime: one tenant per customer, per-tenant API keys, metering and
billing counters, an EU AI Act audit trail (Art. 12/19/26/72) with a hash chain,
and an optional sandbox endpoint backed by the local container runtime.

> Status: reference implementation. It is a control-plane wrapper, **not** a
> hardened multi-tenant boundary: tenants share one process, one filesystem and
> (if enabled) one Docker socket. Read `SECURITY.md` before exposing it.

## What it does

| area | endpoint |
|---|---|
| health | `GET /health` |
| tenants (admin) | `GET/POST /tenants`, `DELETE /tenants/{t}` |
| receipts | `GET /t/{t}/receipts` |
| chain | `GET /t/{t}/chain/verify` |
| claims | `POST /t/{t}/verify` |
| usage / billing | `GET /t/{t}/usage`, `GET /t/{t}/billing` |
| AI Act trail | `POST /t/{t}/audit-event`, `GET /t/{t}/ai-act` |
| attestation | `POST /t/{t}/attest` |
| sandbox | `POST /t/{t}/sandbox` |

The OpenAPI stub is in `openapi.json`. All `/t/...` calls need `X-Api-Key`;
`/tenants` calls need `X-Admin-Token`, read from `$TENANT_BASE/admin.token`.

## Quickstart

```bash
export TENANT_BASE=$PWD/data
mkdir -p "$TENANT_BASE"
python3 -c 'import secrets;print(secrets.token_urlsafe(24))' > "$TENANT_BASE/admin.token"
chmod 600 "$TENANT_BASE/admin.token"
TENANT_BASE=$TENANT_BASE python3 tenant_api.py
```

In another shell:

```bash
TOK=$(cat data/admin.token)
curl -s -X POST 127.0.0.1:18400/tenants \
  -H "X-Admin-Token: $TOK" -d '{"name":"acme"}'
# {"tenant":"acme","api_key":"..."} — shown once
curl -s 127.0.0.1:18400/t/acme/billing -H "X-Api-Key: <key>"
```

Docker: `TENANT_BASE=./data docker compose up --build`.

## Configuration

| variable | default | meaning |
|---|---|---|
| `TENANT_BASE` | `~/.sigil-tenant` | state: `tenants.json`, `admin.token`, `fc.token` |
| `TENANT_TENANTS_DIR` | sibling `sigil-tenants` | per-tenant runtimes and audit files |
| `TENANT_API_HOST` | `127.0.0.1` | bind address (loopback by default) |
| `TENANT_API_PORT` | `18400` | port |
| `TENANT_ALLOW_PRIVATE` | `0` | accept RFC1918/Tailscale peers (for a private network) |
| `FC_HOST` / `FC_PORT` | `127.0.0.1:18500` | Firecracker/vsock endpoint for the sandbox |
| `SHARD_HOST` / `SHARD_PORT` | `127.0.0.1:7150` | optional execution shard |
| `SANDBOX_IMG` | `alpine:latest` | image used by the container sandbox |
| `TENANT_RATE_PER_MIN` | `120` | per-source requests per minute; `0` disables the limit |

## What it is not

- Not encrypted in transit: put it behind your TLS proxy. The proxy client does
  not follow redirects (a 30x would otherwise carry `X-SIGIL-Token` elsewhere).
- Not a hardened sandbox: the container endpoint needs the Docker socket; a
  compromised API process owns the host.
- Billing is a counter, not a ledger: `GET /t/{t}/invoice` turns usage counters
  into a pending invoice. Stripe is optional and only used if `STRIPE_SECRET_KEY`
  is set **and** the `stripe` package is installed; neither ships here.
- API keys are stored in `tenants.json` as issued (file mode is your control);
  hashing them is on the list, not in the code.

## License

Apache-2.0. See `LICENSE`.
