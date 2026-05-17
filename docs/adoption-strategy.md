# Adoption Strategy

AKEP should be accepted by agent runtimes before it is accepted by model vendors.

Models do not need to learn a new protocol. Agent hosts need a small, safe way to receive asynchronous knowledge and resume work. That makes AKEP a runtime boundary protocol, similar in spirit to how MCP sits at the tool/resource boundary.

## Thesis

The shortest path to broad adoption is:

1. Align the wire format with existing standards.
2. Keep the core envelope tiny.
3. Ship installable skills and examples for the tools developers already use.
4. Prove real demand through Sense2AI as the first async knowledge market.
5. Invite other producers to add adapters without changing their model stack.

## Why This Can Win

AKEP solves a visible gap:

- MCP standardizes how agents request tools and resources.
- Webhooks standardize server-to-server notifications.
- Agent frameworks manage runs, state, and tools.
- But there is no small shared convention for "verified external knowledge arrived; store it; maybe resume a paused agent."

AKEP fills only that gap.

## Make It Easy for Every Runtime

### Claude Code and Claude-style agents

Ship an AgentSkills-compatible skill. Claude Code documents skills as folders with `SKILL.md` and supporting files, and the same format is usable across multiple AI tools. AKEP should be installable as:

```bash
mkdir -p ~/.claude/skills
cp -R skills/akep ~/.claude/skills/akep
```

### OpenClaw

OpenClaw loads AgentSkills-compatible skill folders from workspace and user skill directories. AKEP should be installable as:

```bash
mkdir -p ~/.openclaw/skills
cp -R skills/akep ~/.openclaw/skills/akep
```

The public repo can later be published to ClawHub or any skill registry, but the protocol should not depend on a single registry.

### OpenAI Agents SDK

OpenAI webhooks already follow Standard Webhooks. AKEP should provide a helper that maps verified webhook events into an application queue that resumes an Agents SDK run only after local policy checks.

### Gemini and Google ADK

Google ADK supports MCP integration. AKEP should provide an adapter that exposes the inbox as MCP resources/tools while keeping event delivery as AKEP.

### Local and open-source agents

For local agents, AKEP should be just:

- a JSON Schema
- a signature verifier
- a SQLite inbox
- a resume callback

No cloud dependency should be required.

## Governance Proposal

Start pragmatic:

1. Publish this repo under Apache-2.0.
2. Use GitHub issues for design discussion.
3. Mark `docs/protocol.md` as draft until at least three independent implementations exist.
4. Add a conformance test suite before declaring v1.0.
5. If adoption grows, move the protocol to a neutral foundation or multi-maintainer org.

## Adoption Milestones

| Milestone | Acceptance signal |
| --- | --- |
| Draft repo | Protocol, schemas, examples, skill published. |
| Sense2AI adapter | First real producer emits AKEP events. |
| Two receiver SDKs | Python and Node receivers pass conformance tests. |
| Agent skill distribution | Claude/OpenClaw/Codex-style agents can install the skill. |
| MCP bridge | AKEP inbox can be surfaced as MCP resources/tools. |
| Framework adapters | OpenAI Agents SDK, Google ADK, LangGraph, and local agents can consume events. |
| Neutral governance | Non-Sense2AI producers and receivers contribute changes. |

## Messaging

AKEP should be described as:

> The missing async knowledge layer for agents.

More precise:

> MCP is how agents ask for context. AKEP is how context wakes agents up safely after it arrives.

Avoid claiming AKEP is an agent-to-agent replacement, a tool protocol, or a workflow engine. Those claims would create resistance from existing ecosystems.

## Sense2AI as the First Market

Sense2AI makes AKEP concrete:

1. An agent posts a task asking humans to capture real-world context.
2. A human fulfills the task.
3. Sense2AI produces structured knowledge and a defaced media artifact.
4. AKEP delivers `knowledge.acquired`.
5. The receiving agent verifies, stores, normalizes, and resumes the waiting task.

This is a stronger story than a toy webhook demo because it proves the core thesis: agents need asynchronous knowledge from the real world.

## Non-Goals

- Do not standardize model prompts.
- Do not require a specific vector store or memory database.
- Do not require cloud relay for local development.
- Do not let event producers command agents.
- Do not compete with MCP for tool execution.

