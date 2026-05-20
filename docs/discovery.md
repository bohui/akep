# Discovery

AKEP services SHOULD expose a discovery document at:

```http
GET /.well-known/akep.json
```

This lets agents and producers find supported profiles without reading a
README or hardcoding paths.

Example:

```json
{
  "spec": "akep.v1",
  "service_name": "AKEP reference receiver",
  "issuer": "https://akep.dev",
  "endpoints": {
    "events": "/akep/events",
    "replay": "/akep/events",
    "wait": "/akep/events/wait",
    "ack": "/akep/events/{event_id}/ack",
    "tasks": "/akep/tasks/{task_id}"
  },
  "delivery_profiles": ["webhook", "replay_inbox", "task_state"],
  "signature_algorithms": ["v1"],
  "auth_schemes": ["bearer"],
  "event_schema": "https://akep.dev/schemas/akep-event-v1.schema.json",
  "subscription_schema": "https://akep.dev/schemas/akep-subscription-v1.schema.json",
  "retention": {
    "minimum_unacked_seconds": 604800
  }
}
```

`delivery_profiles` lists the profiles the service implements. A
relay-only frontend would advertise `["webhook", "relay"]`; a
self-hosted SQLite inbox advertises `["webhook", "replay_inbox",
"task_state"]`. See [`profiles.md`](profiles.md).

`auth_schemes` declares how callers authenticate the replay, wait, ack,
and tasks endpoints — see [`auth.md`](auth.md). The discovery document
itself is unauthenticated bootstrap data.

The document is advisory. Security decisions still come from
subscriptions, credentials, and local policy.
