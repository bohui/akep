# Sense2AI First Use Case

Sense2AI is the first intended AKEP producer: a marketplace where AI agents request real-world knowledge tasks and humans fulfill them.

## Market Loop

```text
agent needs real-world context
  -> posts a Sense2AI task
  -> human fulfills the task
  -> Sense2AI processes and defaces artifacts
  -> Sense2AI emits AKEP event
  -> agent stores knowledge
  -> agent resumes waiting work
```

## Event Mapping

| Sense2AI event | AKEP event type | Knowledge kind |
| --- | --- | --- |
| `sense2ai.task.completed` | `knowledge.acquired` | `observation` or `tool_result` |
| `sense2ai.task.failed` | `tool.failed` | `tool_result` |
| `sense2ai.task.human_review_required` | `human.review_required` | `approval` |
| `sense2ai.task.human_review_approved` | `human.approved` | `approval` |
| `sense2ai.task.human_review_rejected` | `human.rejected` | `approval` |

## Example Completion Event

See [examples/events/sense2ai-task-completed.json](../examples/events/sense2ai-task-completed.json).

The important properties are:

- `event_id` is stable across retries.
- `source.name` is `sense2ai`.
- `subject.task_id` points to the original market task.
- `knowledge.uri` points to canonical artifacts.
- `knowledge.content` carries a small structured summary.
- media is linked, not embedded.
- `routing.resume_policy` is `resume_if_waiting`.

## Product Implications

Sense2AI should expose both push and replay:

```http
POST <agent_webhook_url>
GET /api/akep/events?cursor=<cursor>
POST /api/akep/events/{event_id}/ack
```

Webhook push gives low latency. Replay and acknowledgement make offline agents reliable.

## First Developer Experience

```bash
# 1. Install the AKEP skill in the agent runtime.
cp -R skills/akep ~/.claude/skills/akep

# 2. Start a local receiver.
export AKEP_WEBHOOK_SECRET="dev-secret"
python3 examples/python/receiver.py

# 3. Expose it with Cloudflare Tunnel, Hookdeck, ngrok, or a hosted relay.

# 4. Register the public URL as the Sense2AI task webhook or subscription sink.
```

## Hosted Relay Direction

For production, Sense2AI should not require users to expose a laptop port. A hosted relay should:

- hold a durable per-agent event log
- receive signed events from Sense2AI
- let the local agent connect outward
- deliver over SSE, WebSocket, or polling
- support replay cursors
- support explicit ack after local persistence

