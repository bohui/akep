# AKEP Protocol Summary

## Event Envelope

```json
{
  "spec": "akep.v1",
  "event_id": "evt_...",
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
    "summary": "Knowledge is ready.",
    "confidence": 0.82,
    "uri": "https://example.com/artifact",
    "content": {}
  },
  "routing": {
    "resume_policy": "resume_if_waiting",
    "priority": "normal",
    "interrupt_id": "optional",
    "sequence": 42
  }
}
```

## Webhook Signing

Required headers:

```text
webhook-id: evt_...
webhook-timestamp: 1778157296
webhook-signature: v1,<base64-hmac-sha256>
webhook-signature-key-id: 2026-05
content-type: application/json
```

Signature message:

```text
webhook-id + "." + webhook-timestamp + "." + raw_body
```

Verify against raw bytes before parsing JSON. Receivers should accept
any valid `v1` signature when multiple signatures are sent during key
rotation.

## Receiver Rules

Reject when:

- missing signature headers
- timestamp is stale
- signature is invalid
- `webhook-id` does not match `event_id`
- event id already exists in the inbox
- subscription filters do not match
- source name or producer id is not allowed by the subscription
- payload is too large
- event contains a direct command

## Sense2AI Mapping

| Sense2AI event | AKEP event type | Knowledge kind |
| --- | --- | --- |
| `sense2ai.task.completed` | `knowledge.acquired` | `observation` |
| `sense2ai.task.failed` | `tool.failed` | `tool_result` |
| `sense2ai.task.human_review_required` | `human.review_required` | `approval` |
| `sense2ai.task.human_review_approved` | `human.approved` | `approval` |
| `sense2ai.task.human_review_rejected` | `human.rejected` | `approval` |

Use normal Sense2AI REST APIs for task creation. Use AKEP for completion,
failure, review, and artifact result events.

## Replay

Replay-capable receivers expose:

```http
GET /akep/events?cursor=<opaque>&limit=100
GET /akep/events/wait?cursor=<opaque>&timeout_seconds=60
POST /akep/events/{event_id}/ack
```

Replay responses use `{ "events": [], "next_cursor": "...", "has_more": false }`.
