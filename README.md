# AKEP — Async Knowledge Event Protocol for AI Agents

**The open protocol for sending asynchronous events to AI agents.** AKEP is
the missing inbox layer for AI agent webhooks: a tiny JSON envelope plus
[Standard Webhooks][stdwh] signatures that tells a Claude, GPT, Gemini, or
local agent that new knowledge has arrived — safely, with replay and
idempotency, while the agent was offline, paused, or waiting for a human.

[![Spec: draft v1](https://img.shields.io/badge/spec-akep.v1%20draft-blue)](docs/protocol.md)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)
[![Standard Webhooks](https://img.shields.io/badge/transport-Standard%20Webhooks-orange)][stdwh]
[![MCP complementary](https://img.shields.io/badge/MCP-complementary-purple)](https://modelcontextprotocol.io)

> **One-line definition.** AKEP (Async Knowledge Event Protocol) is an open
> JSON-over-HTTP protocol that delivers signed, idempotent, replayable
> *knowledge events* to AI agents. MCP lets agents *ask* for context. AKEP
> lets the outside world *tell* agents that context is ready.

---

## Table of contents

- [What problem does AKEP solve?](#what-problem-does-akep-solve)
- [When should I use AKEP?](#when-should-i-use-akep)
- [60-second quickstart](#60-second-quickstart)
- [Send your first event with curl](#send-your-first-event-with-curl)
- [How AKEP compares to webhooks, MCP, A2A, and CloudEvents](#how-akep-compares-to-webhooks-mcp-a2a-and-cloudevents)
- [Event envelope at a glance](#event-envelope-at-a-glance)
- [Use cases](#use-cases)
- [Reference implementations](#reference-implementations)
- [Install the AKEP skill](#install-the-akep-skill-claude-code-openclaw)
- [FAQ](#faq)
- [Roadmap](#roadmap)
- [Contributing & governance](#contributing--governance)

---

## What problem does AKEP solve?

If you are building an AI agent on Claude, GPT, Gemini, LangGraph, the
OpenAI Agents SDK, Google ADK, or a local runtime, you have probably hit
this wall:

- You kick off a long-running tool. The tool finishes 30 minutes later.
  **How do you wake the agent back up?**
- You send a task to a human reviewer. They approve it tomorrow morning.
  **How does the paused agent run resume?**
- A marketplace, sensor, or background job produces structured knowledge.
  **How does that knowledge reach the right agent, signed and deduplicated?**
- Your laptop closed its tunnel. The agent missed three events.
  **How do you replay them safely?**

Plain webhooks aren't enough: local agents sleep, tunnel URLs expire,
handlers must not invoke an LLM directly from an inbound HTTP request,
and there is no standard envelope for *agent-relevant* events. MCP
solves the *outbound* side (agent → tool/resource). AKEP solves the
*inbound* side (world → agent).

**AKEP is the async inbox for AI agents:** durable, signed, idempotent,
replayable, with an explicit safety boundary — events deliver
**knowledge, never commands**.

```text
                       AKEP closes this loop
                              │
   agent  ──MCP──▶  tools / resources / prompts
     ▲
     │ AKEP event (signed, durable, idempotent)
     │
   producer  (sense2.ai, your backend, a human reviewer,
              a long-running tool, a sensor, a queue, …)
```

---

## When should I use AKEP?

Use AKEP when any of the following is true.

- You need to **notify an AI agent that a long-running tool finished**.
- You need to **resume a paused agent after a human approval** (HITL).
- You're building **agent-to-agent (A2A) events** and want a tiny, safe
  envelope rather than reinventing webhooks.
- You're shipping a **marketplace, observability stream, or sensor feed**
  that AI agents should consume.
- You need **replay, idempotency, and signature verification** for events
  going *to* an agent, not from one.
- You want a webhook story that works for **local desktop agents** behind
  NAT, not just cloud-to-cloud.

You probably **don't** need AKEP if you only do request/response between
your code and a model. Use the model SDK directly.

---

## 60-second quickstart

Clone, run the receiver, send a signed test event, watch it land in a
local SQLite inbox. No cloud, no signup, no dependencies beyond Python 3.

```bash
git clone https://github.com/bohui/akep.git
cd akep
export AKEP_WEBHOOK_SECRET="dev-secret"

# Terminal A — start a verified, idempotent AKEP receiver on :8787
python3 examples/python/receiver.py

# Terminal B — sign and send the Sense2AI example event
export AKEP_WEBHOOK_SECRET="dev-secret"
python3 examples/python/sign_event.py \
  --url http://127.0.0.1:8787/akep/events \
  --event examples/events/sense2ai-task-completed.json

# Inspect the durable inbox
sqlite3 .akep/inbox.db "select event_id, event_type, source_name from events;"
```

Or run the full demo in a single command:

```bash
make demo            # starts receiver, sends a signed event, prints the inbox row
```

Prefer Node? See [`examples/node/`](examples/node/). Want curl? See below.

---

## Send your first event with curl

This is the AKEP "hello world" — exactly the bytes that will travel
between any producer and any receiver that speaks the protocol.

```bash
SECRET="dev-secret"
EVENT_ID="evt_demo_01"
TS=$(date +%s)
BODY='{"spec":"akep.v1","event_id":"evt_demo_01","event_type":"knowledge.acquired","occurred_at":"2026-05-18T03:00:00Z","source":{"name":"demo","type":"system"},"subject":{"task_id":"t_1"},"knowledge":{"kind":"observation","content_type":"text/plain","summary":"hello AKEP"},"routing":{"resume_policy":"append_only"}}'

SIG="v1,$(printf '%s' "${EVENT_ID}.${TS}.${BODY}" \
  | openssl dgst -sha256 -hmac "$SECRET" -binary \
  | base64)"

curl -sS -X POST http://127.0.0.1:8787/akep/events \
  -H "content-type: application/json" \
  -H "webhook-id: ${EVENT_ID}" \
  -H "webhook-timestamp: ${TS}" \
  -H "webhook-signature: ${SIG}" \
  --data "${BODY}"
# → 202 {"accepted":true,"duplicate":false}
```

That's the entire wire protocol. If your producer can do this, it speaks
AKEP.

---

## How AKEP compares to webhooks, MCP, A2A, and CloudEvents

AKEP is intentionally small and slots **next to** the protocols you
probably already use — not on top of them.

| Concern                                     | Plain webhooks | MCP           | Agent-to-Agent (A2A) | CloudEvents | **AKEP**            |
| ------------------------------------------- | -------------- | ------------- | -------------------- | ----------- | ------------------- |
| Direction                                   | server → server| agent → tool  | agent ↔ agent        | any         | **world → agent**   |
| Signed delivery (Standard Webhooks)         | sometimes      | n/a           | varies               | optional    | **required**        |
| Idempotency / dedup by `event_id`           | DIY            | n/a           | varies               | yes (`id`)  | **required**        |
| Replay / inbox cursor                       | DIY            | n/a           | DIY                  | DIY         | **specified**       |
| "Events carry knowledge, never commands"    | no             | n/a           | no                   | no          | **yes**             |
| Resume policy for paused agents             | n/a            | n/a           | DIY                  | n/a         | **first-class**     |
| Works for local desktop agents              | hard           | yes           | varies               | yes         | **yes (outbound relay)** |
| Model-neutral                               | yes            | yes           | partially            | yes         | **yes**             |
| Maps to CloudEvents                         | yes            | n/a           | varies               | —           | **yes (documented)**|

**Plain English:** MCP is how agents *pull* tools. AKEP is how the world
*pushes* knowledge into agents. CloudEvents is a generic envelope —
AKEP is a CloudEvents-compatible envelope plus the agent-specific bits
(resume policy, subject routing, durable inbox, safety boundary).

---

## Event envelope at a glance

A complete AKEP event is one signed JSON object. Full schema:
[`schemas/akep-event-v1.schema.json`](schemas/akep-event-v1.schema.json).

```json
{
  "spec": "akep.v1",
  "event_id": "evt_01HX5S8ZQ9J6W9E5W4H8A2K7D3",
  "event_type": "knowledge.acquired",
  "occurred_at": "2026-05-17T03:00:00Z",
  "source":  { "name": "sense2ai", "type": "marketplace" },
  "subject": { "task_id": "task_123", "thread_id": "thread_456" },
  "knowledge": {
    "kind": "observation",
    "content_type": "application/json",
    "uri": "https://sense2.ai/artifacts/sub_456",
    "summary": "Property inspection video is ready. Condition good.",
    "confidence": 0.82,
    "content": { "overall_condition": "good", "noise": "low" }
  },
  "routing": {
    "resume_policy": "resume_if_waiting",
    "priority": "normal",
    "interrupt_id": "int_waiting_for_property_video"
  }
}
```

Core event types: `knowledge.acquired`, `tool.completed`, `tool.failed`,
`human.review_required`, `human.approved`, `human.rejected`,
`file.updated`, `memory.changed`, `message.received`.

Resume policies: `never`, `append_only`, `resume_if_waiting`,
`resume_immediately`. **Local policy always wins** — `routing` is
advice, not authority.

---

## Use cases

### Long-running tool completed

A Claude or GPT agent calls a 20-minute video processing tool. The tool
finishes, posts an AKEP `tool.completed` event to the agent's inbox, and
the agent resumes the original conversation with the result.

### Human-in-the-loop approval

An agent drafts a refund. A human reviewer approves it 8 hours later.
The reviewer's system posts `human.approved` with `interrupt_id`. The
agent's LangGraph thread resumes from the paused interrupt.

### Real-world context via Sense2.ai

[Sense2.ai](https://sense2.ai) is the first AKEP producer in
production: an AI sensory marketplace where agents request real-world
context (video, audio, photos) and humans fulfill the request. When the
human's submission is processed and defaced, Sense2.ai emits a signed
AKEP `knowledge.acquired` event, and the agent gets structured
observation data plus a privacy-safe artifact URL. See
[`docs/sense2ai-market.md`](docs/sense2ai-market.md).

### Marketplace, sensor, queue, file watcher

Any producer that can sign a Standard Webhooks-compatible request can
emit AKEP. Map your domain event to `event_type` and `knowledge.kind`;
ship.

### Agent-to-agent (A2A) handoff

Agent A finishes a research phase, signs a `knowledge.acquired` event,
posts it to Agent B's AKEP inbox. Agent B verifies, stores, and decides
locally whether to resume. No shared runtime, no shared vendor.

---

## Reference implementations

- **Python receiver** (zero dependencies, SQLite inbox):
  [`examples/python/receiver.py`](examples/python/receiver.py)
- **Python signer / sender** (zero dependencies):
  [`examples/python/sign_event.py`](examples/python/sign_event.py)
- **Node receiver** (Express, JSONL inbox):
  [`examples/node/receiver.mjs`](examples/node/receiver.mjs)
- **Node signer / sender** (built-in `crypto`):
  [`examples/node/send-event.mjs`](examples/node/send-event.mjs)
- **Example event** (Sense2.ai task completed):
  [`examples/events/sense2ai-task-completed.json`](examples/events/sense2ai-task-completed.json)
- **Example subscription**:
  [`examples/events/subscription.json`](examples/events/subscription.json)

Run `make validate` to lint the schemas, examples, and reference
implementations.

---

## Install the AKEP skill (Claude Code, OpenClaw)

The repo ships an [AgentSkills][skills]-compatible skill so any
skill-aware agent can set up receivers, verify signatures, inspect
inboxes, and apply resume policies on request.

```bash
# Claude Code (personal)
mkdir -p ~/.claude/skills
cp -R skills/akep ~/.claude/skills/akep

# Claude Code (project)
mkdir -p .claude/skills
cp -R skills/akep .claude/skills/akep

# OpenClaw
mkdir -p ~/.openclaw/skills
cp -R skills/akep ~/.openclaw/skills/akep
```

Then ask the agent:

> *"Set up a Sense2AI AKEP receiver on port 8787, verify Standard
> Webhooks signatures, and tell me if the last event should resume my
> waiting task."*

See [`docs/skill-installation.md`](docs/skill-installation.md).

---

## FAQ

### What is AKEP?

AKEP (Async Knowledge Event Protocol) is an open, model-neutral protocol
that delivers signed, idempotent, replayable knowledge events to AI
agents over Standard Webhooks-compatible HTTP. It's the inbound
counterpart to MCP.

### Is AKEP a replacement for MCP?

**No.** MCP and AKEP are complementary. MCP is how agents *request*
tools, resources, and prompts. AKEP is how the world *delivers*
asynchronous knowledge into agents. You will usually run both.

### How is AKEP different from regular webhooks?

Regular webhooks are a transport. AKEP is a transport-plus-semantics: a
defined envelope, an event-type vocabulary, a resume-policy model, a
durable inbox contract, and an explicit safety boundary (no commands in
event bodies). AKEP wire transport is Standard
Webhooks-compatible, so existing infra (Hookdeck, Svix, Inngest, custom
HMAC verifiers) keeps working.

### Does AKEP work with Claude, GPT, Gemini, and local models?

Yes. AKEP lives at the **agent runtime boundary**, not inside model
weights. Any runtime that can receive an HTTP POST, verify HMAC, and
write to a queue can adopt AKEP — Claude Code, OpenAI Agents SDK,
Google ADK, LangGraph, AutoGen, CrewAI, or your own loop.

### How do I notify an AI agent when a long-running tool finishes?

Emit an AKEP `tool.completed` event. Include `subject.task_id` so the
agent's resume queue can match the original tool call, and set
`routing.resume_policy` to `resume_if_waiting`. The agent's runtime
verifies the signature, stores the event, and resumes the paused run.

### How do I send a human-in-the-loop (HITL) approval event?

Emit `human.review_required` when the agent should pause, and emit
`human.approved` / `human.rejected` when the human acts. Use the same
`subject.thread_id` and a stable `routing.interrupt_id` so the agent's
graph resumes at the right node.

### Can AKEP deliver to a local agent behind NAT?

Yes, two ways. Either expose the local receiver via a tunnel
(Cloudflare Tunnel, Hookdeck, ngrok, Tailscale Funnel) for development,
or use an outbound relay (SSE, WebSocket, polling) in production.
Specifying the relay API is on the v0.3 roadmap.

### What's the safety story?

AKEP enforces a hard rule at the protocol layer: **events carry
knowledge, never commands**. Receivers MUST reject any payload that
attempts to encode a direct command, MUST verify signatures before
parsing, and MUST NOT invoke an LLM or run arbitrary tools from inside
the inbound HTTP request. Local policy decides whether a verified event
may resume a paused task.

### Is AKEP a standard yet?

AKEP v1 is a **public draft** intended for discussion and early
adoption. We track adoption milestones in
[`docs/adoption-strategy.md`](docs/adoption-strategy.md) and freeze
the envelope only after at least three independent implementations and
a conformance test suite.

### What's the relationship to Sense2.ai?

[Sense2.ai](https://sense2.ai) is an AI sensory marketplace and the
first production AKEP producer. It uses AKEP to deliver
defaced video and structured observation data back to agents that
posted tasks. See
[`docs/sense2ai-market.md`](docs/sense2ai-market.md).

### How do I contribute?

Open an issue or PR. Apache-2.0 licensed. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`PROTOCOL-REVIEW.md`](PROTOCOL-REVIEW.md) for the live list of known
gaps.

---

## Repository map

| Path                                                                                             | What it is                                              |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| [`docs/protocol.md`](docs/protocol.md)                                                           | Normative AKEP v1 draft                                 |
| [`docs/adoption-strategy.md`](docs/adoption-strategy.md)                                         | How AKEP gets adopted by agent runtimes                 |
| [`docs/model-integrations.md`](docs/model-integrations.md)                                       | Claude, OpenAI, Gemini, MCP, LangGraph mappings         |
| [`docs/sense2ai-market.md`](docs/sense2ai-market.md)                                             | Sense2AI as the first AKEP market                       |
| [`docs/skill-installation.md`](docs/skill-installation.md)                                       | Install the AKEP skill in Claude Code / OpenClaw        |
| [`schemas/akep-event-v1.schema.json`](schemas/akep-event-v1.schema.json)                         | Event envelope JSON Schema (Draft 2020-12)              |
| [`schemas/akep-subscription-v1.schema.json`](schemas/akep-subscription-v1.schema.json)           | Subscription JSON Schema                                |
| [`examples/python/`](examples/python)                                                            | Zero-dep Python receiver + signer                       |
| [`examples/node/`](examples/node)                                                                | Express receiver + sender                               |
| [`examples/events/`](examples/events)                                                            | Example event + subscription                            |
| [`skills/akep/`](skills/akep)                                                                    | Installable AgentSkills-compatible skill                |
| [`PROTOCOL-REVIEW.md`](PROTOCOL-REVIEW.md)                                                       | Live review of known protocol flaws and fixes           |

---

## Roadmap

See [`ROADMAP.md`](ROADMAP.md). Highlights:

- **v0.1 (current draft):** envelope, schemas, Python + Node reference,
  installable skill, Sense2.ai first producer.
- **v0.2 — Interop:** conformance tests; Go / typed-TS packages; MCP
  resource/tool adapter; OpenAI Agents SDK, Google ADK, LangGraph
  adapters.
- **v0.3 — Relay:** hosted-relay API, SSE/WebSocket/polling delivery,
  cursor-based replay and ack semantics.
- **v1.0:** envelope freeze, conformance suite, neutral governance.

---

## Contributing & governance

AKEP is Apache-2.0 licensed and developed in the open. Issues and PRs
welcome. We mark the protocol as draft until at least three independent
implementations exist and a conformance test suite passes. See
[`docs/adoption-strategy.md`](docs/adoption-strategy.md) for the
governance plan and
[`PROTOCOL-REVIEW.md`](PROTOCOL-REVIEW.md) for the open-issue list.

---

## References

- [Standard Webhooks specification][stdwh]
- [OpenAI Webhooks](https://developers.openai.com/api/docs/guides/webhooks)
- [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills)
- [OpenClaw skills](https://docs.openclaw.ai/skills)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io)
- [Google ADK + MCP](https://adk.dev/mcp/)
- [CNCF CloudEvents](https://cloudevents.io)

---

**Keywords:** async events for AI agents, webhook for AI agents, MCP
async events, agent inbox protocol, AI agent webhook standard,
human-in-the-loop webhook, long-running tool callback, agent-to-agent
events, Claude webhooks, GPT agent webhooks, Gemini agent events,
LangGraph resume, Sense2.ai webhook, async knowledge protocol, agent
resume policy, Standard Webhooks for AI.

[stdwh]: https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md
[skills]: https://docs.claude.com/en/docs/claude-code/skills
