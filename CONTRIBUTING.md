# Contributing to AKEP

AKEP should stay small, boring, and interoperable.

Good contributions include:

- corrections to the event envelope
- new event examples
- receiver implementations in additional languages
- mappings to agent runtimes and async frameworks
- threat model improvements
- Sense2AI integration examples

Design rules:

- Prefer existing standards before inventing new wire behavior.
- Keep model-specific integration outside the core protocol.
- Do not add executable behavior to inbound events.
- Preserve `knowledge arrival` and `agent resume` as separate stages.
- Add schemas and examples with every protocol change.

