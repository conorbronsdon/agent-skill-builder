# Changelog

## Unreleased

- Split validation into `claude-code` and `agentskills` profiles, including portable required fields, name-directory matching, and profile-specific description limits.
- Fix named-argument detection and support current Claude Code boolean aliases plus the `background` field.
- Reject argument interpolation and mutating commands inside dynamic context injection.
- Replace the one-way spec check with a bidirectional field comparison; network and parser failures now return a distinct non-zero result.
- Refresh the Claude Code snapshot and add a pinned portable Agent Skills reference.
- Add 18 adversarial unit tests with paired positive and negative controls, plus a portable CLI example and CI coverage.
- Refactor the builder around reference, task, and tool-backed skill shapes; generation now follows the user's requested draft-versus-write scope.
- Preserve the existing overwrite guard: never replace an installed `SKILL.md` without explicit approval.

## 0.1.0 — 2026-07-13

Initial extraction from [claude-code-skills](https://github.com/conorbronsdon/claude-code-skills)' `skill-creator`, hardened per review feedback (Ed Harrod's LinkedIn critique of stale skill generators + a GPT 5.6 architecture review):

- SKILL.md with three modes (`new` / `review` / `migrate`) and invocation-control-first design flow
- `references/claude-code-frontmatter.md` — pinned, dated spec snapshot; **generation never mutates it** (warn-and-continue when stale)
- `scripts/validate_skill.py` — machine-checkable version of the quality checklist
- `scripts/check_spec_freshness.py` + weekly `spec-drift` CI that opens an issue on upstream spec changes
- `test` CI validating the repo's own SKILL.md and both examples
- Examples: minimal (dynamic context injection) and tool-using (user-only commit skill)
