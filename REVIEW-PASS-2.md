# AKEP v1 Draft — Second-Pass Review

A close re-read after the v0.2 refactor: new schemas, new HTTP surface
(replay / wait / ack / tasks), `.well-known/akep.json`, OpenAPI and
AsyncAPI definitions, profile model, conformance fixtures,
`signatures.md`, `replay-and-ack.md`, `profiles.md`, `discovery.md`, and
updated reference receivers in Python and Node.

Reviewer: post-refactor pass, May 2026.
Live test: `make validate` (with `jsonschema`) + end-to-end smoke against
the Python reference receiver including discovery, replay, task state,
ack, and ack idempotency.

---

## TL;DR

The refactor closed **6 of 8** original blockers and ~9 of 12 usability
gaps. AKEP is now genuinely shippable as a v0.2 draft. Two real issues
turned up in this pass — one fail-open security bug in subscription
enforcement, and unauthenticated replay/task endpoints — plus a handful
of smaller doc-vs-code drifts.

Closed since pass 1:

- ✓ 1.1 schema/spec consistency on `subject` and `routing`
- ✓ 1.2 `subject: {}` rejected (`minProperties: 1` + `anyOf`)
- ✓ 1.5 `spec` is now a pattern (`^akep\.v1(\.[0-9]+)?$`)
- ✓ 1.7 ack and replay contracts specified (`docs/replay-and-ack.md`)
- ✓ 2.1 `extensions` namespacing rule (propertyNames pattern)
- ✓ 2.2 `knowledge.hash` requires `algo:value` form
- ✓ 2.4 `event_id` constraint hoisted into the spec
- ✓ 2.6 `causation_id` and `sequence` added
- ✓ 2.7 filter grammar specified (dotted JSON paths, AND, scalar/list)
- ✓ 2.8 subscription gains `security` block with `signature_key_ids`
- ✓ 3.1 raw-bytes signing rule clarified
- ✓ 4.1 reference receivers now enforce subscription filters
- ✓ 4.3 `references/protocol-summary.md` exists and is current
- ✓ 4.4 `make validate` runs real JSON Schema conformance + negative cases
- ✓ 5.1 `make demo` (one-command end-to-end)
- ✓ 5.3 OpenAPI 3.1 + AsyncAPI 3 published
- ✓ 5.4 `.well-known/akep.json` discovery document published
- ✓ 5.5 curl quickstart added
- ✓ key-rotation language (multi-signature header) added to
  `signatures.md` and reference verifier

Still open or partially addressed:

- 1.3 key-id rotation: **documented but fail-open** (see §1 below)
- 1.4 algorithm registry: **documented** (`v1`/`v1a`/`v2`), only `v1`
  implemented — fine for v1 freeze
- 1.6 sense2.ai legacy headers: tracked in `PROTOCOL-REVIEW.md`
  remaining work; no adapter yet
- 1.8 producer auth: `accepted_producer_ids` exists but is **fail-open
  when the producer omits `producer_id`** (see §2)
- 2.3 `knowledge.uri` lifetime: unchanged
- 2.5 `occurred_at` skew vs `resume_immediately`: unchanged
- 2.9 resume policies still have no time bound
- 3.4 replay-attack defense beyond timestamp window: still implicit
- 5.2 hosted test broker: not yet
- 5.6 SDK on PyPI/npm: not yet
- 5.7 CloudEvents mapping doc: not yet
- New gap: replay, wait, and task endpoints have no auth model.

---

## 1. Blocking: subscription `signature_key_ids` enforcement is fail-open

`docs/signatures.md` and the new subscription schema introduce
`security.signature_key_ids`. The reference receivers attempt to enforce
it, but both implementations check it only when the request actually
includes a key id:

`examples/python/receiver.py`:
```python
if accepted_key_ids is not None and key_id and key_id not in accepted_key_ids:
    return False, f"webhook-signature-key-id '{key_id}' not in signature_key_ids"
```

