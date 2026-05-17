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
  const digest = crypto.createHmac("sha256", secretBytes()).update(signed).digest("base64");
  return `v1,${digest}`;
}

function verify(headers, rawBody) {
  const eventId = headers["webhook-id"] || "";
  const timestamp = headers["webhook-timestamp"] || "";
  const signature = headers["webhook-signature"] || "";
  if (!eventId || !timestamp || !signature) return [false, "missing webhook signature headers"];
  if (eventId.includes(".") || timestamp.includes(".")) return [false, "event id and timestamp must not contain dots"];
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > toleranceSeconds) return [false, "stale timestamp"];

  const expected = expectedSignature(eventId, timestamp, rawBody);
  const a = Buffer.from(expected);
  const b = Buffer.from(signature);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return [false, "invalid signature"];
  return [true, ""];
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
  if (event.spec !== "akep.v1") return res.status(400).json({ error: "unsupported spec" });
  if ("command" in event) return res.status(400).json({ error: "AKEP events carry knowledge, not commands" });

  fs.mkdirSync(path.dirname(inboxPath), { recursive: true });
  fs.appendFileSync(inboxPath, `${req.body.toString("utf8")}\n`);
  return res.status(202).json({ accepted: true });
});

app.listen(port, host, () => {
  console.log(`AKEP receiver listening on http://${host}:${port}${route}`);
  console.log(`Inbox file: ${inboxPath}`);
});

