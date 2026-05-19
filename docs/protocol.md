# AKEP v1 Draft Protocol

Status: Draft  
Protocol name: Async Knowledge Event Protocol  
Wire version: `akep.v1`

## 1. Purpose

AKEP standardizes how asynchronous knowledge is delivered to AI agents.

An AKEP event says: "new external knowledge is available for a subject." It does not say: "execute this command." That distinction is the protocol's safety boundary.

AKEP is designed for:

- long-running tools
- human approval and review
- knowledge publisher task fulfillment
- sensor and real-world observations
- background model and batch jobs
- artifact, file, and memory changes
- offline local agents that need replay

AKEP is not a full agent-to-agent negotiation protocol. Use A2A-style
protocols when two autonomous agents need capability discovery,
conversation, and task negotiation. Use AKEP when an external system has
asynchronous knowledge that should be delivered into an agent inbox.

## 2. Architecture

```text
producer
  -> delivery adapter
  -> signed AKEP event
  -> receiver
  -> durable inbox
  -> normalizer
  -> memory / task state
  -> resume queue
```

Receivers MUST verify and persist the event before any expensive processing.

Receivers MUST NOT invoke a model, call arbitrary tools, or execute commands directly from a webhook handler.

## 3. Event Envelope

Every event is a JSON object with this shape:

```json
{
  "spec": "akep.v1",
  "event_id": "evt_01HX5S8ZQ9J6W9E5W4H8A2K7D3",
  "event_type": "knowledge.acquired",
  "occurred_at": "2026-05-17T03:00:00Z",
  "source": {
    "producer_id": "prod_sense2ai_01",
    "name": "sense2ai",
    "type": "publisher",
    "source_event_id": "submission_sub_456_completed"
  },
  "subject": {
    "task_id": "task_123",
    "thread_id": "thread_456",
    "agent_id": "agent_local_abc"
  },
  "knowledge": {
    "kind": "observation",
    "content_type": "application/json",
    "uri": "https://sense2.ai/artifacts/sub_456",
    "summary": "Defaced property video is ready. Condition good, noise low.",
    "confidence": 0.82,
    "content": {
      "defaced_video_url": "https://example.invalid/defaced-video.mp4",
      "json_summary": {
        "condition": "good",
        "noise": "low"
      }
    }
  },
  "routing": {
    "resume_policy": "resume_if_waiting",
    "priority": "normal",
    "interrupt_id": "optional_interrupt_id",
    "causation_id": "evt_previous_01",
    "sequence": 42
  },
  "links": {
    "self": "https://sense2.ai/api/akep/events/evt_01HX5S8ZQ9J6W9E5W4H8A2K7D3",
    "ack": "https://sense2.ai/api/akep/events/evt_01HX5S8ZQ9J6W9E5W4H8A2K7D3/ack"
  }
}
```

### Required Fields

| Field | Requirement |
| --- | --- |
| `spec` | MUST be `akep.v1` for this draft. |
| `event_id` | MUST be globally unique and stable across retries. |
| `event_type` | MUST be one of the core types or a reverse-DNS/vendor extension. |
| `occurred_at` | MUST be the ISO 8601 time the knowledge event occurred. |
| `source` | MUST identify the event producer. |
| `subject` | MUST identify at least one task, thread, agent, user, or artifact the event concerns. |
| `knowledge` | MUST contain normalized knowledge or a pointer to it. |
| `routing` | MUST contain resume advice. Receivers MAY ignore it after persistence. |

## 4. Core Event Types

| Event type | Meaning |
| --- | --- |
| `knowledge.acquired` | New external knowledge is available. |
| `tool.completed` | A long-running tool completed. |
| `tool.failed` | A long-running tool failed. |
| `human.review_required` | Work is blocked on human review. |
| `human.approved` | Human review approved a pending item. |
| `human.rejected` | Human review rejected a pending item. |
| `file.updated` | A watched artifact changed. |
| `memory.changed` | A memory item was created, updated, or invalidated. |
| `message.received` | A message arrived asynchronously. |

Vendor-specific events MAY use reverse-DNS names, for example `ai.sense2.task.completed`, but producers SHOULD map them to a core `event_type` where possible.

## 5. Knowledge Kinds

| Kind | Use |
| --- | --- |
| `observation` | Real-world or sensor observation. |
| `tool_result` | Output of a long-running tool. |
| `approval` | Human decision or review state. |
| `document` | Document or parsed document output. |
| `artifact` | File, media, model output, or build artifact. |
| `message` | User, system, or agent message. |
| `memory` | Memory mutation or invalidation notice. |

Large media SHOULD be sent as URLs, content-addressed identifiers, or resource references, not embedded directly.

## 6. Resume Policies

| Policy | Receiver behavior |
| --- | --- |
| `never` | Store/index the event but never resume a task from it. |
| `append_only` | Add the event to inbox and memory only. |
| `resume_if_waiting` | Resume only if local task state is waiting for this subject, event type, or interrupt id. |
| `resume_immediately` | Queue a resume after verification and local policy checks. |

`routing.resume_policy` is advice, not authority. Local policy always wins.

`routing.causation_id` SHOULD point to the event that caused this event
when a producer can express causality. `routing.sequence` SHOULD be
monotonic per subject when a producer can detect out-of-order delivery.

## 7. Delivery Transports

AKEP defines the envelope and receiver semantics. Transports are adapters.