`examples/node/receiver.mjs`:
```js
if (security.signature_key_ids && keyId && !security.signature_key_ids.includes(keyId))
```

The `and key_id` / `&& keyId` clauses mean: if the producer omits
`webhook-signature-key-id` entirely, the security constraint is silently
bypassed. The whole point of advertising `signature_key_ids` is to bind
the subscription to specific active keys; allowing unkeyed deliveries
defeats that.

**Repro (from live smoke test):**

```
subscription requires signature_key_ids: ["2026-05"]
event signed without webhook-signature-key-id header
→ receiver: 202 accepted
```

**Fix:** when the subscription declares `signature_key_ids`, require the
header to be present *and* present in the list. Suggested Python:

```python
accepted_key_ids = security.get("signature_key_ids")
if accepted_key_ids is not None:
    if not key_id:
        return False, "webhook-signature-key-id required by subscription"
    if key_id not in accepted_key_ids:
        return False, f"webhook-signature-key-id '{key_id}' not in signature_key_ids"
```

Same for Node.

**Bonus:** `examples/python/sign_event.py` and
`examples/node/send-event.mjs` never emit `webhook-signature-key-id`, so
the demo can't exercise this path even when the receiver is fixed. Add
an optional `--key-id` flag / env var.

Severity: **high**. Live exploit in the reference impl.

---

## 2. Blocking: `accepted_producer_ids` is fail-open on missing `producer_id`

`source.producer_id` is now optional in the event schema but enforced by
the subscription's `accepted_producer_ids`. Reference enforcement:

```python
producer_id = event.get("source", {}).get("producer_id")
accepted_producers = security.get("accepted_producer_ids")
if accepted_producers is not None and producer_id not in accepted_producers:
    return False, ...
```

That's correct — `None not in [...]` is True, so a missing
`producer_id` will be caught. ✓

However, `event.source.producer_id` is **not** required by the schema,
which means a producer can simply omit it and still pass schema
validation. Combined with the key-id bypass above, this creates a path
where a subscription claiming strict producer + key restrictions accepts
an event with neither.

**Fix:** either

- make `producer_id` required at the schema level for v1, or
- have receivers treat a missing `producer_id` as a rejection when the
  subscription declares `accepted_producer_ids`.

Recommendation: require `producer_id` in v1. The cost is one line of
boilerplate per producer and the security value is large.

Severity: **medium-high**.

---

## 3. Blocking: replay / wait / tasks endpoints are unauthenticated

The new `GET /akep/events`, `GET /akep/events/wait`, and
`GET /akep/tasks/{task_id}` endpoints in both reference receivers have
no authentication of any kind. Live smoke test:

```
$ curl -o /dev/null -w "%{http_code}\n" 'http://127.0.0.1:8787/akep/events'
200
```

That returns the full inbox. In production, anyone who can reach the
receiver can dump every signed event ever delivered. The protocol
mentions only ingestion auth (HMAC); it says nothing about replay /
task auth.

**Fix:** add a `docs/auth.md` (or §10 in the protocol) specifying:

- Replay, wait, and task endpoints MUST require caller authentication.
- Recommended schemes: bearer token bound to the subscription, mTLS, or
  signed query (`?cursor=...&signature=...`).
- The discovery document SHOULD declare which auth schemes are
  supported.

The reference receivers can ship an opt-in `AKEP_REPLAY_BEARER` token
gate, off by default for the local demo.

Severity: **high** for any production deployment.

---

## 4. Doc/code drift

### 4.1 Discovery document disagrees on `delivery_profiles`

`.well-known/akep.json` (root file) advertises:
```json
"delivery_profiles": ["webhook", "replay_inbox", "relay"]
```

The Python receiver's served `/.well-known/akep.json` advertises:
```json
"delivery_profiles": ["webhook", "replay_inbox", "task_state"]
```

