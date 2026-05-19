#!/usr/bin/env python3
"""Repository validation script."""

from __future__ import annotations

import json
import py_compile
from pathlib import Path

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_json_files() -> None:
    for path in ROOT.rglob("*.json"):
        load_json(path)
        print(f"json ok: {path.relative_to(ROOT)}")


def validate_event_example() -> None:
    events = [
        load_json(ROOT / "examples/events/sense2ai-task-completed.json"),
    ]
    for event in events:
        require(str(event["spec"]).startswith("akep.v1"), "event spec must be akep.v1")
        require(event["event_id"].startswith("evt_"), "event_id should start with evt_")
        require(event["subject"], "event subject must not be empty")
        require(event["source"].get("producer_id"), "event source should include producer_id")
        require(event["routing"]["resume_policy"] in {"append_only", "resume_if_waiting", "resume_immediately", "never"}, "known resume policy required")
        require("command" not in event, "event must not include commands")
    event = events[0]
    require(event["event_type"] == "knowledge.acquired", "Sense2AI completion maps to knowledge.acquired")
    require(event["source"]["name"] == "sense2ai", "source name should be sense2ai")
    require(event["knowledge"]["kind"] == "observation", "Sense2AI completion should be observation knowledge")
    require(event["routing"]["resume_policy"] == "resume_if_waiting", "Sense2AI completion should resume if waiting")
    print("event example ok")


def validate_subscription_example() -> None:
    sub = load_json(ROOT / "examples/events/subscription.json")
    require(sub["spec"] == "akep.v1", "subscription spec must be akep.v1")
    require("knowledge.acquired" in sub["event_types"], "subscription should include knowledge.acquired")
    require(sub["delivery"]["type"] == "webhook", "example delivery should be webhook")
    require(sub["security"]["accepted_producer_ids"], "subscription should restrict producer ids")
    print("subscription example ok")


def validate_skill() -> None:
    skill = ROOT / "skills/akep/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    require(text.startswith("---\n"), "skill must start with YAML frontmatter")
    require("name: akep" in text, "skill frontmatter must name akep")
    require("description:" in text, "skill frontmatter must include description")
    require("Standard Webhooks" in text, "skill should mention Standard Webhooks")
    print("skill ok")


def validate_python_examples() -> None:
    for path in (ROOT / "examples/python").glob("*.py"):
        py_compile.compile(str(path), doraise=True)
        print(f"python syntax ok: {path.relative_to(ROOT)}")
    py_compile.compile(str(ROOT / "scripts/validate_repo.py"), doraise=True)


def validate_event_minimal(event: dict) -> tuple[bool, str]:
    required = {"spec", "event_id", "event_type", "occurred_at", "source", "subject", "knowledge", "routing"}
    missing = required - set(event)
    if missing:
        return False, f"missing required fields: {sorted(missing)}"
    if "command" in event:
        return False, "command key is not allowed"
    if not isinstance(event.get("subject"), dict) or not event["subject"]:
        return False, "subject must be a non-empty object"
    if not isinstance(event.get("source"), dict) or not event["source"].get("producer_id"):
        return False, "source.producer_id is required for examples"
    if event["source"].get("type") not in {"publisher", "tool", "agent", "human", "system", "webhook", "queue", "sensor", "other"}:
        return False, "source.type is not recognized"
    if event.get("routing", {}).get("resume_policy") not in {"never", "append_only", "resume_if_waiting", "resume_immediately"}:
        return False, "routing.resume_policy is not recognized"
    return True, ""


def validate_schemas() -> None:
    if not HAS_JSONSCHEMA:
        print("jsonschema package not found. Running built-in conformance fallback.")
        valid_event = load_json(ROOT / "examples/events/conformance/valid_event.json")
        ok, reason = validate_event_minimal(valid_event)
        require(ok, f"valid conformance event failed fallback validation: {reason}")
        invalid_events = [
            ROOT / "examples/events/conformance/invalid_no_subject.json",
            ROOT / "examples/events/conformance/invalid_empty_subject.json",
            ROOT / "examples/events/conformance/invalid_command.json",
        ]
        for path in invalid_events:
            ok, _ = validate_event_minimal(load_json(path))
            require(not ok, f"invalid conformance event passed fallback validation: {path.name}")
            print(f"  Built-in conformance failed as expected: {path.relative_to(ROOT)}")
        return

    print("Running JSON Schema conformance checks...")
    event_schema = load_json(ROOT / "schemas/akep-event-v1.schema.json")
    sub_schema = load_json(ROOT / "schemas/akep-subscription-v1.schema.json")

    # 1. Validate valid events
    valid_events = [
        ROOT / "examples/events/sense2ai-task-completed.json",
        ROOT / "examples/events/conformance/valid_event.json"
    ]
    for path in valid_events:
        event = load_json(path)
        jsonschema.validate(instance=event, schema=event_schema)
        print(f"  Schema validation PASSED: {path.relative_to(ROOT)}")

    # 2. Validate valid subscriptions
    valid_subs = [
        ROOT / "examples/events/subscription.json",
        ROOT / "examples/events/relay-subscription.json"
    ]
    for path in valid_subs:
        sub = load_json(path)
        jsonschema.validate(instance=sub, schema=sub_schema)
        print(f"  Schema validation PASSED: {path.relative_to(ROOT)}")

    # 3. Validate invalid event conformance test cases (expecting failures)
    invalid_events = [
        (ROOT / "examples/events/conformance/invalid_no_subject.json", "missing subject"),
        (ROOT / "examples/events/conformance/invalid_empty_subject.json", "empty subject"),
        (ROOT / "examples/events/conformance/invalid_command.json", "command key present")
    ]
    for path, description in invalid_events:
        event = load_json(path)
        try:
            jsonschema.validate(instance=event, schema=event_schema)
            raise AssertionError(f"Expected schema validation error for {path.name} ({description}), but it passed.")
        except jsonschema.ValidationError:
            print(f"  Schema validation FAILED as expected: {path.relative_to(ROOT)} ({description})")


def main() -> None:
    validate_json_files()
    validate_event_example()
    validate_subscription_example()
    validate_skill()
    validate_python_examples()
    validate_schemas()
    print("AKEP repo validation complete")


if __name__ == "__main__":
    main()
