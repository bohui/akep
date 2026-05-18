# AKEP v1 Draft — Protocol Review

A close read of `docs/protocol.md`, both JSON Schemas, the Python and Node
reference implementations, the `akep` skill, and the Sense2AI mapping. Findings
are grouped by severity, with concrete fixes. The goal is twofold: make the
protocol harder to misuse, and make it dramatically easier to adopt.

Reviewer: AKEP-external read, May 2026.
Scope: AKEP repo only; sense2.ai referenced as the first producer.

---

## TL;DR

AKEP is on the right track — small envelope, clear safety boundary
("knowledge in, never commands"), Standard Webhooks transport, model-neutral.
It has eight blocking issues before a v1.0 freeze and roughly a dozen
usability gaps that explain why nobody beyond sense2.ai will integrate today.

Top blockers:

1. **Schema/spec disagreement on `subject`** (schema requires it, prose says SHOULD).
2. **`subject` accepts `{}`** — empty subject defeats routing/dedup.
3. **No `kid` / key rotation** in Standard Webhooks signatures.
4. **`v1,` signature prefix is undefined** (no algorithm registry, no agility).
5. **`spec: "akep.v1"` is a `const`** — locks out v1.1/v2 forever.
6. **The reference producer (sense2.ai) does not emit AKEP-compliant headers** — different header names, hex vs base64, no `event_id` in the signed payload.
7. **No ack/replay/cursor contract** — both are mentioned in prose, neither is specified.
8. **No producer authentication or tenant isolation** beyond a shared HMAC secret.

Top usability gaps:

