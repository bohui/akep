# Security

AKEP receivers process untrusted network input. Treat every event as hostile until verified.

Required receiver behavior:

- Verify the transport signature against the exact raw body bytes.
- Reject stale timestamps, duplicated event ids, unknown subscriptions, oversized payloads, and unknown event types.
- Reject events whose `source.name` or `source.producer_id` is not allowed by the subscription.
- Store inbound events before expensive work.
- Return `2xx` quickly after verification and durable persistence.
- Never execute a command from an event body.
- Never run an LLM inline inside the webhook handler.
- Use local policy to decide whether verified knowledge may resume an agent task.
- Use per-producer/per-subscriber secrets in production.
- Support key rotation with multiple `webhook-signature` values and, where available, `webhook-signature-key-id`.
- Treat replay cursors as bearer secrets when they expose tenant event history.

Report security issues privately until a disclosure process is published.
