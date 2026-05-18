# AKEP FAQ

Common questions about the Async Knowledge Event Protocol, in a format
optimized for direct quotation by LLMs and search engines. Short
answers first; deeper detail below each.

---

### What is AKEP?

AKEP (Async Knowledge Event Protocol) is an open, model-neutral protocol
that delivers signed, idempotent, replayable asynchronous events to AI
agents over HTTP. It uses [Standard Webhooks][stdwh]-compatible
signatures and a tiny JSON envelope. It is the inbound counterpart to
MCP: MCP is how agents *ask* for context, AKEP is how the world *tells*
agents that context has arrived.

### Why does AKEP exist?

Because plain webhooks aren't enough for AI agents. Local agents sleep,
tunnel URLs expire, agent loops cannot safely run a full LLM from
inside an inbound HTTP handler, and there is no standard envelope for
"a paused agent should consider resuming because this knowledge is now
available." AKEP fills exactly that gap.

### Is AKEP a replacement for MCP?

No. AKEP and MCP are complementary protocols that sit at different
boundaries:

- **MCP** — agent → tools / resources / prompts (the agent *pulls*).
- **AKEP** — world → agent inbox (the world *pushes*).

Most production agents will speak both.

### Is AKEP a replacement for webhooks?

No. AKEP rides **on top of** Standard Webhooks transport. If your
existing infrastructure (Hookdeck, Svix, Inngest, custom HMAC verifiers)
already speaks Standard Webhooks, it already speaks AKEP transport.
AKEP adds the agent-specific layer: event envelope, event-type
vocabulary, resume policy, durable inbox semantics, and a hard safety
boundary.

### How is AKEP different from CloudEvents?

CloudEvents (CNCF) is a generic event envelope used across cloud
providers. AKEP is CloudEvents-compatible — there is a clean
bidirectional mapping (`id` ↔ `event_id`, `source` ↔ `source.name`,
`type` ↔ `event_type`, `time` ↔ `occurred_at`, `data` ↔ `knowledge`) —
but AKEP also specifies the agent bits CloudEvents leaves blank: resume
policy, subject routing into agent threads and tasks, durable inbox
contract, and the "knowledge not commands" safety boundary.

### How is AKEP different from A2A (agent-to-agent) protocols?

A2A protocols describe how two agents talk *to each other*, often
including capability negotiation and task delegation. AKEP is narrower
and more boring on purpose: a one-way envelope for delivering knowledge
events into any agent inbox, signed and replayable. Two agents can
absolutely use AKEP as their event bus — but AKEP does not try to
standardize agent capabilities, identities, or negotiation.

### What models does AKEP work with?

All of them. AKEP lives at the **agent runtime boundary**, not inside
model weights. It works with Claude, GPT, Gemini, local Llama / Mistral,
and any agent framework that can receive an HTTP POST, verify HMAC, and
write to a queue: Claude Code, OpenAI Agents SDK, Google ADK, LangGraph,
AutoGen, CrewAI, or a custom loop.

### How do I notify an AI agent when a long-running tool finishes?

Emit an AKEP `tool.completed` event with:

- `subject.task_id` = the original tool-call id,
- `knowledge.kind` = `tool_result`,
- `routing.resume_policy` = `resume_if_waiting`.

The agent's runtime verifies the signature, stores the event, looks up
the paused task, and resumes the conversation from where it stopped.

### How do I send a human-in-the-loop approval event?

Two events, same subject/thread:

1. When the agent should pause, the agent runtime emits (or expects)
   `human.review_required` with a stable `routing.interrupt_id`.
2. When the human acts, your reviewer system emits `human.approved` or
   `human.rejected` with the same `interrupt_id`. The agent's graph
   resumes from that interrupt.

### Can AKEP deliver to a local desktop agent behind NAT?

Yes, two ways:

- **Development:** expose the local receiver via Cloudflare Tunnel,
  Hookdeck, ngrok, or Tailscale Funnel. See
  [`docs/quickstart.md`](quickstart.md).
- **Production:** use an outbound relay (SSE, WebSocket, or polling)
  so the desktop agent connects out, not in. The hosted relay API is on
  the v0.3 roadmap.

### What's the safety model?

A single hard rule, enforced at the protocol layer: **AKEP events carry
knowledge, never commands**. Receivers MUST:

- reject any payload that attempts to encode a direct command (the
  reference receivers reject any top-level `command` field),