- No OpenAPI / AsyncAPI definition; no client codegen path.
- No `.well-known/akep.json` for discovery (web crawlers and agents can't find AKEP services).
- No one-command quickstart (the receiver, the signer, and a public tunnel are three separate steps).
- Reference receiver doesn't enforce subscription filters, although the protocol says receivers MUST reject unknown subjects.
- No CloudEvents alignment, despite CloudEvents being the existing prior art every cloud already speaks.

Detailed findings follow.

---

## 1. Blocking issues (fix before v1.0)

### 1.1 Schema/spec disagreement on required fields  — severity: high

`docs/protocol.md §3` says `subject` **SHOULD** identify the task/thread/agent.
`schemas/akep-event-v1.schema.json` lists `subject` in `required`. The
schema also requires `routing`, but the prose says receivers **MAY ignore**
routing — implying it should be optional.

**Fix:** decide once. Recommendation: keep both required, but tighten the
schema so the required-ness is meaningful (see 1.2). Update the prose to
match the schema and add a "Conformance" section that distinguishes
producer requirements from receiver requirements.

### 1.2 `subject: {}` is a valid event  — severity: high

The `subject` schema lists five optional typed properties (`task_id`,
`thread_id`, `agent_id`, `user_id`, `artifact_id`) plus
`additionalProperties` of scalar/null. There is no `minProperties` or
`anyOf` constraint, so `"subject": {}` validates. That makes routing,
dedup, and `resume_if_waiting` meaningless.

**Fix:**

```json
"subject": {
  "type": "object",
  "minProperties": 1,
  "additionalProperties": { "type": ["string", "number", "boolean", "null"] },
  "properties": { ... },
  "anyOf": [
    { "required": ["task_id"] },
    { "required": ["thread_id"] },
    { "required": ["agent_id"] },
    { "required": ["user_id"] },
    { "required": ["artifact_id"] }
  ]
}
```

### 1.3 No key id / no key rotation  — severity: high

Standard Webhooks supports multiple active signatures in one header
(`webhook-signature: v1,a v1,b v2,c`) precisely so producers can rotate
secrets without downtime. AKEP says nothing about this. Without a `kid` or
key-id mechanism, rotating a leaked secret means a flag day for every
subscriber.

**Fix:** specify that producers MAY send multiple signature pairs in the
same header, that receivers MUST accept any one valid pair, and that
producers SHOULD include a key id in a separate header
(`webhook-signature-key-id: 2026-05`) or embed it in the signature prefix
(`v1k,2026-05,<sig>`). Document the rotation procedure.

### 1.4 Algorithm agility — what does `v1,` mean?  — severity: high

The signature is prefixed `v1,` but the spec doesn't define what `v1`
means. Today it's HMAC-SHA256/base64. Tomorrow it might need Ed25519 for
asymmetric verification, or HMAC-SHA512 for FIPS environments. There is no
registry, no negotiation, no path forward.

**Fix:** define an algorithm registry in `docs/signatures.md`:

| Tag    | Algorithm     | Encoding |
| ------ | ------------- | -------- |
| `v1`   | HMAC-SHA256   | base64   |
| `v1a`  | Ed25519       | base64   |
| `v2`   | reserved      | —        |

Receivers MUST reject unknown tags; producers MAY send multiple tags.

### 1.5 `spec: "akep.v1"` is a `const`  — severity: high

```json
"spec": { "const": "akep.v1" }
```

A receiver that strictly validates this schema will refuse `akep.v1.1` or
`akep.v2`. The intent ("this is AKEP v1, exactly") is correct, but the
expression in the schema makes forward compatibility impossible.

**Fix:** keep the const for v1.0, but publish a `vNext` discovery rule:
receivers SHOULD accept any `akep.vMAJOR.MINOR` whose MAJOR matches a
supported version. Use a regex `pattern` instead of `const`, e.g.
`^akep\\.v1(\\.[0-9]+)?$`.

### 1.6 The reference producer doesn't speak AKEP  — severity: high

sense2.ai's current outbound webhooks (per `sense2ai/README.md`) use:

```
X-Sense2AI-Timestamp: <unix>
X-Sense2AI-Signature: t=<ts>,v1=<hex>
HMAC body = ts + "." + raw_body          # no event_id; hex; non-standard headers
```

AKEP says:

```
webhook-id: <event_id>
webhook-timestamp: <unix>
webhook-signature: v1,<base64>
HMAC body = event_id + "." + timestamp + "." + raw_body
```

These are **incompatible**. AKEP claims sense2.ai as its first producer
but sense2.ai does not actually emit AKEP. This is the single biggest
credibility risk for the repo: anyone who reads both repositories will
notice within ten minutes.

**Fix (in priority order):**

1. Make sense2.ai emit AKEP-compliant Standard Webhooks headers
   (additionally; keep the old headers for a deprecation window).
2. Ship a sense2.ai → AKEP adapter in `examples/adapters/sense2ai.py` for
   subscribers stuck on the old format.
3. Update `docs/sense2ai-market.md` to be honest about the current state
   and the migration path.

### 1.7 Ack and replay contracts are advertised but not specified  — severity: high

`protocol.md §9` says:

```http
GET /akep/events?cursor=<cursor>
POST /akep/events/{event_id}/ack
```

…and stops. What's the cursor format? Opaque string? Monotonic? Per-subscription? What does ack do — mark processed, mark received, both? What's the response shape? What about partial replay (since timestamp, since event id, since cursor)? What happens to events that were never acked — do they replay forever?

**Fix:** add `docs/replay-and-ack.md` with:

- cursor is opaque to clients, must round-trip safely
- `GET /akep/events?cursor=...&limit=...&since=...` response shape: `{ events: [...], next_cursor, has_more }`
- `POST /akep/events/{id}/ack { received_at, processed_at?, status: "stored"|"applied"|"rejected", reason? }`
- producers MUST retain unacked events for at least 7 days
- ack is idempotent
- replay returns events in `occurred_at` order, ties broken by `event_id`

### 1.8 No producer auth, no tenant isolation  — severity: medium-to-high

Anyone with the shared HMAC secret can claim to be `source.name:
"sense2ai"`. There is no producer identity beyond the secret, and no way
to express "this subscription only accepts events from producer X".

**Fix:**

- Make `source.name` plus a producer key fingerprint part of the
  subscription contract.
- Recommend per-(producer, subscriber) secrets, not per-subscriber.
- Optionally specify a `producer_id` field with a registered prefix
  convention (`prod_sense2ai_…`).

---

## 2. Schema and envelope tightening

### 2.1 `extensions` has no namespacing rule

`extensions: { additionalProperties: true }` invites collisions. CloudEvents
solved this years ago: extensions are flat, lowercase, and conventionally
namespaced. AKEP should require reverse-DNS or vendor-prefixed keys,
e.g. `extensions["ai.sense2.task_priority"]`.

### 2.2 `knowledge.hash` algorithm is undefined

`knowledge.hash` is a free string up to 256 chars. Is it sha256-hex?
sha256-base64? multihash? Anyone consuming it has to guess.

**Fix:** require the multihash-style prefix:
`sha256:<hex>` or `sha256:<base64>`. Pick one encoding and stick to it.

### 2.3 `knowledge.uri` lifetime is undefined

For real workloads, `knowledge.uri` will frequently be a signed Supabase
or S3 URL with a 1-hour TTL. Replay 24 hours later → 403. The protocol
must either:

- require `knowledge.uri` to be valid for at least the producer's
  replay window, or
- require `knowledge.uri_expires_at` so receivers know when to re-fetch,
  or
- recommend content-addressed URIs (`cas://sha256/…`).

### 2.4 `event_id` regex contradicts the signing rule

The signing rule joins `event_id + "." + timestamp + "." + raw_body`. The
reference receiver explicitly rejects `event_id` containing `.`. The
schema enforces `^[A-Za-z0-9_:-]+$` (no dots). Good — but the **protocol
prose** doesn't state that no dot is allowed in `event_id` or `timestamp`.
Move that rule from "implementation detail of receiver.py" to the spec.

### 2.5 `occurred_at` skew

`webhook-timestamp` has a 5-minute tolerance. `occurred_at` is unbounded.
That means a producer can replay a 6-month-old event as "just happened"
to the receiver. Add: receivers SHOULD ignore `resume_immediately` when
`now - occurred_at > replay_window`, and downgrade to `append_only`.

### 2.6 No causality / ordering primitives

There is no `seq`, `causation_id`, or `prev_event_id`. Out-of-order
delivery of `human.review_required` after `human.approved` is silently
ambiguous. Add an optional `causation_id` and recommend that producers
emit a monotonic `seq` per `subject` so receivers can detect gaps.

### 2.7 Filter expression grammar is unstated

`subscription.filters` accepts any scalar/array, but the meaning is
undefined. Is `"knowledge.kind": ["observation", "tool_result"]` an OR? A
nested-path lookup? Glob? The reference implementation doesn't enforce
filters at all (see 4.1).

**Fix:** specify a small grammar:

- keys are dotted JSON paths
- values are scalars (equality) or arrays (membership / OR)
- all keys are AND
- no regex, no `not`, no nesting in v1

### 2.8 Subscription has no signing-secret field

`protocol.md §9` lists `secret_ref` in the inbox schema, but
`akep-subscription-v1.schema.json` has no field for it. In practice every
subscription needs at least an opaque `secret_id` so receivers can
verify which secret was used. Add it.

### 2.9 Resume policies missing time bounds

`resume_if_waiting` doesn't say *for how long*. If the agent was waiting
30 days ago and the user has moved on, you still want the inbox copy but
not the resume. Add an optional `routing.resume_if_within_seconds`.

---

## 3. Transport and security

### 3.1 Re-serialization is dangerous and undocumented

`examples/python/sign_event.py` sorts keys before signing:

```python
raw_body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

`examples/node/send-event.mjs` implements a custom `stableStringify`.
That's fine *as a producer convention* — but the spec says "verify
against the exact raw body bytes that arrived on the wire." If a proxy or
serializer ever reorders keys mid-transit, signatures break silently.

**Fix:** state explicitly that signing is over wire bytes, and recommend
producers either (a) sign the literal bytes they emit, regardless of
order, or (b) emit canonical JSON (RFC 8785 / JCS) if downstream
canonicalization is required for cross-language signing.

### 3.2 Payload size limit isn't enforced in two of three places

The Python receiver enforces `AKEP_MAX_BYTES`. The Node receiver passes
`maxBytes` to express, but doesn't enforce a hard 413. The schema doesn't
enforce anything (it can't, schema-side). The subscription declares
`max_payload_bytes` but no one checks it.

**Fix:** make the producer responsible for honoring the smaller of
(its own limit, subscription `max_payload_bytes`) and document the
expected `413` response.

### 3.3 HTTP semantics aren't normalized

Across the codebase, response codes are: `202` on accept, `400` on bad
input, `413` on too large, `404` on wrong path. Receivers should also
return `409 Conflict` for duplicate event ids (currently silently
ignored), `401` for missing signature, and `429` for rate limiting. None
of this is in the spec. Add `docs/http-semantics.md`.

### 3.4 No replay-attack defense beyond timestamp window

Timestamp tolerance defaults to 5 minutes. Within that window, an
attacker who captures one valid request can replay it. The reference
receiver rejects duplicate `event_id` via the SQLite primary key — good —
but that's an implementation detail, not a spec requirement. Add: receivers
MUST persist seen `event_id`s for at least the timestamp tolerance.

### 3.5 No defense against secret-confusion across subscriptions

If a host runs receivers for sense2.ai and another producer, and they
share a secret env var, an event signed for producer A can be replayed
to receiver B if both accept the same URL pattern. Recommend
per-subscription secrets, and bind the verification to the subscription
id (header `webhook-subscription-id`, or signature including the
subscription id).

---

## 4. Implementation gaps vs. the spec

### 4.1 Reference receiver does not enforce subscription filters

`protocol.md §8` says receivers MUST reject when "event type or subject
does not match a subscription". The Python and Node receivers never load
a subscription file. They accept any signed event with `spec: akep.v1`.

**Fix:** load `examples/events/subscription.json` (or an env-pointed
file) and reject mismatched events with `422 Unprocessable Entity`.

### 4.2 Skill description is too sense2.ai-centric

`skills/akep/SKILL.md` description leads with "Sense2AI callbacks." For
a generic AKEP user, the skill should still trigger on phrases like
"webhook for AI agent", "long-running tool callback", "human review
event", "agent inbox", etc. Rewrite the description for trigger breadth
while keeping Sense2AI as an example.

### 4.3 Skill `references/protocol-summary.md` is referenced but missing

The skill says "Read `references/protocol-summary.md`…" — but the
`references/` directory exists empty. Either populate it or remove the
pointer.

### 4.4 `make validate` doesn't validate against the schemas

`scripts/validate_repo.py` parses JSON and checks a few hand-coded
invariants. It never validates events against
`schemas/akep-event-v1.schema.json`. Conformance is not enforced.

**Fix:** add a tiny `jsonschema`-based check, gated by
`pip install jsonschema || skip`. Or vendor a minimal Draft 2020-12
validator.

### 4.5 No conformance test suite

`docs/adoption-strategy.md` calls for a conformance test suite "before
v1.0." There is none today. Even a folder of `events/valid/*.json` and
`events/invalid/*.json` plus a tiny harness would let three independent
implementations claim compatibility.

---

## 5. Developer experience (the "easier to use" pile)

These aren't protocol flaws so much as adoption blockers.

### 5.1 No one-command demo

Today, a curious developer has to: export a secret, start the receiver
in one terminal, sign and send an event in another terminal, *and*
already understand HMAC. A `make demo` or `./scripts/demo.sh` that does
all three should be the first thing in the README.

### 5.2 No public test broker

For evaluation, developers want to point at `akep.dev/test` and see
events flow without configuring a tunnel. A hosted ephemeral relay is
called out in the roadmap but doesn't exist; even a docs page with a
public sandbox URL would help.

### 5.3 No OpenAPI / AsyncAPI

JSON Schemas are great for the envelope but useless for the **API
surface** (the ack endpoint, replay endpoint, subscription CRUD). Ship
`openapi.yaml` so Postman, Insomnia, Hoppscotch, and codegen tools work
out of the box.

### 5.4 No `.well-known/akep.json` discovery

A producer should advertise its AKEP capability:

```
GET https://sense2.ai/.well-known/akep.json
{
  "spec": "akep.v1",
  "endpoints": {
    "replay":   "https://sense2.ai/api/akep/events",
    "ack":      "https://sense2.ai/api/akep/events/{event_id}/ack",
    "subscribe":"https://sense2.ai/api/akep/subscriptions"
  },
  "signature_algorithms": ["v1"],
  "event_types": ["knowledge.acquired", "human.review_required", ...],
  "max_payload_bytes": 1048576,
  "replay_retention_days": 7
}
```

Cheap, discoverable, gives crawlers and agents a single integration
target.

### 5.5 No copy-pasteable curl

The README has Python commands; it has no `curl` example. `curl` is the
universal AI/dev lingua franca and is what LLMs will quote back when
someone asks ChatGPT "how do I send an AKEP event?".

### 5.6 No SDK on PyPI / npm

`examples/python/receiver.py` is dependency-free, which is excellent for
auditability, but not portable. Publish:

- `akep` on PyPI (`from akep import verify, sign, AKEPEvent`)
- `@akep/core` on npm (CommonJS + ESM)
- `akep-go` and `akep-rs` later

`examples/*` then become demos that *use* the SDK, not standalone files.

### 5.7 No CloudEvents bridge

CloudEvents (CNCF, v1.0) is the dominant prior art for event envelopes —
Azure Event Grid, Knative, Argo, Dapr, AWS EventBridge all speak it. A
documented bidirectional mapping costs ~30 lines and unlocks a huge
amount of distribution. Recommended mapping:

| CloudEvent attribute | AKEP path                       |
| -------------------- | ------------------------------- |
| `id`                 | `event_id`                      |
| `source`             | `source.name`                   |
| `type`               | `event_type`                    |
| `time`               | `occurred_at`                   |
| `datacontenttype`    | `knowledge.content_type`        |
| `subject`            | `subject.task_id` or thread_id  |
| `data`               | `knowledge`                     |

### 5.8 No `Hookdeck` / `ngrok` / `Cloudflare Tunnel` recipes

`docs/sense2ai-market.md` mentions them by name but doesn't show the
commands. New users don't know what "expose port 8787 over the
public internet" means in practice. A 6-line snippet per tunnel
provider would save hours.

### 5.9 Branding and discoverability

The README never names the keywords AKEP should rank for in ChatGPT,
Claude, and Google: *async agent events*, *webhook for AI agents*, *MCP
async events*, *agent inbox*, *human-in-the-loop webhook*, *long-running
tool callback*, *notify agent when X*. LLMs cite documents that contain
the literal phrasing of the query. Today AKEP has the protocol but not
the prose.

---

## 6. Documentation gaps

- No `SECURITY.md` threat model (the file exists but is one paragraph).
- No "Comparing AKEP to webhooks / MCP / A2A / CloudEvents" page.
- No FAQ. "Do I need AKEP if I already use webhooks?" is the single
  most-asked question and is unanswered.
- No diagram for the resume-policy decision tree.
- No "Producer Quickstart" — every doc is receiver-oriented.
- No "Self-host vs. hosted relay" decision matrix.
- License is Apache-2.0 (good) but README doesn't say so prominently.

---

## 7. Recommended sequencing

Three milestones, each one calendar week of work, would close almost
every issue above:

**Week 1 — Spec hygiene (closes 1.1, 1.2, 1.5, 2.x).**
Fix schema/spec disagreements, tighten `subject`, switch `spec` const →
pattern, namespace `extensions`, fix `knowledge.hash`, add
`anyOf` to subscriptions, document `event_id` constraints in the spec.

**Week 2 — Reference reality (closes 1.6, 4.x, 5.1, 5.5).**
Make sense2.ai emit AKEP headers (additively). Add a sense2.ai →
AKEP adapter. Enforce subscriptions in the reference receivers. Ship
`scripts/demo.sh`, a `curl` example, and schema-based validation in
`make validate`.

**Week 3 — Adoption surface (closes 1.3, 1.4, 1.7, 5.3, 5.4, 5.6, 5.7).**
Define the signature algorithm registry, add `kid`/rotation, write
`openapi.yaml`, ship `.well-known/akep.json`, publish the Python and
Node SDKs to PyPI/npm, document the CloudEvents bridge.

After that, AKEP v1.0 freeze is defensible.

---

## 8. What AKEP gets right

It's worth saying out loud. The protocol gets a lot of important things
right that competing proposals tend to miss:

- The safety boundary is **explicit and load-bearing**: "events carry
  knowledge, never commands." That single sentence does more than most
  agent-security RFCs.
- Standard Webhooks alignment means existing infra works.
- "Local policy always wins" on resume — exactly right.
- Receivers MUST NOT invoke a model from the request handler — closes
  the most common production footgun.
- Model-neutral framing puts AKEP in the right architectural slot,
  next to MCP rather than competing with it.
- The Sense2AI use case is concrete enough to test the protocol, not
  so specific that it pollutes the spec.

Hold onto those. The fixes above are about making the protocol *easier
to reach* — not about changing what it is.
