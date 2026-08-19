---
name: agent-skill-builder
description: Builds, reviews, or migrates agent skills. Use when creating a SKILL.md, auditing an existing skill, or converting a legacy Claude Code command.
argument-hint: "[new <description> | review <path> | migrate <path>]"
compatibility: Designed for Claude Code 2.1.218+; can generate portable Agent Skills.
---

# Agent Skill Builder

Produce a ready-to-use skill from a plain-language request. Preserve the user's runtime, scope, and requested level of implementation.

## Select the mode

Parse `$ARGUMENTS`; default to `new` when it contains a description.

- `new <description>`: create or draft a skill.
- `review <path>`: report actionable findings and run validation. Do not rewrite unless asked.
- `migrate <path>`: convert a legacy `.claude/commands/*.md` file into a skill directory while preserving behavior.

## Establish the contract

Infer what is already clear. Ask only when a missing choice would materially change the result.

1. Choose the runtime:
   - Claude Code (default): read [the Claude Code reference](references/claude-code-frontmatter.md).
   - Portable Agent Skills: read [the portable reference](references/portable-agent-skills.md) and omit Claude-only fields.
2. Read the host repository's applicable instruction files (`AGENTS.md`, `CLAUDE.md`, or equivalents) and inspect existing skills. Match local conventions and avoid duplicate capabilities.
3. Identify inputs, outputs, required resources, and the destination directory.
4. Classify the skill:
   - Reference: standing domain rules or conventions.
   - Task: a bounded workflow with a defined result and stopping condition.
   - Tool-backed: a task that benefits from repeatable scripts or narrowly scoped tool grants.

## Design decisions

Include only fields and instructions that change behavior.

- Name: lowercase letters, digits, and hyphens. Portable skills require the frontmatter name to match the directory.
- Description: lead with the capability and include phrases users would naturally say. Keep model-visible descriptions near 250 characters when practical.
- Invocation (Claude Code only):
  - Use `disable-model-invocation: true` when timing must remain user-controlled, especially publishing, deploying, sending, deleting, or other consequential mutations.
  - Use `user-invocable: false` for background knowledge users should not run directly.
  - Leave both enabled when natural-language discovery is useful. Invocation control never replaces approval immediately before an external or hard-to-reverse mutation.
- Arguments (Claude Code only): pair `argument-hint` with `$ARGUMENTS`, positional `$N`, or names declared in `arguments:`.
- Forking (Claude Code only): use `context: fork` for self-contained tasks. Add `background: false` only when the invoking turn needs the result immediately.
- Tool grants: `allowed-tools` pre-approves tools; it does not restrict the remaining pool. Grant only commands the workflow actually needs.
- Dynamic injection (Claude Code only): use `!` commands for bounded read-only context. Never interpolate skill arguments into shell commands, and never perform mutations during preprocessing.
- Resources: keep shared instructions in `SKILL.md`; put conditional details in `references/`, repeated deterministic mechanics in `scripts/`, and output material in `assets/`.

Do not force every skill into the same outline. Reference skills usually need concise standing rules. Task skills need an objective, workflow, stopping conditions, and output. Tool-backed skills also need execution and failure behavior.

## Implement or review

- For `new`, draft only when the user asked for a draft. When the user asked to create or install the skill, write it and verify it.
- Before writing, check whether `<destination>/<name>/SKILL.md` exists. Do not overwrite it without explicit approval.
- For `review`, tie every finding to an observable behavior, specification rule, or concrete maintenance risk. Separate runtime errors from optional improvements.
- For `migrate`, preserve command arguments and behavior, move substantial supporting material beside the new `SKILL.md`, then validate the chosen runtime.
- Add scripts or references only when they provide a concrete reusable benefit. Remove scaffold placeholders before delivery.

## Validate

Run the bundled validator with the selected profile:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_skill.py --profile claude-code <skill-directory>
python3 ${CLAUDE_SKILL_DIR}/scripts/validate_skill.py --profile agentskills <skill-directory>
```

For portable skills, also run `skills-ref validate <skill-directory>` when available. Report which checks ran and their exact PASS/FAIL results.

Test behavior in a fresh session when practical:

- Direct invocation with realistic input.
- A natural-language request that should activate a model-invocable skill.
- A near-miss that should not activate it.
- One mutation that should make a meaningful validator or workflow check fail, followed by restoration of the valid input.

For high-value skills, offer the official `skill-creator` eval loop for with-skill/without-skill comparisons and trigger tuning.

## Deliver

Show the created or changed files, validator and test output, and any unresolved warnings. If files were written, do not ask whether to save them afterward. Ask for the next external action only when it requires separate authorization.