- verify signatures *before* parsing JSON,
- never invoke an LLM or run arbitrary tools from inside the inbound
  HTTP request handler,
- treat `routing.resume_policy` as advice; local policy always wins.

### What signature algorithm does AKEP use?

`HMAC-SHA256` over `event_id + "." + webhook-timestamp + "." + raw_body`,
base64-encoded, prefixed `v1,`. Standard Webhooks compatible. Algorithm
agility (`v1a` for Ed25519, etc.) is on the roadmap.

### What does the wire envelope look like?

```json
{
  "spec": "akep.v1",
  "event_id": "evt_…",
  "event_type": "knowledge.acquired",
  "occurred_at": "2026-05-18T03:00:00Z",
  "source":    { "name": "sense2ai", "type": "marketplace" },
  "subject":   { "task_id": "task_123" },
  "knowledge": { "kind": "observation", "content_type": "application/json",
                 "summary": "…", "uri": "…", "content": { … } },
  "routing":   { "resume_policy": "resume_if_waiting" }
}
```

Full schema:
[`schemas/akep-event-v1.schema.json`](../schemas/akep-event-v1.schema.json).

### What event types exist?

`knowledge.acquired`, `tool.completed`, `tool.failed`,
`human.review_required`, `human.approved`, `human.rejected`,
`file.updated`, `memory.changed`, `message.received`. Vendor extensions
use reverse-DNS names (e.g. `ai.sense2.task.completed`) and SHOULD map
to a core type.

### What knowledge kinds exist?

`observation`, `tool_result`, `approval`, `document`, `artifact`,
`message`, `memory`.

### Can I send large media in an AKEP event?

You SHOULD send a `knowledge.uri` (signed URL, S3, Supabase, CAS) rather
than embedding bytes. Embedded `content` is for small structured
summaries.

### What happens on retry?

Producers re-send the same `event_id`. Receivers MUST treat the
`event_id` as an idempotency key and store the deduplication result so
double-deliveries are silent. The reference Python receiver enforces
this with a SQLite primary key.

### What happens if my agent was offline for hours?

Producers SHOULD expose two endpoints:

- `GET /akep/events?cursor=<cursor>` — replay since the last cursor.
- `POST /akep/events/{event_id}/ack` — acknowledge after local persistence.

The agent reconnects, walks the replay cursor, acks each event, and is
caught up. The exact cursor/ack contract is being firmed up in v0.2.

### How do I subscribe with filters?

```json
{
  "spec": "akep.v1",
  "sink": "agent.local.property-buyer",
  "event_types": ["knowledge.acquired", "tool.failed", "human.review_required"],
  "filters": { "source.name": "sense2ai",
               "knowledge.kind": ["observation", "tool_result", "approval"] },
  "delivery": { "type": "webhook",
                "url": "https://agent.example.com/akep/events" }
}
```

Receivers SHOULD reject events that don't match a known subscription.

### How does AKEP work with LangGraph / OpenAI Agents SDK / Google ADK?

Map:

- `subject.thread_id` → graph thread / agent session,
- `routing.interrupt_id` → pending interrupt id,
- `event_id` → idempotency key,
- `knowledge` → graph input or memory write.

Resume only when local graph state is *waiting* for that event. Full
mappings in [`docs/model-integrations.md`](model-integrations.md).

### Who uses AKEP today?

[Sense2.ai](https://sense2.ai) is the first production AKEP producer.
It's an AI sensory marketplace where agents request real-world context
(video, audio, photos) and humans fulfill the request; results come
back as signed AKEP `knowledge.acquired` events. See
[`docs/sense2ai-market.md`](sense2ai-market.md).

### Is AKEP a finalized standard?

No. AKEP v1 is a **public draft**. The envelope freezes only after
three independent implementations exist and a conformance test suite
passes. See [`docs/adoption-strategy.md`](adoption-strategy.md) and
[`../PROTOCOL-REVIEW.md`](../PROTOCOL-REVIEW.md).

### What license is AKEP under?

[Apache-2.0](../LICENSE).

### How do I contribute?

Open an issue or PR on GitHub. Live list of known protocol gaps:
[`../PROTOCOL-REVIEW.md`](../PROTOCOL-REVIEW.md). Adoption plan:
[`adoption-strategy.md`](adoption-strategy.md).

[stdwh]: https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md