Recommended transports:

- Standard Webhooks HTTP POST for simple producer-to-receiver delivery.
- Hosted relay with outbound SSE, WebSocket, or polling for local agents.
- Queue adapters for backend-to-backend deployments.
- Tunnels such as Cloudflare Tunnel, Hookdeck, ngrok, or Tailscale Funnel for development.

Production desktop agents SHOULD prefer outbound relay connections instead of exposing a local port.

Implementations SHOULD advertise supported transport and behavior
profiles through `GET /.well-known/akep.json`. See
[`discovery.md`](discovery.md) and [`profiles.md`](profiles.md).

## 8. Webhook Transport

Webhook delivery MUST use Standard Webhooks-compatible metadata headers:

```text
webhook-id: evt_01HX5S8ZQ9J6W9E5W4H8A2K7D3
webhook-timestamp: 1778157296
webhook-signature: v1,<base64-hmac-sha256>
webhook-signature-key-id: 2026-05
content-type: application/json
```

For symmetric signatures, compute:

```text
HMAC_SHA256(secret, webhook-id + "." + webhook-timestamp + "." + raw_body)
```

The receiver MUST verify against the exact raw body bytes that arrived on the wire. Parsing and reserializing JSON before verification will break signatures and can introduce security bugs.

`webhook-id` and `webhook-timestamp` MUST NOT contain `.`. Producers MAY
send multiple signatures in one `webhook-signature` header during key
rotation. Receivers MUST accept the event if any signature validates
against an active key for the producer and subscription. See
[`signatures.md`](signatures.md).

Receivers MUST reject when:

- a required header is missing
- `webhook-id` differs from the body `event_id`
- timestamp is outside the receiver tolerance, recommended 5 minutes
- signature is invalid
- event id was already processed
- event type or subject does not match a subscription
- payload exceeds configured limits
- payload attempts to encode a direct command

## 9. Inbox and Acknowledgement

Receivers SHOULD maintain a durable inbox with at least:

```text
events(event_id, event_type, source_name, subject_json, received_at, verified, processed_at, raw_json)
subscriptions(subscription_id, filters_json, delivery_json, secret_ref)
knowledge_items(id, source_event_id, kind, content_hash, summary, uri)
tasks(task_id, status, waiting_for_json, run_state_ref)
```

Producers SHOULD expose replay and acknowledgement endpoints:

```http
GET /akep/events?cursor=<cursor>
POST /akep/events/{event_id}/ack
```

Webhook push is the low-latency path. Inbox replay is the reliability path.

Replay cursors are opaque. Replay responses MUST use this shape:

```json
{
  "events": [],
  "next_cursor": "cur_42",
  "has_more": false
}
```

Implementations that advertise the replay profile MUST also support:

```http
GET /akep/events/wait?cursor=<cursor>&timeout_seconds=60
GET /akep/tasks/{task_id}
```

The wait endpoint is long-polling over ordinary HTTP and returns either a
replay page (`200 OK`) or `204 No Content` on timeout. See
[`replay-and-ack.md`](replay-and-ack.md) for the normative replay,
wait, ack, and task-state contract.

## 10. Subscriptions

An agent SHOULD subscribe with declared capabilities rather than exposing an unfiltered endpoint.

```json
{
  "spec": "akep.v1",
  "sink": "agent.local.123",
  "event_types": ["knowledge.acquired", "tool.completed"],
  "filters": {
    "subject.task_id": "task_123",
    "knowledge.kind": ["observation", "tool_result"]
  },
  "delivery": {
    "type": "webhook",
    "url": "https://example.com/akep/events",
    "ack_required": true,
    "replay_retention_seconds": 604800
  },
  "security": {
    "accepted_source_names": ["sense2ai"],
    "accepted_producer_ids": ["prod_sense2ai_01"],
    "signature_key_ids": ["2026-05"]
  },
  "capabilities": {
    "resume_policies": ["append_only", "resume_if_waiting"],
    "max_payload_bytes": 1048576
  }
}
```

Receivers SHOULD reject events that do not match a known subscription.

Filter keys are dotted JSON paths. Scalar values mean equality, array
values mean membership, and all filter keys are combined with AND.

## 11. Relationship to Other Protocols

AKEP does not replace MCP, A2A, workflow engines, or model SDKs.

- Use MCP for tools, resources, prompts, and structured calls.
- Use AKEP for async events, inbox replay, and controlled task resume.
- Use workflow engines for durable execution.
- Use model SDKs for reasoning once local policy has accepted an event.

## 12. Adoption Profiles

AKEP compatibility is profile-based:

- Core Event Receiver: webhook ingestion, signature verification,
  idempotency, inbox persistence, and safe resume policy handling.
- Replay Inbox: cursor replay, ack, and long-poll wait.
- Relay: outbound delivery for local/domainless agents.
- Task State: HTTP task-state retrieval.
- Knowledge Publisher Results: real-world or external knowledge result events.

See [`profiles.md`](profiles.md).

## 13. Compatibility Requirements

An implementation is AKEP v1 compatible if it:

- accepts and emits the `akep.v1` event envelope
- verifies Standard Webhooks-compatible signatures for webhook transport
- stores `event_id` as an idempotency key
- separates event ingestion from model/tool execution
- supports at least `append_only` and `resume_if_waiting`
- documents its subscription and payload limits
