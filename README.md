# AKEP: Async Knowledge Event Protocol

AKEP is an open protocol for delivering asynchronous knowledge to AI agents.

MCP lets an agent ask for tools, resources, and context. AKEP lets the outside world tell an agent that knowledge has arrived while the agent was offline, paused, waiting for a human, or running a long task.

The first reference use case is [sense2.ai](https://sense2.ai): an AI sensory marketplace where agents can request real-world context from humans and receive signed completion events when the knowledge is ready.

## Why AKEP

Modern agents need more than request/response tools. They wait for:

- human review decisions
- long-running tools
- marketplace fulfillment
- sensor or field observations
- file, memory, and artifact changes
- background model runs and batch jobs

Webhook-only integrations are not enough. Local agents sleep, laptops move, tunnel URLs expire, and handlers should not run an LLM directly from an inbound HTTP request. AKEP defines a durable event-inbox model with signed delivery, replay, acknowledgement, subscription filters, and controlled resume policy.

```text
knowledge source
  -> signed delivery adapter
  -> durable agent inbox
  -> normalizer
  -> memory / task state
  -> local resume policy
```

## Design Position

AKEP is intentionally small:

- **Model neutral**: it works with Claude, OpenAI, Gemini, local models, and agent frameworks because it lives at the agent runtime boundary, not inside model weights.
- **MCP complementary**: MCP is for tool/resource access; AKEP is for asynchronous external events and missed-event recovery.
- **Standard Webhooks compatible**: webhook transport uses `webhook-id`, `webhook-timestamp`, and `webhook-signature` headers.
- **Skill installable**: the repo ships an AgentSkills-compatible `SKILL.md` for Claude Code, OpenClaw, Codex-style, and other skill-aware agents.
- **Safety first**: inbound events carry knowledge, not commands. Local policy decides whether an event can resume work.

## Repository Map

- [docs/protocol.md](docs/protocol.md) - normative AKEP v1 draft
- [docs/adoption-strategy.md](docs/adoption-strategy.md) - proposal to make AKEP broadly accepted by agent runtimes
- [docs/sense2ai-market.md](docs/sense2ai-market.md) - Sense2AI as the first AKEP market
- [docs/model-integrations.md](docs/model-integrations.md) - mapping to Claude, OpenAI, Gemini, MCP, and local agents
- [docs/skill-installation.md](docs/skill-installation.md) - install the AKEP skill in Claude Code or OpenClaw
- [schemas/akep-event-v1.schema.json](schemas/akep-event-v1.schema.json) - event envelope schema
- [schemas/akep-subscription-v1.schema.json](schemas/akep-subscription-v1.schema.json) - subscription schema
- [examples/events/sense2ai-task-completed.json](examples/events/sense2ai-task-completed.json) - example event
- [examples/python](examples/python) - dependency-light receiver and signer
- [examples/node](examples/node) - Express receiver and sender
- [skills/akep/SKILL.md](skills/akep/SKILL.md) - installable AKEP agent skill

## Quick Start

Run a local Python receiver:

```bash
cd /Users/victor/vh_work/akep
export AKEP_WEBHOOK_SECRET="dev-secret"
python3 examples/python/receiver.py
```

Send the Sense2AI example event:

```bash
export AKEP_WEBHOOK_SECRET="dev-secret"
python3 examples/python/sign_event.py \
  --url http://127.0.0.1:8787/akep/events \
  --event examples/events/sense2ai-task-completed.json
```

Validate repo examples and schema JSON:

```bash
make validate
```

## Current Draft

AKEP v1 is a draft intended for public discussion. The right path is not to ask every model provider to hardcode AKEP. The right path is to make AKEP easy for every agent runtime to adopt as a tiny boundary protocol:

1. JSON Schema + Standard Webhooks transport.
2. Installable skills for Claude Code, OpenClaw, Codex-style agents, and other AgentSkills hosts.
3. Reference receivers in Python and Node.
4. Adapters for MCP clients, OpenAI Agents SDK, Google ADK, LangGraph, and local agent runtimes.
5. Sense2AI as the first production market proving async knowledge fulfillment.

## References

- [Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks/blob/main/spec/standard-webhooks.md)
- [OpenAI Webhooks](https://developers.openai.com/api/docs/guides/webhooks)
- [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills)
- [OpenClaw skills](https://docs.openclaw.ai/skills)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Google ADK MCP integration](https://adk.dev/mcp/)
