#!/usr/bin/env python3
"""Validate agent skill directories against a runtime-specific profile.

Usage:
    validate_skill.py [--profile claude-code|agentskills] <skill-dir> [...]

Exit 0 = all skills pass (warnings allowed), 1 = any error, 2 = bad usage.
The parser intentionally supports the frontmatter shapes used by skills without
adding a PyYAML dependency. Portable Agent Skills should also be checked with
the upstream `skills-ref validate` command when it is available.
"""

import argparse
import re
import sys
from pathlib import Path


CLAUDE_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools",
    "disallowed-tools", "model", "effort", "context", "agent", "background",
    "hooks", "paths", "shell", "license", "compatibility", "metadata",
}
AGENT_SKILLS_KEYS = {
    "name", "description", "license", "compatibility", "metadata", "allowed-tools",
}
TRUE_VALUES = {"true", "yes", "on", "1"}
FALSE_VALUES = {"false", "no", "off", "0"}
DESC_TARGET = 250
CLAUDE_LISTING_CAP = 1536
AGENT_SKILLS_DESC_CAP = 1024
BODY_LINE_MAX = 500

SIDE_EFFECT_PATTERNS = [
    (r"git\s+push\b", "git push"),
    (r"gh\s+(?:pr|issue|release)\s+(?:create|merge|close|edit)\b", "gh mutation"),
    (r"rm\s+-rf?\b", "rm -r"),
    (r"git\s+reset\s+--hard\b", "git reset --hard"),
    (r"curl\b[^\n]*\s-X\s*(?:POST|PUT|DELETE|PATCH)\b", "mutating HTTP call"),
    (r"(?:npm|cargo)\s+publish\b|twine\s+upload\b", "package publish"),
]
COMMAND_PREFIX = re.compile(
    r"^\s*(?:(?:[-*]|\d+\.)\s+)?(?:on approval:\s*)?(?:run\s+)?",
    re.I,
)
GATE_RE = re.compile(
    r"\b(confirm|confirmation|approval|approve|wait for (?:the )?user|explicit permission)\b",
    re.I,
)
NEGATION_RE = re.compile(r"\b(?:do not|don't|never|must not|without running)\b", re.I)
PLACEHOLDER_RE = re.compile(
    r"\[(?:Your|Insert|Add|Enter|Describe|Specify|Choose|TODO)[^\]]*\]|\b\d{4}-XX-XX\b"
)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_frontmatter(text):
    """Return (mapping, body, error) for the supported YAML subset."""
    text = text.removeprefix("\ufeff")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not match:
        return None, text, "missing or unterminated frontmatter block"

    frontmatter = {}
    current_key = None
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s+", line):
            if not current_key:
                return None, match.group(2), f"orphaned nested frontmatter line: {line!r}"
            frontmatter[current_key] += " " + line.strip()
            continue
        key_value = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if not key_value:
            return None, match.group(2), f"unparseable frontmatter line: {line!r}"
        current_key = key_value.group(1)
        if current_key in frontmatter:
            return None, match.group(2), f"duplicate frontmatter key: {current_key!r}"
        frontmatter[current_key] = key_value.group(2).strip().strip('"').strip("'")
    return frontmatter, match.group(2), None


def boolean_value(value):
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return None


def named_arguments(raw):
    """Extract declared argument identifiers from scalar or simple list syntax."""
    if not raw:
        return []
    return re.findall(r"\b[a-z_][a-z0-9_-]*\b", raw, re.I)


def body_uses_arguments(body, frontmatter):
    if re.search(r"\$ARGUMENTS(?:\[\d+\])?|\$\d+\b", body):
        return True
    return any(
        re.search(rf"\${re.escape(name)}\b", body)
        for name in named_arguments(frontmatter.get("arguments", ""))
    )


def executable_side_effects(body):
    """Find command-like side effects while ignoring explanatory/negative prose."""
    hits = set()
    for raw_line in body.splitlines():
        line = raw_line.strip().strip("`")
        if not line or NEGATION_RE.search(line):
            continue
        commandish = COMMAND_PREFIX.sub("", line)
        for pattern, label in SIDE_EFFECT_PATTERNS:
            if re.match(pattern, commandish, re.I):
                hits.add(label)
    return sorted(hits)


def injected_commands(body):
    commands = []
    for line in body.splitlines():
        commands.extend(re.findall(r"!`([^`]+)`", line))
    return commands


