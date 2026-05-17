#!/usr/bin/env python3
"""Sign and send an AKEP event using Standard Webhooks-style headers."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request


def secret_bytes() -> bytes:
    secret = os.environ.get("AKEP_WEBHOOK_SECRET")
    if not secret:
        raise SystemExit("AKEP_WEBHOOK_SECRET is required")
    if secret.startswith("whsec_"):
        return base64.b64decode(secret.removeprefix("whsec_"))
    return secret.encode("utf-8")


def signature(event_id: str, timestamp: str, raw_body: bytes) -> str:
    signed = b".".join([event_id.encode(), timestamp.encode(), raw_body])
    digest = hmac.new(secret_bytes(), signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--event", required=True)
    args = parser.parse_args()

    with open(args.event, "r", encoding="utf-8") as fh:
        event = json.load(fh)

    raw_body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    event_id = event["event_id"]
    timestamp = str(int(time.time()))
    headers = {
        "content-type": "application/json",
        "webhook-id": event_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": signature(event_id, timestamp, raw_body),
    }

    request = urllib.request.Request(args.url, data=raw_body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        print(response.status, response.read().decode("utf-8"))


if __name__ == "__main__":
    main()