Neither is wrong, but they should agree on which list is "the canonical
example" — pick one and align. Also, `task_state` is a profile per
`profiles.md` but `discovery.md`'s example doesn't list it.

### 4.2 `sense2ai-market.md` still calls Sense2.ai a "marketplace"

The `source.type` enum dropped `marketplace` in favor of `publisher`
(reflected in the example event). The `sense2ai-market.md` prose still
uses "marketplace" twice and is mapped via the `Knowledge Publisher
Results` profile. Suggestion: keep the prose ("Sense2.ai is a
marketplace where humans fulfill agent requests") but explicitly call
out that AKEP categorizes Sense2.ai as a `publisher` source type. Avoid
reader confusion when they cross-reference the schema.

### 4.3 OpenAPI doesn't document 422

Both reference receivers return `422 Unprocessable Entity` for
subscription mismatch — correct per pass-1 recommendation. But
`openapi/akep.v1.openapi.json` lists only 202 / 400 / 413 for `POST
/akep/events`. Add 422 (and consider 409 for duplicate event ids, 401 /
403 for bad auth once §3 lands).

### 4.4 OpenAPI `$ref` to a relative file path

`"$ref": "../schemas/akep-event-v1.schema.json"` will not resolve in
hosted tools (Swagger UI on docs.akep.dev, Stoplight, Postman). Use the
schema's `$id`:
`"$ref": "https://akep.dev/schemas/akep-event-v1.schema.json"`. Same in
AsyncAPI.

### 4.5 `examples/events/subscription.json` has a `filters.knowledge.kind` array, but `accepted_producer_ids` of `["prod_sense2ai_01"]` — the demo only happens to pass because the example event uses that exact producer id

Not a bug, but the `demo.sh` regenerates the event id and leaves
`source` alone; explain that in `quickstart.md` so a reader who renames
the source name doesn't wonder why their adapted demo 422s.

---

## 5. Smaller things found in this pass

### 5.1 Subscription file parsing fails open

In the Python receiver:

```python
try:
    with open(sub_path, ...) as fh:
        subscription = json.load(fh)
    ok_sub, reason_sub = matches_subscription(event, subscription, self.headers)
    if not ok_sub: ...
except Exception as e:
    print(f"Error checking subscription filters: {e}")
```

If the subscription file is malformed, the receiver logs and proceeds
to accept the event. That fails open. Same shape in the Node receiver.
Fail closed: log and 503 (or 500).

### 5.2 Node receiver inbox dedup is O(N²)

`appendEventIfNew` re-reads the entire JSONL file on every request to
look for the existing event_id. Document that the JSONL receiver is a
demo-only path and link to the Python SQLite receiver for any real use.

### 5.3 `task_state` recomputes the full inbox

`/akep/tasks/{task_id}` reads every row and filters by `task_id`.
Fine for the reference; recommend that production receivers index
`task_id` from the event body at insert time.

### 5.4 `parse_cursor` silently coerces malformed cursors to 0

```python
try:
    return max(0, int(cursor))
except ValueError:
    return 0
```

A client that round-trips a corrupted cursor will silently restart at
the beginning. Should return a 400 with `{"error": "invalid cursor"}`
instead — it's almost always a client bug worth surfacing.

### 5.5 `webhook-signature-key-id` is documented but reference signer never sends it

`sign_event.py` and `send-event.mjs` don't accept a `--key-id` flag.
Add it; it costs three lines and lets the demo exercise key rotation.

### 5.6 `routing.causation_id` and `routing.sequence` are in the spec and example, but no doc explains how a receiver should *use* them

Add a short subsection in `replay-and-ack.md` or `protocol.md`: "If a
receiver sees `routing.sequence` going backwards or skipping for a given
`subject`, it MAY mark the subject as out-of-order and queue a replay."

### 5.7 No deletion / retention enforcement endpoint

`replay-and-ack.md` says producers SHOULD retain unacked events for at
least 7 days. There's no defined endpoint for clients to purge or
auto-expire; not strictly required, but worth a one-line note in the
spec.

### 5.8 `propertyNames` regex requires ≥ 2 chars

```
"propertyNames": { "pattern": "^[a-z0-9][a-z0-9_.-]*[a-z0-9]$" }
```

This rejects single-character extension keys (`"v"` would be invalid).
Probably intentional. If so, document it. If not, switch to
`^[a-z0-9]([a-z0-9_.-]*[a-z0-9])?$`.

---

## 6. What's verifiably working (live smoke test, May 2026)

```
✓ make validate (schema-strict; jsonschema installed)
  - schemas/akep-event-v1.schema.json
  - schemas/akep-subscription-v1.schema.json
  - 4 valid event/subscription fixtures: PASSED
  - 3 invalid event fixtures (no_subject, empty_subject, command): FAILED-AS-EXPECTED

✓ make demo
  - signed event → 202 accepted → durable inbox row
  - works without sqlite3 CLI (Python fallback)

✓ GET /.well-known/akep.json     → 200 with profile list
✓ POST /akep/events              → 202 (matching subscription)
✓ GET  /akep/events?limit=5       → 200 with replay page
✓ GET  /akep/tasks/{task_id}     → 200 with reconstructed task state
✓ POST /akep/events/{id}/ack     → 200 (idempotent on repeat)
✓ POST /akep/events/missing/ack  → 404
✓ POST /akep/events with mismatched source.name → 422
```

That's the protocol in operation, end-to-end, against the published
schemas and OpenAPI surface. As reference-implementation health goes,
that's well above the bar for a public draft.

---

## 7. Recommended ordering for the next pass

Three small PRs would close every blocker above.

**PR 1 — Fix fail-open security paths (§1, §2, §5.1).**
Tighten the two `matches_subscription` helpers, require `producer_id`
in the schema, fail closed on subscription-file parse errors, and add
a unit test per case. ~50 lines, mostly tests.

**PR 2 — Add auth to replay/wait/task endpoints (§3).**
Document `docs/auth.md`, add an opt-in `AKEP_REPLAY_BEARER` env var to
both reference receivers, advertise `auth_schemes` in
`.well-known/akep.json`, declare 401/403 in OpenAPI. ~80 lines.

**PR 3 — Doc cleanups (§4, §5.2-§5.8).**
Align discovery docs, document 422/409, switch OpenAPI/AsyncAPI `$ref`
to absolute schema URLs, add `--key-id` to the signers, document
causation/sequence semantics, fix `parse_cursor` to 400 on garbage,
note retention. ~40 lines.

After those, v1.0 envelope freeze is defensible. The bigger work
(SDKs, CloudEvents bridge, hosted relay, sense2.ai legacy adapter) is
adoption-flywheel — important, but not blocking on protocol
correctness.

---

## 8. What's clearly improved since pass 1

It's worth saying out loud — the v0.2 refactor is a real upgrade:

- The protocol now reads like a v1 candidate, not a sketch.
- Schema, prose, examples, and reference code agree on the same shape.
- Schema-strict validation (positive + negative fixtures) is wired into
  CI's natural entry point (`make validate`).
- The HTTP API is actually defined, not advertised — OpenAPI 3.1 +
  AsyncAPI 3 + a working reference impl all describe the same surface.
- Discovery (`/.well-known/akep.json`) means a crawler or agent has a
  single place to ask "do you speak AKEP?".
- Profiles (Core / Replay / Relay / Task State / Knowledge Publisher
  Results) make conformance discussions tractable.
- The `references/protocol-summary.md` that the skill points at exists
  and is current.
- Security identity (`producer_id`, `signature_key_ids`, multi-signature
  rotation) is at least in the model, even if enforcement needs the
  fixes above.

The remaining gaps are concrete and small. The hard architectural
decisions look right.
