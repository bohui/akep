# Model and Runtime Integrations

AKEP is not a model capability. It is a runtime contract. Any model can benefit when its host runtime knows how to receive, store, and route asynchronous knowledge.

## MCP

MCP exposes tools, resources, and prompts to agents. AKEP should integrate by exposing the durable inbox as MCP resources and controlled actions as MCP tools.

Example resources:

```text
akep://events/recent
akep://events/{event_id}
akep://knowledge/{knowledge_id}
```

Example tools:

```text
akep_ack_event(event_id)
akep_replay_events(cursor)
akep_subscribe(filters, delivery)
```

Do not deliver live webhooks through MCP stdio. Store events first, then let MCP expose the inbox.

## Claude Code

Install the AKEP skill under:

```text
~/.claude/skills/akep/SKILL.md
<project>/.claude/skills/akep/SKILL.md
```

The skill teaches Claude to set up receivers, validate signatures, inspect inboxes, and map events to safe resume behavior.

## OpenClaw

Install the AKEP skill under:

```text
~/.openclaw/skills/akep/SKILL.md
<workspace>/skills/akep/SKILL.md
```

OpenClaw-compatible metadata should stay simple because OpenClaw skill parsing expects single-line frontmatter keys.

## OpenAI Agents SDK

Recommended adapter shape:

```text
AKEP receiver
  -> verify signature
  -> store inbox event
  -> map event subject to saved run/session/thread
  -> enqueue resume input
  -> call application runner outside the webhook request
```

The adapter should never call the model from the HTTP request handler.

## Google ADK / Gemini

Use AKEP at the event boundary and ADK/MCP at the tool boundary:

```text
AKEP event -> inbox -> ADK workflow state -> Gemini agent run
```

Expose inbox inspection through ADK tools or an MCP server when useful.

## LangGraph and Other Durable Runtimes

Map:

- `subject.thread_id` to graph thread/session id
- `routing.interrupt_id` to pending interrupt id
- `event_id` to idempotency key
- `knowledge` to graph input or memory update

Resume only when local graph state is waiting for that event.
