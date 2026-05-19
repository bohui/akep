# AKEP Adoption Profiles

AKEP is intentionally small. Adoption should happen through profiles so
simple receivers can stay simple while production platforms can advertise
stronger behavior.

## Profile: Core Event Receiver

Required for every compatible implementation.

- Accept `POST /akep/events`.
- Verify Standard Webhooks signatures.
- Reject stale timestamps, duplicate event ids, unknown subscriptions,
  oversized payloads, and direct-command payloads.
- Persist the raw event before expensive processing.
- Treat `routing.resume_policy` as advice.
- Support `append_only` and `resume_if_waiting`.

## Profile: Replay Inbox

For agents that may be offline or hibernating.

- Implement `GET /akep/events?cursor=...&limit=...`.
- Implement `POST /akep/events/{event_id}/ack`.
- Retain unacknowledged events for at least 7 days.
- Return stable opaque cursors.

## Profile: Relay

For local or domainless agents that cannot receive inbound webhooks.

- Receive producer webhooks at a hosted relay.
- Store events per subscriber.
- Let the agent connect outward using replay, long-poll, SSE, or
  WebSocket.
- Ack only after the local agent durably stores the event.

Relay is the recommended production path for desktop agents such as
Hermes, OpenClaw, Codex-style local agents, and other runtimes behind
NAT.

## Profile: Task State

For systems that want task-level retrieval in addition to event replay.

- Implement `GET /akep/tasks/{task_id}`.
- Map external producer states into task states.
- Include artifact pointers and related event ids.
- Do not require the task endpoint for event-only producers.

## Profile: Knowledge Publisher Results

For knowledge publishers where an agent asks humans or systems to
collect real-world context.

Recommended flow:

1. An agent requests knowledge through the publisher's own API.
2. The publisher returns or assigns stable correlation ids.
3. The publisher emits AKEP events for completion, failure, or human review.
4. The receiver accepts events at one AKEP endpoint.
5. The receiver writes the event into an inbox and resumes the
   matching durable workflow.

Use AKEP for the async result boundary. AKEP does not standardize task
creation or publisher-specific ordering flows.

## Profile Discovery

Services SHOULD expose:

```http
GET /.well-known/akep.json
```

The discovery document lists supported profiles, endpoints, signature
algorithms, schema URLs, and retention promises.
