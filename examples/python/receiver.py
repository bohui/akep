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
from typing import Optional
from urllib.parse import parse_qs, urlparse


HOST = os.environ.get("AKEP_HOST", "127.0.0.1")
PORT = int(os.environ.get("AKEP_PORT", "8787"))
PATH = os.environ.get("AKEP_PATH", "/akep/events")
DISCOVERY_PATH = "/.well-known/akep.json"
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


def expected_signature_value(event_id: str, timestamp: str, raw_body: bytes) -> str:
    signed = b".".join([event_id.encode(), timestamp.encode(), raw_body])
    digest = hmac.new(secret_bytes(), signed, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def matches_subscription(event: dict, subscription: dict, headers) -> tuple[bool, str]:
    # Check event type
    event_type = event.get("event_type")
    allowed_types = subscription.get("event_types", [])
    if event_type not in allowed_types:
        return False, f"event_type '{event_type}' not allowed by subscription"

    # Check dotted filters
    filters = subscription.get("filters", {})
    for path, filter_val in filters.items():
        actual_val = event
        for part in path.split("."):
            if isinstance(actual_val, dict) and part in actual_val:
                actual_val = actual_val[part]
            else:
                actual_val = None
                break
        
        if isinstance(filter_val, list):
            if actual_val not in filter_val:
                return False, f"filter mismatch: '{path}' value '{actual_val}' not in {filter_val}"
        else:
            if actual_val != filter_val:
                return False, f"filter mismatch: '{path}' value '{actual_val}' != '{filter_val}'"

    # Check security constraints
    security = subscription.get("security", {})

    # 1. accepted_source_names
    source_name = event.get("source", {}).get("name")
    accepted_sources = security.get("accepted_source_names")
    if accepted_sources is not None and source_name not in accepted_sources:
        return False, f"source.name '{source_name}' not in accepted_source_names"

    # 2. accepted_producer_ids
    producer_id = event.get("source", {}).get("producer_id")
    accepted_producers = security.get("accepted_producer_ids")
    if accepted_producers is not None and producer_id not in accepted_producers:
        return False, f"source.producer_id '{producer_id}' not in accepted_producer_ids"

    # 3. signature_key_ids
    key_id = headers.get("webhook-signature-key-id")
    accepted_key_ids = security.get("signature_key_ids")
    if accepted_key_ids is not None and key_id and key_id not in accepted_key_ids:
        return False, f"webhook-signature-key-id '{key_id}' not in signature_key_ids"

    return True, ""


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

    expected = expected_signature_value(event_id, timestamp, raw_body)
    valid = False
    for part in signature.split():
        try:
            algorithm, value = part.split(",", 1)
        except ValueError:
            continue
        if algorithm == "v1" and hmac.compare_digest(expected, value):
            valid = True
            break
    if not valid:
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
              processed_at integer,
              ack_status text,
              ack_reason text,
              raw_json text not null
            )
            """
        )
        columns = {row[1] for row in db.execute("pragma table_info(events)")}
        for column, definition in {
            "processed_at": "integer",
            "ack_status": "text",
            "ack_reason": "text",
        }.items():
            if column not in columns:
                db.execute(f"alter table events add column {column} {definition}")


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


def parse_cursor(cursor: str) -> int:
    if not cursor:
        return 0
    if cursor.startswith("cur_"):
        cursor = cursor.removeprefix("cur_")
    try:
        return max(0, int(cursor))
    except ValueError:
        return 0


def replay_events(cursor: str, limit: int) -> dict:
    offset = parse_cursor(cursor)
    limit = max(1, min(limit, 1000))
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """
            select rowid, raw_json
            from events
            where rowid > ?
            order by rowid asc
            limit ?
            """,
            (offset, limit + 1),
        ).fetchall()
    page = rows[:limit]
    events = [json.loads(raw_json) for _, raw_json in page]
    next_cursor = f"cur_{page[-1][0]}" if page else f"cur_{offset}"
    return {"events": events, "next_cursor": next_cursor, "has_more": len(rows) > limit}


def ack_event(event_id: str, payload: dict) -> bool:
    status = payload.get("status", "stored")
    reason = payload.get("reason", "")
    if status not in {"stored", "applied", "rejected"}:
        status = "stored"
    with sqlite3.connect(DB_PATH) as db:
        cur = db.execute(
            """
            update events
            set processed_at = ?, ack_status = ?, ack_reason = ?
            where event_id = ?
            """,
            (int(time.time()), status, reason, event_id),
        )
        return cur.rowcount > 0


def task_state(task_id: str) -> Optional[dict]:
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "select event_id, event_type, received_at, raw_json from events order by rowid asc"
        ).fetchall()
    matched = []
    artifacts = []
    updated_at = None
    status = "unknown"
    for event_id, event_type, received_at, raw_json in rows:
        event = json.loads(raw_json)
        if event.get("subject", {}).get("task_id") != task_id:
            continue
        matched.append(event_id)
        updated_at = received_at
        uri = event.get("knowledge", {}).get("uri")
        if uri:
            artifacts.append(
                {
                    "uri": uri,
                    "content_type": event.get("knowledge", {}).get("content_type"),
                }
            )
        if event_type in {"knowledge.acquired", "tool.completed", "human.approved"}:
            status = "completed"
        elif event_type in {"tool.failed", "human.rejected"}:
            status = "failed"
        elif event_type == "human.review_required":
            status = "input_required"
    if not matched:
        return None
    return {
        "task_id": task_id,
        "status": status,
        "updated_at": updated_at,
        "events": matched,
        "artifacts": artifacts,
    }


class AKEPHandler(BaseHTTPRequestHandler):
    server_version = "AKEPReceiver/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == DISCOVERY_PATH:
            self.respond(
                200,
                {
                    "spec": "akep.v1",
                    "service_name": "AKEP Python reference receiver",
                    "endpoints": {
                        "events": PATH,
                        "replay": PATH,
                        "wait": f"{PATH}/wait",
                        "ack": f"{PATH}/{{event_id}}/ack",
                        "tasks": "/akep/tasks/{task_id}",
                    },
                    "delivery_profiles": ["webhook", "replay_inbox", "task_state"],
                    "signature_algorithms": ["v1"],
                    "retention": {"minimum_unacked_seconds": 604800},
                },
            )
            return

        query = parse_qs(parsed.query)
        if parsed.path == PATH:
            limit = int(query.get("limit", ["100"])[0])
            self.respond(200, replay_events(query.get("cursor", [""])[0], limit))
            return

        if parsed.path == f"{PATH}/wait":
            timeout = max(1, min(int(query.get("timeout_seconds", ["30"])[0]), 60))
            cursor = query.get("cursor", [""])[0]
            deadline = time.time() + timeout
            while time.time() < deadline:
                page = replay_events(cursor, 100)
                if page["events"]:
                    self.respond(200, page)
                    return
                time.sleep(1)
            self.send_response(204)
            self.end_headers()
            return

        if parsed.path.startswith("/akep/tasks/"):
            task_id = parsed.path.removeprefix("/akep/tasks/")
            state = task_state(task_id)
            if state is None:
                self.respond(404, {"error": "unknown task"})
            else:
                self.respond(200, state)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith(f"{PATH}/") and parsed.path.endswith("/ack"):
            event_id = parsed.path.removeprefix(f"{PATH}/").removesuffix("/ack")
            content_length = int(self.headers.get("content-length", "0"))
            raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                payload = json.loads(raw_body)
            except json.JSONDecodeError:
                payload = {}
            if ack_event(event_id, payload):
                self.respond(200, {"acked": True, "event_id": event_id})
            else:
                self.respond(404, {"error": "unknown event"})
            return

        if parsed.path != PATH:
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
        if not str(event.get("spec", "")).startswith("akep.v1"):
            self.respond(400, {"error": "unsupported spec"})
            return
        if not event.get("subject"):
            self.respond(400, {"error": "subject is required"})
            return
        if "command" in event:
            self.respond(400, {"error": "AKEP events carry knowledge, not commands"})
            return

        # Load and verify subscription filters
        sub_path = os.environ.get("AKEP_SUBSCRIPTION_PATH", "examples/events/subscription.json")
        if os.path.exists(sub_path):
            try:
                with open(sub_path, "r", encoding="utf-8") as fh:
                    subscription = json.load(fh)
                ok_sub, reason_sub = matches_subscription(event, subscription, self.headers)
                if not ok_sub:
                    self.respond(422, {"error": f"subscription mismatch: {reason_sub}"})
                    return
            except Exception as e:
                print(f"Error checking subscription filters: {e}")

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
