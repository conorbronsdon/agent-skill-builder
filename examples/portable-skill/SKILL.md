---
name: portable-skill
description: Reviews a SKILL.md for portable structure. Use when checking a skill intended for multiple Agent Skills-compatible clients.
compatibility: Requires access to the target skill directory.
---

Review the target skill against the portable Agent Skills specification.

- Verify that `name` matches the parent directory.
- Verify that the description states what the skill does and when to use it.
- Identify client-specific fields or instructions that reduce portability.
- Report errors separately from optional improvements.
