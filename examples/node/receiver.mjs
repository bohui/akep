import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import express from "express";

const host = process.env.AKEP_HOST || "127.0.0.1";
const port = Number(process.env.AKEP_PORT || "8787");
const route = process.env.AKEP_PATH || "/akep/events";
const maxBytes = process.env.AKEP_MAX_BYTES || "1mb";
const toleranceSeconds = Number(process.env.AKEP_TIMESTAMP_TOLERANCE || "300");
const inboxPath = process.env.AKEP_INBOX_JSONL || ".akep/inbox.jsonl";

function secretBytes() {
  const secret = process.env.AKEP_WEBHOOK_SECRET;
  if (!secret) throw new Error("AKEP_WEBHOOK_SECRET is required");
  if (secret.startsWith("whsec_")) return Buffer.from(secret.slice("whsec_".length), "base64");
  return Buffer.from(secret, "utf8");
}

function expectedSignature(eventId, timestamp, rawBody) {
  const signed = Buffer.concat([
    Buffer.from(eventId),
    Buffer.from("."),
    Buffer.from(timestamp),
    Buffer.from("."),
    rawBody,
  ]);
  return crypto.createHmac("sha256", secretBytes()).update(signed).digest("base64");
}

function verify(headers, rawBody) {
  const eventId = headers["webhook-id"] || "";
  const timestamp = headers["webhook-timestamp"] || "";
  const signature = headers["webhook-signature"] || "";
  if (!eventId || !timestamp || !signature) return [false, "missing webhook signature headers"];
  if (eventId.includes(".") || timestamp.includes(".")) return [false, "event id and timestamp must not contain dots"];
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > toleranceSeconds) return [false, "stale timestamp"];

  const expected = Buffer.from(expectedSignature(eventId, timestamp, rawBody));
  const valid = signature.split(/\s+/).some((part) => {
    const [algorithm, value] = part.split(",", 2);
    if (algorithm !== "v1" || !value) return false;
    const actual = Buffer.from(value);
    return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
  });
  if (!valid) return [false, "invalid signature"];
  return [true, ""];
}

function matchesSubscription(event, subscription, headers) {
  // Check event type
  const eventType = event.event_type;
  const allowedTypes = subscription.event_types || [];
  if (!allowedTypes.includes(eventType)) {
    return [false, `event_type '${eventType}' not allowed by subscription`];
  }

  // Check dotted filters
  const filters = subscription.filters || {};
  for (const [path, filterVal] of Object.entries(filters)) {
    let actualVal = event;
    for (const part of path.split(".")) {
      if (actualVal && typeof actualVal === "object" && part in actualVal) {
        actualVal = actualVal[part];
      } else {
        actualVal = undefined;
        break;
      }
    }

    if (Array.isArray(filterVal)) {
      if (!filterVal.includes(actualVal)) {
        return [false, `filter mismatch: '${path}' value '${actualVal}' not in [${filterVal.join(", ")}]`];
      }
    } else {
      if (actualVal !== filterVal) {
        return [false, `filter mismatch: '${path}' value '${actualVal}' !== '${filterVal}'`];
      }
    }
  }

  // Check security constraints
  const security = subscription.security || {};

  // 1. accepted_source_names
  const sourceName = event.source?.name;
  if (security.accepted_source_names && !security.accepted_source_names.includes(sourceName)) {
    return [false, `source.name '${sourceName}' not in accepted_source_names`];
  }

  // 2. accepted_producer_ids
  const producerId = event.source?.producer_id;
  if (security.accepted_producer_ids && !security.accepted_producer_ids.includes(producerId)) {
    return [false, `source.producer_id '${producerId}' not in accepted_producer_ids`];
  }

  // 3. signature_key_ids
  const keyId = headers["webhook-signature-key-id"];
  if (security.signature_key_ids && keyId && !security.signature_key_ids.includes(keyId)) {
    return [false, `webhook-signature-key-id '${keyId}' not in signature_key_ids`];
  }

  return [true, ""];
}

function appendEventIfNew(rawBody, eventId) {
  fs.mkdirSync(path.dirname(inboxPath), { recursive: true });
  if (fs.existsSync(inboxPath)) {
    const rows = fs.readFileSync(inboxPath, "utf8").split("\n").filter(Boolean);
    for (const row of rows) {
      try {
        const existing = JSON.parse(row);
        if (existing.event_id === eventId) return false;
      } catch {
        // Ignore malformed historical rows; the new event is still validated.
      }
    }
  }
  fs.appendFileSync(inboxPath, `${rawBody.toString("utf8")}\n`);
  return true;
}

const app = express();
app.use(express.raw({ type: "application/json", limit: maxBytes }));

app.post(route, (req, res) => {
  const [ok, reason] = verify(req.headers, req.body);
  if (!ok) return res.status(400).json({ error: reason });

  let event;
  try {
    event = JSON.parse(req.body.toString("utf8"));
  } catch {
    return res.status(400).json({ error: "invalid json" });
  }

  if (event.event_id !== req.headers["webhook-id"]) {
    return res.status(400).json({ error: "webhook-id does not match event_id" });
  }
  if (!String(event.spec || "").startsWith("akep.v1")) return res.status(400).json({ error: "unsupported spec" });
  if (!event.subject || Object.keys(event.subject).length === 0) return res.status(400).json({ error: "subject is required" });
  if ("command" in event) return res.status(400).json({ error: "AKEP events carry knowledge, not commands" });

  const subPath = process.env.AKEP_SUBSCRIPTION_PATH || "examples/events/subscription.json";
  if (fs.existsSync(subPath)) {
    try {
      const subscription = JSON.parse(fs.readFileSync(subPath, "utf8"));
      const [okSub, reasonSub] = matchesSubscription(event, subscription, req.headers);
      if (!okSub) {
        return res.status(422).json({ error: `subscription mismatch: ${reasonSub}` });
      }
    } catch (err) {
      console.error("Error loading or matching subscription:", err);
    }
  }

  const inserted = appendEventIfNew(req.body, event.event_id);
  return res.status(202).json({ accepted: true, duplicate: !inserted });
});

app.listen(port, host, () => {
  console.log(`AKEP receiver listening on http://${host}:${port}${route}`);
  console.log(`Inbox file: ${inboxPath}`);
});
