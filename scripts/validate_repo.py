#!/usr/bin/env python3
"""Lightweight repository validation without third-party dependencies."""

from __future__ import annotations

import json
import py_compile
from pathlib import Path


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
    event = load_json(ROOT / "examples/events/sense2ai-task-completed.json")
    require(event["spec"] == "akep.v1", "event spec must be akep.v1")
    require(event["event_id"].startswith("evt_"), "event_id should start with evt_")
    require(event["event_type"] == "knowledge.acquired", "Sense2AI completion maps to knowledge.acquired")
    require(event["source"]["name"] == "sense2ai", "source name should be sense2ai")
    require(event["knowledge"]["kind"] == "observation", "Sense2AI completion should be observation knowledge")
    require(event["routing"]["resume_policy"] == "resume_if_waiting", "Sense2AI completion should resume if waiting")
    require("command" not in event, "event must not include commands")
    print("event example ok")


def validate_subscription_example() -> None:
    sub = load_json(ROOT / "examples/events/subscription.json")
    require(sub["spec"] == "akep.v1", "subscription spec must be akep.v1")
    require("knowledge.acquired" in sub["event_types"], "subscription should include knowledge.acquired")
    require(sub["delivery"]["type"] == "webhook", "example delivery should be webhook")
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


def main() -> None:
    validate_json_files()
    validate_event_example()
    validate_subscription_example()
    validate_skill()
    validate_python_examples()
    print("AKEP repo validation complete")


if __name__ == "__main__":
    main()

