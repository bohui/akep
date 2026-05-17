#!/usr/bin/env python3
"""Minimal AKEP webhook receiver.

No third-party dependencies. Stores verified events in `.akep/inbox.db`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.environ.get("AKEP_HOST", "127.0.0.1")
PORT = int(os.environ.get("AKEP_PORT", "8787"))
PATH = os.environ.get("AKEP_PATH", "/akep/events")
MAX_BYTES = int(os.environ.get("AKEP_MAX_BYTES", "1048576"))
TOLERANCE_SECONDS = int(os.environ.get("AKEP_TIMESTAMP_TOLERANCE", "300"))
DB_PATH = Path(os.environ.get("AKEP_INBOX_DB", ".akep/inbox.db"))


def secret_bytes() -> bytes:
    secret = os.environ.get("AKEP_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("AKEP_WEBHOOK_SECRET is required")
    if secret.startswith("whsec_"):
        return base64.b64decode(secret.removeprefix("whsec_"))
    return secret.encode("utf-8")


def expected_signature(event_id: str, timestamp: str, raw_body: bytes) -> str:
    signed = b".".join([event_id.encode(), timestamp.encode(), raw_body])
    digest = hmac.new(secret_bytes(), signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode("ascii")


def verify_signature(headers, raw_body: bytes) -> tuple[bool, str]:
    event_id = headers.get("webhook-id", "")
    timestamp = headers.get("webhook-timestamp", "")
    signature = headers.get("webhook-signature", "")

    if not event_id or not timestamp or not signature:
        return False, "missing webhook signature headers"
    if "." in event_id or "." in timestamp:
        return False, "event id and timestamp must not contain dots"
    try:
        age = abs(time.time() - int(timestamp))
    except ValueError:
        return False, "invalid timestamp"
    if age > TOLERANCE_SECONDS:
        return False, "stale timestamp"

    expected = expected_signature(event_id, timestamp, raw_body)
    if not hmac.compare_digest(expected, signature):
        return False, "invalid signature"
    return True, ""


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """
            create table if not exists events (
              event_id text primary key,
              event_type text not null,
              source_name text not null,
              received_at integer not null,
              raw_json text not null
            )
            """
        )


def store_event(event: dict, raw_body: bytes) -> bool:
    with sqlite3.connect(DB_PATH) as db:
        try:
            db.execute(
                """
                insert into events(event_id, event_type, source_name, received_at, raw_json)
                values (?, ?, ?, ?, ?)
                """,
                (
                    event["event_id"],
                    event["event_type"],
                    event["source"]["name"],
                    int(time.time()),
                    raw_body.decode("utf-8"),
                ),
            )
        except sqlite3.IntegrityError:
            return False
    return True


class AKEPHandler(BaseHTTPRequestHandler):
    server_version = "AKEPReceiver/0.1"

    def do_POST(self) -> None:
        if self.path != PATH:
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("content-length", "0"))
        if content_length <= 0 or content_length > MAX_BYTES:
            self.respond(413, {"error": "payload too large or empty"})
            return

        raw_body = self.rfile.read(content_length)
        ok, reason = verify_signature(self.headers, raw_body)
        if not ok:
            self.respond(400, {"error": reason})
            return

        try:
            event = json.loads(raw_body)
        except json.JSONDecodeError:
            self.respond(400, {"error": "invalid json"})
            return

        header_id = self.headers.get("webhook-id", "")
        if event.get("event_id") != header_id:
            self.respond(400, {"error": "webhook-id does not match event_id"})
            return
        if event.get("spec") != "akep.v1":
            self.respond(400, {"error": "unsupported spec"})
            return
        if "command" in event:
            self.respond(400, {"error": "AKEP events carry knowledge, not commands"})
            return

        inserted = store_event(event, raw_body)
        self.respond(202, {"accepted": True, "duplicate": not inserted})

    def log_message(self, fmt: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), AKEPHandler)
    print(f"AKEP receiver listening on http://{HOST}:{PORT}{PATH}")
    print(f"Inbox database: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()

