# Replay and Acknowledgement

Webhook push is the low-latency path. Inbox replay is the reliability
path. AKEP implementations that advertise the `replay_inbox` profile
MUST implement this contract.

## Cursor Replay

```http
GET /akep/events?cursor=<opaque>&limit=100
```

`cursor` is opaque. Clients MUST store and round-trip it unchanged.
Servers MAY encode offsets, timestamps, event ids, tenant ids, or shard
positions inside it.

Response:

```json
{
  "events": [],
  "next_cursor": "cur_42",
  "has_more": false
}
```

Rules:

- `limit` defaults to `100` and MUST NOT exceed `1000`.
- Events MUST be returned in stable replay order.
- Replay order SHOULD be `received_at`, with ties broken by `event_id`.
- `next_cursor` MUST point after the final returned event.
- Empty pages are valid and still return a `next_cursor`.
- Servers SHOULD retain unacknowledged events for at least 7 days.

## Long-Poll Wait

```http
GET /akep/events/wait?cursor=<opaque>&timeout_seconds=60
```

Servers hold the request until events after `cursor` are available or
the timeout expires. `timeout_seconds` MUST be capped at 60.

- `200 OK` returns the same page shape as cursor replay.
- `204 No Content` means no event became available before timeout.

This gives local agents and serverless workers an HTTP-only way to wait
without exposing a public webhook.

## Acknowledgement

```http
POST /akep/events/{event_id}/ack
content-type: application/json

{
  "status": "stored",
  "processed_at": "2026-05-19T03:12:00Z",
  "reason": "persisted to local inbox"
}
```

`status` values:

| Status | Meaning |
| --- | --- |
| `stored` | Receiver durably stored the event but did not apply it yet. |
| `applied` | Receiver applied the event to local memory or resumed work. |
| `rejected` | Receiver refused to apply the event after storage. |

Ack is idempotent. Repeating the same ack MUST return success.

Ack does not mean the event executed a command. It only reports receiver
disposition after local policy handled the knowledge.

## Causality and Ordering

Two optional `routing` fields help receivers detect out-of-order or
gap-prone delivery without changing the wire envelope:

| Field                  | Meaning                                                                      |
| ---------------------- | ---------------------------------------------------------------------------- |
| `routing.causation_id` | The `event_id` of the event that caused this event, when the producer knows. |
| `routing.sequence`     | A monotonic, per-`subject` counter the producer maintains.                   |

Receivers MAY use them as follows:

- If `routing.sequence` for a given `subject.task_id` (or `thread_id`)
  goes backwards or skips, the receiver SHOULD treat the subject as
  out-of-order and trigger a cursor replay for that subject before
  applying further events.
- `routing.causation_id` is for audit and trace correlation. Receivers
  SHOULD NOT block on it (the producer may legitimately omit it), but
  SHOULD persist it alongside the event for debugging.

These fields are advisory. Receivers without ordering needs can ignore
them. Producers that cannot emit them MAY leave them off.

## Task State Lookup

```http
GET /akep/tasks/{task_id}
```

This endpoint is optional for basic event receivers and required for
implementations that advertise the `task_state` profile. It returns the
receiver's current view of a task reconstructed from durable state and
inbox events:

```json
{
  "task_id": "task_123",
  "status": "completed",
  "updated_at": "2026-05-19T03:12:00Z",
  "events": ["evt_sense2ai_..."],
  "artifacts": [
    {
      "uri": "https://sense2.ai/artifacts/sub_456",
      "content_type": "application/json"
    }
  ]
}
```
