# AKEP v1 Draft - Repository Review

Reviewer: whole-repo pass, May 2026.
Scope: protocol docs, schemas, examples, reference receivers, validation, and the bundled `akep` skill.

## Summary

AKEP is now consistently framed as an async knowledge event protocol, not a general agent-to-agent replacement. The repo focuses on a small signed event envelope, durable inbox semantics, replay/ack, relay support for local agents, and Sense2.ai as the first knowledge-publisher use case.

The earlier high-risk gaps have been addressed in the draft:

- `subject` is required in prose and schema, and empty subjects are invalid.
- `source.producer_id` plus subscription security constraints give producers a routable identity.
- `source.type = "publisher"` replaces the older overloaded source category.
- Standard Webhooks signing now documents key ids, multiple signatures during rotation, and algorithm tags.
- Replay, wait, ack, task-state, relay, discovery, OpenAPI, and AsyncAPI surfaces are documented.
- Python and Node receivers verify signatures, enforce subscription filters, reject command payloads, and preserve `event_id` idempotency.
- The bundled skill and protocol summary align with the current docs.

## Remaining Work Before v1.0

- Add CI that installs `jsonschema` and runs full schema conformance on every PR.
- Add receiver-level tests for duplicate delivery, stale timestamps, subscription mismatch, replay cursor paging, ack idempotency, and long-poll timeout.
- Add a Sense2.ai legacy-webhook adapter if production Sense2.ai still emits non-AKEP headers during migration.
- Add typed client packages only after the HTTP and schema surfaces settle.
- Obtain at least three independent implementations before freezing the envelope.

## Protocol Positioning

Recommended positioning:

> MCP is how agents ask for context. AKEP is how context wakes agents up safely after it arrives.

Avoid claiming AKEP replaces A2A, workflow engines, MCP, or generic webhooks. AKEP should stay deliberately narrow: signed, idempotent, replayable knowledge events for agent runtimes.
