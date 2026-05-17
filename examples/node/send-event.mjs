import crypto from "node:crypto";
import fs from "node:fs";

const url = process.argv[2] || "http://127.0.0.1:8787/akep/events";
const eventPath = process.argv[3] || "examples/events/sense2ai-task-completed.json";

function secretBytes() {
  const secret = process.env.AKEP_WEBHOOK_SECRET;
  if (!secret) throw new Error("AKEP_WEBHOOK_SECRET is required");
  if (secret.startsWith("whsec_")) return Buffer.from(secret.slice("whsec_".length), "base64");
  return Buffer.from(secret, "utf8");
}

function stableStringify(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
}

const event = JSON.parse(fs.readFileSync(eventPath, "utf8"));
const rawBody = Buffer.from(stableStringify(event));
const eventId = event.event_id;
const timestamp = String(Math.floor(Date.now() / 1000));
const signed = Buffer.concat([
  Buffer.from(eventId),
  Buffer.from("."),
  Buffer.from(timestamp),
  Buffer.from("."),
  rawBody,
]);
const signature = `v1,${crypto.createHmac("sha256", secretBytes()).update(signed).digest("base64")}`;

const response = await fetch(url, {
  method: "POST",
  headers: {
    "content-type": "application/json",
    "webhook-id": eventId,
    "webhook-timestamp": timestamp,
    "webhook-signature": signature,
  },
  body: rawBody,
});

console.log(response.status, await response.text());

