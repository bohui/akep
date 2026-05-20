# Authentication

AKEP has two distinct authentication boundaries. They protect different
things and use different mechanisms.

## 1. Ingestion: `POST /akep/events`

Inbound events are authenticated by the Standard Webhooks signature
described in [`signatures.md`](signatures.md). The receiver MUST verify
`webhook-signature` over the raw body before parsing JSON.

No additional HTTP authentication is required on the ingestion endpoint —
the HMAC over body bytes is the auth.

## 2. Read endpoints: replay, wait, ack, tasks

The following endpoints expose stored events and reconstructed state and
MUST be authenticated in any non-local deployment:

```http
GET  /akep/events
GET  /akep/events/wait
POST /akep/events/{event_id}/ack
GET  /akep/tasks/{task_id}
```

Without authentication, anyone who can reach the receiver can dump the
full inbox or any task's reconstructed state. The reference receivers
default to "no auth" only so the local demo and CI flow can run without
secrets; in production you MUST set a bearer or use mTLS in front.

### Recommended schemes

| Scheme         | When to use                                                   |
| -------------- | ------------------------------------------------------------- |
| `bearer`       | Default for service-to-service. Token bound to the subscription. |
| `mtls`         | Closed networks where you already run mutual TLS.             |
| `signed_url`   | Replay cursors handed out as short-lived signed URLs.         |
| `none`         | Local demo only. Never in production.                         |

The reference Python receiver implements `bearer`:

```bash
export AKEP_REPLAY_BEARER="secret-token-from-your-secrets-manager"
python3 examples/python/receiver.py
```

Callers attach:

```http
Authorization: Bearer secret-token-from-your-secrets-manager
```

Without a valid token the receiver returns:

- `401 Unauthorized` (and `WWW-Authenticate: Bearer realm="akep"`) when
  the header is missing or malformed.
- `403 Forbidden` when the bearer token does not match.

### Discovery

Receivers SHOULD advertise the auth schemes they accept in
`/.well-known/akep.json`:

```json
{
  "spec": "akep.v1",
  "delivery_profiles": ["webhook", "replay_inbox", "task_state"],
  "signature_algorithms": ["v1"],
  "auth_schemes": ["bearer"]
}
```

Clients SHOULD inspect this field before calling read endpoints.

### Token rotation

Bearer tokens SHOULD be per-subscriber (or at least per-tenant) and
rotated on a fixed schedule. The same rotation guidance as for HMAC
secrets in [`signatures.md`](signatures.md) applies: overlap old and new
for at least the maximum retry window, and document the cutover.

## 3. Threat model

| Threat                                                  | Mitigation                                                                 |
| ------------------------------------------------------- | -------------------------------------------------------------------------- |
| Anyone GETs the inbox and exfiltrates events            | Bearer / mTLS on replay, wait, tasks.                                      |
| Stolen bearer token replays past events                 | Per-subscriber tokens; rotate; pair with mTLS or network ACL in production. |
| Cursor enumeration leaks event ordering                 | Opaque cursors; auth gates make enumeration meaningless without a token.   |
| Forged inbound event                                    | Standard Webhooks signature over raw body.                                 |
| Replayed inbound event                                  | Timestamp tolerance + dedup by `event_id`.                                 |
| Compromised producer signs anything                     | Per-subscription `accepted_producer_ids` + `signature_key_ids`; rotate secrets. |
| Producer rotates keys; old subscribers break overnight  | Multi-signature header during overlap window. See `signatures.md`.         |