def validate(skill_dir, profile="claude-code"):
    errors, warnings = [], []
    directory = Path(skill_dir).resolve()
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return [f"{directory}: no SKILL.md"], []

    text = skill_file.read_text(encoding="utf-8")
    frontmatter, body, error = parse_frontmatter(text)
    if error:
        return [f"{skill_file}: {error}"], []

    known_keys = CLAUDE_KEYS if profile == "claude-code" else AGENT_SKILLS_KEYS
    for key in frontmatter:
        if key not in known_keys:
            message = f"unknown {profile} frontmatter key `{key}`"
            (warnings if profile == "claude-code" else errors).append(message)

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    if profile == "agentskills":
        if not name:
            errors.append("Agent Skills requires `name`")
        elif not NAME_RE.fullmatch(name) or len(name) > 64:
            errors.append("`name` must be <=64 lowercase letters, digits, and single hyphens")
        elif name != directory.name:
            errors.append(f"Agent Skills requires name `{name}` to match directory `{directory.name}`")
        if not description:
            errors.append("Agent Skills requires a non-empty `description`")
        elif len(description) > AGENT_SKILLS_DESC_CAP:
            errors.append(f"description is {len(description)} chars; Agent Skills cap is {AGENT_SKILLS_DESC_CAP}")
        compatibility = frontmatter.get("compatibility", "")
        if compatibility and len(compatibility) > 500:
            errors.append("`compatibility` exceeds the Agent Skills 500-character cap")
    else:
        if not description:
            warnings.append("no `description`; Claude Code will use the body's first paragraph")
        else:
            combined = len(description) + len(frontmatter.get("when_to_use", ""))
            if combined > CLAUDE_LISTING_CAP:
                errors.append(
                    f"description+when_to_use is {combined} chars; Claude Code truncates at {CLAUDE_LISTING_CAP}"
                )
            disabled = boolean_value(frontmatter.get("disable-model-invocation", "false"))
            if len(description) > DESC_TARGET and disabled is not True:
                warnings.append(
                    f"description is {len(description)} chars; recommended ambient budget is ~{DESC_TARGET}"
                )
        if name and name != directory.name:
            warnings.append(
                f"frontmatter name `{name}` differs from directory `{directory.name}`; "
                "Claude Code uses the directory as the command name"
            )

    for key in ("disable-model-invocation", "user-invocable", "background"):
        if key in frontmatter and boolean_value(frontmatter[key]) is None:
            errors.append(f"`{key}` must be a recognized boolean value")

    if "$ARGUMENTS" in body and "argument-hint" not in frontmatter:
        warnings.append("body consumes $ARGUMENTS but frontmatter has no `argument-hint`")
    if "argument-hint" in frontmatter and not body_uses_arguments(body, frontmatter):
        warnings.append("`argument-hint` is declared but the body does not consume positional or named arguments")

    tools = frontmatter.get("allowed-tools", "")
    if re.search(r"(?:^|[,\s\[])(?:-\s*)?Bash(?:$|[,\s\]])", tools):
        warnings.append("`allowed-tools` grants unscoped `Bash`; scope the grant to required commands")

    disabled = boolean_value(frontmatter.get("disable-model-invocation", "false"))
    side_effects = executable_side_effects(body)
    if profile == "claude-code" and disabled is not True and side_effects and not GATE_RE.search(body):
        warnings.append(
            f"model-invocable skill contains ungated side-effect commands ({', '.join(side_effects)})"
        )

    for command in injected_commands(body):
        uses_untrusted_args = bool(re.search(r"\$ARGUMENTS|\$\d+\b", command)) or any(
            re.search(rf"\${re.escape(name)}\b", command)
            for name in named_arguments(frontmatter.get("arguments", ""))
        )
        if uses_untrusted_args:
            errors.append("dynamic command injection interpolates skill arguments; pass untrusted input safely instead")
        command_hits = [label for pattern, label in SIDE_EFFECT_PATTERNS if re.search(pattern, command, re.I)]
        if command_hits:
            errors.append(f"dynamic command injection performs a side effect ({', '.join(sorted(set(command_hits)))})")

    if frontmatter.get("context") == "fork" and not re.search(r"^\s*(?:\d+\.|- |## )", body, re.M):
        warnings.append("`context: fork` body lacks an explicit task or structured instructions")

    for link in re.findall(r"\]\((?!https?://|#|mailto:)([^)]+)\)", body):
        path = link.split("#", 1)[0].strip("<>")
        if path and not (directory / path).resolve().exists():
            errors.append(f"broken relative link: {link}")

    body_lines = body.count("\n") + 1
    if body_lines > BODY_LINE_MAX:
        warnings.append(f"body is {body_lines} lines (> {BODY_LINE_MAX}); move conditional detail to references")

    prose_without_fences = re.sub(r"```.*?```", "", text, flags=re.S)
    if PLACEHOLDER_RE.search(prose_without_fences):
        warnings.append("possible unfilled scaffold placeholder outside a fenced template")

    if re.search(r"(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{40,})", text):
        errors.append("possible credential in skill text")

    return errors, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("claude-code", "agentskills"), default="claude-code")
    parser.add_argument("skill_dirs", nargs="+")
    args = parser.parse_args(argv)

    failed = False
    for skill_dir in args.skill_dirs:
        errors, warnings = validate(skill_dir, args.profile)
        status = "FAIL" if errors else "PASS"
        print(f"\n{skill_dir} [{args.profile}]: {status}")
        for error in errors:
            print(f"  ERROR: {error}")
        for warning in warnings:
            print(f"  warning: {warning}")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
