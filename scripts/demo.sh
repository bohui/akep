#!/usr/bin/env bash
# AKEP one-command demo.
#
# Starts the Python receiver in the background, signs and sends the example
# Sense2.ai event, prints the resulting durable inbox row, then cleans up.
#
# Usage: scripts/demo.sh
# Requires: python3, sqlite3.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export AKEP_WEBHOOK_SECRET="${AKEP_WEBHOOK_SECRET:-dev-secret}"
export AKEP_HOST="${AKEP_HOST:-127.0.0.1}"
export AKEP_PORT="${AKEP_PORT:-8787}"
export AKEP_PATH="${AKEP_PATH:-/akep/events}"
export AKEP_INBOX_DB="${AKEP_INBOX_DB:-.akep/inbox.db}"

# Use a unique event_id every run so the demo doesn't 200-duplicate after
# the first invocation.
EVENT_SRC="examples/events/sense2ai-task-completed.json"
EVENT_TMP="$(mktemp -t akep-demo.XXXXXX.json)"
EVENT_ID="evt_demo_$(date +%s)_$$"
python3 - "$EVENT_SRC" "$EVENT_TMP" "$EVENT_ID" <<'PY'
import json, sys
src, dst, event_id = sys.argv[1], sys.argv[2], sys.argv[3]
with open(src) as fh:
    event = json.load(fh)
event["event_id"] = event_id
if "links" in event:
    event.pop("links")
with open(dst, "w") as fh:
    json.dump(event, fh)
PY

cleanup() {
  if [[ -n "${RECEIVER_PID:-}" ]] && kill -0 "$RECEIVER_PID" 2>/dev/null; then
    kill "$RECEIVER_PID" 2>/dev/null || true
    wait "$RECEIVER_PID" 2>/dev/null || true
  fi
  rm -f "$EVENT_TMP"
}
trap cleanup EXIT

echo "→ starting AKEP receiver on http://${AKEP_HOST}:${AKEP_PORT}${AKEP_PATH}"
python3 examples/python/receiver.py >/tmp/akep-receiver.log 2>&1 &
RECEIVER_PID=$!

# Wait for the receiver to bind.
for _ in $(seq 1 30); do
  if (echo > "/dev/tcp/${AKEP_HOST}/${AKEP_PORT}") 2>/dev/null; then
    break
  fi
  sleep 0.1
done

echo "→ signing and sending example event (event_id=${EVENT_ID})"
python3 examples/python/sign_event.py \
  --url "http://${AKEP_HOST}:${AKEP_PORT}${AKEP_PATH}" \
  --event "$EVENT_TMP"

echo "→ durable inbox row:"
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 -header -column "$AKEP_INBOX_DB" \
    "select event_id, event_type, source_name, received_at from events order by received_at desc limit 1;"
else
  python3 - "$AKEP_INBOX_DB" <<'PY'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
row = db.execute(
    "select event_id, event_type, source_name, received_at "
    "from events order by received_at desc limit 1"
).fetchone()
print(f"{'event_id':<48}  {'event_type':<24}  {'source_name':<16}  received_at")
print("-" * 100)
if row:
    print(f"{row[0]:<48}  {row[1]:<24}  {row[2]:<16}  {row[3]}")
PY
fi

echo
echo "✓ demo complete. Inbox database: ${AKEP_INBOX_DB}"
echo "  Receiver log: /tmp/akep-receiver.log"
