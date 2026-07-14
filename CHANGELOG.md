# Changelog

## Unreleased

Mechanical guardrail from a second round of Ed Harrod's feedback:

- SKILL.md step 5 gains a pre-write guard: check the target path is clear and confirm before overwriting an existing `SKILL.md`, never clobber silently (`review` mode is for improving one that exists).

(No name-format check: any directory name resolves to a working command, so spelling/casing is cosmetic. The validator flags what breaks or misleads, not style.)

## 0.1.0 — 2026-07-13

Initial extraction from [claude-code-skills](https://github.com/conorbronsdon/claude-code-skills)' `skill-creator`, hardened per review feedback (Ed Harrod's LinkedIn critique of stale skill generators + a GPT 5.6 architecture review):

- SKILL.md with three modes (`new` / `review` / `migrate`) and invocation-control-first design flow
- `references/claude-code-frontmatter.md` — pinned, dated spec snapshot; **generation never mutates it** (warn-and-continue when stale)
- `scripts/validate_skill.py` — machine-checkable version of the quality checklist
- `scripts/check_spec_freshness.py` + weekly `spec-drift` CI that opens an issue on upstream spec changes
- `test` CI validating the repo's own SKILL.md and both examples
- Examples: minimal (dynamic context injection) and tool-using (user-only commit skill)
