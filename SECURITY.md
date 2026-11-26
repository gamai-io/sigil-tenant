# Security notes

## Reporting

Write to renato@gamatrade.ba with the tag `[sigil-tenant-security]`. We answer
within two working days.

## Supported versions

This is a reference implementation; only the current `main` is supported.

## Deployment assumptions

- Bind to loopback (`TENANT_API_HOST=127.0.0.1`) and terminate TLS in a proxy.
- `$TENANT_BASE/admin.token` must be `0600`; the API refuses admin calls without
  it.
- `TENANT_ALLOW_PRIVATE=1` widens the accepted source addresses to RFC1918 and
  Tailscale ranges. Use it only on a network you control.
- The sandbox endpoint mounts the Docker socket in the Compose example. That is
  host-level power for the API process; remove the mount and the endpoint if you
  do not need it.
- Tenants share one process and one state file. This is not a hardened
  multi-tenant boundary and must not be sold as one.
