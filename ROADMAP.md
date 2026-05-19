# AKEP Roadmap

## v0.1 Draft

- Publish AKEP event envelope and subscription schema.
- Ship Python and Node receiver examples.
- Ship AgentSkills-compatible `akep` skill.
- Document Sense2AI as the first knowledge-publisher use case.

## v0.2 Interop

- Add conformance tests for signing, replay, and schema validation.
- Add Go and TypeScript typed packages.
- Add MCP resource/tool adapter examples.
- Add OpenAI Agents SDK, Google ADK, LangGraph, and local runtime adapters.
- Publish OpenAPI and `.well-known/akep.json` discovery.
- Freeze replay, wait, ack, and task-state profile semantics.
- Document the knowledge-publisher result profile.

## v0.3 Relay

- Ship hosted relay reference implementation for production users who should not expose local ports.
- Add SSE, WebSocket, polling, and long-poll delivery examples.
- Add relay conformance tests for cursor, ack, and retention behavior.

## v1.0

- Freeze the core envelope.
- Publish a compatibility test suite.
- Move governance to a neutral org if adoption justifies it.
