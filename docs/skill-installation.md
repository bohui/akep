# Installing the AKEP Skill

The bundled skill lives at [skills/akep/SKILL.md](../skills/akep/SKILL.md).

It is intentionally AgentSkills-compatible: a directory named `akep` with one required `SKILL.md` file and optional references.

## Claude Code

Personal install:

```bash
mkdir -p ~/.claude/skills
cp -R /Users/victor/vh_work/akep/skills/akep ~/.claude/skills/akep
```

Project install:

```bash
mkdir -p .claude/skills
cp -R /Users/victor/vh_work/akep/skills/akep .claude/skills/akep
```

Use it by asking a request that matches the skill description, for example:

```text
Set up a Sense2AI AKEP receiver on port 8787.
```

## OpenClaw

Shared install:

```bash
mkdir -p ~/.openclaw/skills
cp -R /Users/victor/vh_work/akep/skills/akep ~/.openclaw/skills/akep
```

Workspace install:

```bash
mkdir -p skills
cp -R /Users/victor/vh_work/akep/skills/akep skills/akep
```

Use it by asking a request that matches the skill description, for example:

```text
Inspect the last failed AKEP event and explain whether it should resume the waiting task.
```

## What the Skill Does

The skill helps an agent:

- create or inspect a local AKEP receiver
- verify Standard Webhooks signatures
- store events in a durable inbox
- debug subscription filters
- replay events
- map Sense2AI events into AKEP
- decide whether a verified event can resume a task
