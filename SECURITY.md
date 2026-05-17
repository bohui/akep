# Security

AKEP receivers process untrusted network input. Treat every event as hostile until verified.

Required receiver behavior:

- Verify the transport signature against the exact raw body bytes.
- Reject stale timestamps, duplicated event ids, unknown subscriptions, oversized payloads, and unknown event types.
- Store inbound events before expensive work.
- Return `2xx` quickly after verification and durable persistence.
- Never execute a command from an event body.
- Never run an LLM inline inside the webhook handler.
- Use local policy to decide whether verified knowledge may resume an agent task.

Report security issues privately until a disclosure process is published.

