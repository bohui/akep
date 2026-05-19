# Signatures and Key Rotation

AKEP webhook delivery uses Standard Webhooks-compatible metadata headers.
Receivers verify the exact raw body bytes before parsing JSON.

## Required Headers

```http
webhook-id: evt_01HX5S8ZQ9J6W9E5W4H8A2K7D3
webhook-timestamp: 1778157296
webhook-signature: v1,<base64-hmac-sha256>
webhook-signature-key-id: 2026-05
```

`webhook-signature-key-id` is optional for single-key deployments and
recommended for production. It lets receivers choose the correct active
secret without trying every configured key.

## Signature Base String

```text
webhook-id + "." + webhook-timestamp + "." + raw_body
```

`webhook-id` and `webhook-timestamp` MUST NOT contain `.`. The receiver
MUST reject an event when the header `webhook-id` differs from the body
`event_id`.

## Algorithm Registry

| Tag | Algorithm | Encoding | Status |
| --- | --- | --- | --- |
| `v1` | HMAC-SHA256 | base64 | Required for v1 receivers |
| `v1a` | Ed25519 | base64 | Reserved |
| `v2` | Reserved | Reserved | Reserved |

Receivers MUST reject unknown algorithm tags unless the subscription
explicitly opts into them.

## Rotation

During rotation, producers MAY send multiple signatures in the same
header, separated by spaces:

```http
webhook-signature: v1,<old-signature> v1,<new-signature>
```

Receivers MUST accept the event if any signature validates against an
active key for the producer and subscription. Producers SHOULD overlap
old and new keys for at least the maximum retry window.

Production deployments SHOULD use a different secret for each
producer/subscriber pair. A shared global secret is acceptable only for
local demos.
