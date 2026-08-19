# Portable Agent Skills Reference

**Snapshot:** 2026-08-18, from https://agentskills.io/specification.

Use this profile when the skill must load across Agent Skills-compatible clients rather than depend on Claude Code extensions.

## Required frontmatter

| Field | Constraint |
|-------|------------|
| `name` | 1–64 lowercase letters, digits, and single hyphens. Must match the parent directory name. |
| `description` | 1–1,024 characters. State what the skill does and when to use it. |

Optional portable fields are `license`, `compatibility` (maximum 500 characters), `metadata` (a string-to-string map), and experimental `allowed-tools` support. Client support for tool grants varies.

Claude Code fields such as `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `context`, `agent`, `background`, `hooks`, `paths`, and `shell` are not portable.

## Validation

Run both checks when `skills-ref` is installed:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_skill.py --profile agentskills <skill-directory>
skills-ref validate <skill-directory>
```

The bundled validator checks repository-specific quality rules. `skills-ref` is authoritative for the portable format.
