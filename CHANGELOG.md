# Changelog

## 4.0.3 — 2026-11-26
- Rate limiting is per tenant for `/t/...` (a botnet behind many addresses cannot
  use one budget) and per source for the rest; 429 with `Retry-After: 60`.


## 4.0.1 — 2026-11-26
- The AI Act chain compares the computed head with `chain_head.json`, so a
  truncated or deleted tail is `ok:false, code:"truncated"` (it used to report a
  clean chain of zero records).
- Tenant names are validated (`[a-z0-9][a-z0-9._-]{0,62}`, no `..`, no slashes)
  before they are used in filesystem paths; `DELETE` validates too.
- `GET /tenants` requires the admin token; an empty stored API key no longer
  matches an absent header.
- Metering updates take an exclusive lock and use `os.replace`, so concurrent
  requests do not lose counts.
- A new tenant's base port skips ports already used (deleting a tenant can no
  longer make the next one collide), and creation fails if no runtime answers.
- A body with a negative or oversized `Content-Length` is rejected instead of
  blocking a thread.

## 4.0 — 2026-11-26
- Initial public release.
