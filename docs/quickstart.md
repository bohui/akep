# AKEP Quickstart

Get a verified AKEP event into a local durable inbox in 60 seconds. No
cloud, no signup, no third-party dependencies beyond Python 3 (or
Node 20+).

This guide covers four flavors of the same demo so you can pick the one
that matches your stack:

1. [One-command demo](#1-one-command-demo) — `make demo`
2. [Python receiver + Python signer](#2-python-receiver--python-signer)
3. [Node receiver + Node sender](#3-node-receiver--node-sender)
4. [Curl from anything](#4-curl-from-anything)

After that:

- [Expose the receiver to the public internet](#5-expose-the-receiver-to-the-public-internet)
- [Use AKEP from your own producer](#6-emit-akep-from-your-own-producer)
- [What to read next](#7-what-to-read-next)

---

## 1. One-command demo

The fastest path. Starts a local receiver in the background, signs and
sends the example Sense2.ai event, prints the resulting inbox row, and
cleans up.

```bash
git clone https://github.com/bohui/akep.git
cd akep
make demo
```

You should see something like:

```text
AKEP receiver listening on http://127.0.0.1:8787/akep/events
202 {"accepted":true,"duplicate":false}
event_id|event_type|source_name
evt_sense2ai_01HX5S8ZQ9J6W9E5W4H8A2K7D3|knowledge.acquired|sense2ai
```

That single line — `event_type=knowledge.acquired`, `source_name=sense2ai` —
is the proof. A signed event has been verified, idempotency-checked, and
durably stored in `.akep/inbox.db`.

---

## 2. Python receiver + Python signer

Run the receiver in one terminal:

```bash
export AKEP_WEBHOOK_SECRET="dev-secret"
python3 examples/python/receiver.py
```

Send the example event from another terminal:

```bash
export AKEP_WEBHOOK_SECRET="dev-secret"
python3 examples/python/sign_event.py \
  --url http://127.0.0.1:8787/akep/events \
  --event examples/events/sense2ai-task-completed.json
```

Inspect the durable inbox:

```bash
sqlite3 .akep/inbox.db "select event_id, event_type, source_name from events;"
```

Replay the inbox over HTTP:

```bash
curl -sS 'http://127.0.0.1:8787/akep/events?limit=10'
```

Ack the event after local persistence or processing:

```bash
curl -sS -X POST http://127.0.0.1:8787/akep/events/evt_sense2ai_01HX5S8ZQ9J6W9E5W4H8A2K7D3/ack \
  -H 'content-type: application/json' \
  --data '{"status":"stored","reason":"quickstart replay verified"}'
```

---

## 3. Node receiver + Node sender

```bash
cd examples/node
npm install
export AKEP_WEBHOOK_SECRET="dev-secret"
node receiver.mjs
```

In another terminal:

```bash
cd examples/node
export AKEP_WEBHOOK_SECRET="dev-secret"
node send-event.mjs http://127.0.0.1:8787/akep/events ../events/sense2ai-task-completed.json
```

Inspect the inbox:

```bash
cat .akep/inbox.jsonl
```

---

## 4. Curl from anything

This is the wire protocol with no SDK between you and HTTP. Useful when
you want to integrate AKEP from a language that doesn't yet have a
client, or when you want to verify a producer.

```bash
SECRET="dev-secret"
EVENT_ID="evt_demo_$(date +%s)"
TS=$(date +%s)
BODY=$(cat <<JSON
{
  "spec": "akep.v1",
  "event_id": "${EVENT_ID}",
  "event_type": "knowledge.acquired",
  "occurred_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source": { "name": "demo", "type": "system" },
  "subject": { "task_id": "task_demo" },
  "knowledge": {
    "kind": "observation",
    "content_type": "text/plain",
    "summary": "hello AKEP"
  },
  "routing": { "resume_policy": "append_only" }
}
JSON
)
# IMPORTANT: the same bytes you sign must be the bytes you send.
BODY_MIN=$(printf '%s' "$BODY" | python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin), separators=(",",":"), sort_keys=True), end="")')

SIG="v1,$(printf '%s' "${EVENT_ID}.${TS}.${BODY_MIN}" \
  | openssl dgst -sha256 -hmac "$SECRET" -binary \
  | base64)"

curl -sS -X POST http://127.0.0.1:8787/akep/events \
  -H "content-type: application/json" \
  -H "webhook-id: ${EVENT_ID}" \
  -H "webhook-timestamp: ${TS}" \
  -H "webhook-signature: ${SIG}" \
  --data "${BODY_MIN}"
```

**Pitfall:** the receiver validates the HMAC against the **exact raw
body bytes** that arrived. If your shell, editor, or proxy reformats the
JSON between signing and sending, verification will fail. Sign the
canonical bytes you are about to send and send them unchanged.

---

## 5. Expose the receiver to the public internet

For development tunnels:

```bash
# Cloudflare Tunnel (stable, free, persistent)
cloudflared tunnel --url http://127.0.0.1:8787

# Hookdeck (best replay/debug experience)
hookdeck listen 8787 akep --path /akep/events

# ngrok (fastest demo)
ngrok http 8787

# Tailscale Funnel (if your team already runs Tailscale)
tailscale funnel 8787
```

Register the public URL as your producer's webhook destination (for
Sense2.ai: as the task webhook URL or AKEP subscription `delivery.url`).

For **production**, prefer an outbound relay over exposing a local
port. Use cursor replay or HTTP long-poll when the local agent only has
outbound access; see [`replay-and-ack.md`](replay-and-ack.md).

---

## 6. Emit AKEP from your own producer

You need three things on the producer side:

1. A stable, globally unique `event_id` (ULID or UUIDv7 recommended).
2. The same `AKEP_WEBHOOK_SECRET` configured on the receiver.
3. The Standard Webhooks signature.

Python producer (copy-paste):

```python
import base64, hashlib, hmac, json, time, urllib.request

def send_akep_event(url: str, event: dict, secret: str) -> None:
    body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    event_id = event["event_id"]
    ts = str(int(time.time()))
    signed = b".".join([event_id.encode(), ts.encode(), body])
    sig = "v1," + base64.b64encode(
        hmac.new(secret.encode(), signed, hashlib.sha256).digest()
    ).decode()

    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "webhook-id": event_id,
            "webhook-timestamp": ts,
            "webhook-signature": sig,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read()
```

Node producer (copy-paste):

```js
import crypto from "node:crypto";

export async function sendAkepEvent(url, event, secret) {
  const body = Buffer.from(JSON.stringify(event)); // sign the bytes you send
  const ts = String(Math.floor(Date.now() / 1000));
  const signed = Buffer.concat([
    Buffer.from(event.event_id), Buffer.from("."),
    Buffer.from(ts), Buffer.from("."),
    body,
  ]);
  const sig = "v1," + crypto.createHmac("sha256", secret).update(signed).digest("base64");

  const res = await fetch(url, {
    method: "POST",
    body,
    headers: {
      "content-type": "application/json",
      "webhook-id": event.event_id,
      "webhook-timestamp": ts,
      "webhook-signature": sig,
    },
  });
  if (!res.ok) throw new Error(`AKEP delivery failed: ${res.status} ${await res.text()}`);
}
```

Map your domain event to `event_type` (`knowledge.acquired`,
`tool.completed`, `human.approved`, etc.) and your domain identifiers
to `subject.task_id` / `thread_id` / `agent_id`. Done.

---

## 7. What to read next

- The normative envelope: [`docs/protocol.md`](protocol.md)
- The FAQ: [`docs/faq.md`](faq.md)
- Sense2.ai mapping: [`docs/sense2ai-market.md`](sense2ai-market.md)
- Model and runtime integrations:
  [`docs/model-integrations.md`](model-integrations.md)
- Install the AKEP skill into Claude Code or OpenClaw:
  [`docs/skill-installation.md`](skill-installation.md)
- Open issues, design gaps, and planned fixes:
  [`../PROTOCOL-REVIEW.md`](../PROTOCOL-REVIEW.md)
