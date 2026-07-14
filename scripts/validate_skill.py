#!/usr/bin/env python3
"""Validate an agent skill directory against the skill-builder checklist.

Usage: validate_skill.py <skill-dir> [<skill-dir> ...]

Exit 0 = all skills pass (warnings allowed), 1 = any error.
No dependencies beyond the standard library; the frontmatter parser is
deliberately minimal (flat key: value pairs), which covers real skill files.
"""

import re
import sys
from pathlib import Path

KNOWN_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable", "allowed-tools",
    "disallowed-tools", "model", "effort", "context", "agent", "hooks",
    "paths", "shell",
    # agentskills.io / common metadata keys that are harmless extensions
    "version", "license", "compatibility", "metadata",
}

DESC_TARGET = 250       # recommended budget
DESC_LISTING_CAP = 1536  # hard truncation in the skill listing
BODY_LINE_MAX = 500

SIDE_EFFECT_PATTERNS = [
    (r"\bgit push\b", "git push"),
    (r"\bgh (pr|issue|release) (create|merge|close|edit)\b", "gh mutation"),
    (r"\brm -rf?\b", "rm -r"),
    (r"\bgit reset --hard\b", "git reset --hard"),
    (r"\bcurl\b[^\n]*-X *(POST|PUT|DELETE|PATCH)", "mutating HTTP call"),
    (r"\bnpm publish\b|\bcargo publish\b|\btwine upload\b", "package publish"),
]

PLACEHOLDER_RE = re.compile(
    r"\[(Your|Insert|Add|Enter|Describe|Specify|Choose|TODO)[^\]]*\]|\b\d{4}-XX-XX\b"
)


def parse_frontmatter(text):
    """Return (dict, body, error). Minimal flat YAML: key: value lines."""
    if not text.startswith("---"):
        return None, text, "no frontmatter block"
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return None, text, "unterminated frontmatter block"
    fm = {}
    current_key = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if re.match(r"^\s+", line) and current_key:
            # continuation / nested value — keep raw, we only need presence
            fm[current_key] = str(fm[current_key]) + " " + line.strip()
            continue
        kv = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if not kv:
            return None, m.group(2), f"unparseable frontmatter line: {line!r}"
        current_key = kv.group(1)
        val = kv.group(2).strip().strip('"').strip("'")
        fm[current_key] = val
    return fm, m.group(2), None


def validate(skill_dir):
    errors, warnings = [], []
    d = Path(skill_dir).resolve()
    f = d / "SKILL.md"
    if not f.is_file():
        return [f"{d}: no SKILL.md"], []
    text = f.read_text(encoding="utf-8")
    fm, body, err = parse_frontmatter(text)
    if err:
        return [f"{f}: {err}"], []

    # --- frontmatter checks ---
    for k in fm:
        if k not in KNOWN_KEYS:
            warnings.append(f"unknown frontmatter key `{k}` (typo, or a spec change?)")

    desc = fm.get("description", "")
    if not desc:
        warnings.append("no `description` — the model can't decide when to use this skill")
    else:
        combined = len(desc) + len(fm.get("when_to_use", ""))
        if combined > DESC_LISTING_CAP:
            errors.append(
                f"description+when_to_use is {combined} chars — the listing truncates at {DESC_LISTING_CAP}"
            )
        elif len(desc) > DESC_TARGET and fm.get("disable-model-invocation") != "true":
            warnings.append(
                f"description is {len(desc)} chars; recommended budget is ~{DESC_TARGET} "
                "(it loads into every session — move detail to the body)"
            )

    name = fm.get("name")
    if name and name != d.name:
        warnings.append(
            f"frontmatter name `{name}` != directory `{d.name}` — the directory name is the "
            "command; `name` is only a display label (fine if intentional)"
        )

    # --- name format: nudge toward the command-name convention ---
    # The directory name IS the command. Lowercase alphanumerics joined by single
    # hyphens is the convention; capitals/underscores still produce a working
    # command, just an unconventional one, so this is a warning, not an error.
    # A space is the one case that actually breaks invocation — flagged louder.
    NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    for label, value in (("directory name", d.name), ("frontmatter name", name)):
        if value and not NAME_RE.match(value):
            if " " in value:
                errors.append(
                    f"{label} `{value}` contains a space — the command won't invoke "
                    "as one token; use lowercase-hyphenated (e.g. `deploy-staging`)"
                )
            else:
                warnings.append(
                    f"{label} `{value}` is unconventional — the norm is lowercase "
                    "alphanumerics and single hyphens (e.g. `deploy-staging`); "
                    "capitals/underscores work but read oddly as a `/command`"
                )

    # --- arguments ---
    uses_args = bool(re.search(r"\$ARGUMENTS|\$\d|\$[a-z_]+\b(?=.*arguments:)", body))
    if "$ARGUMENTS" in body and "argument-hint" not in fm:
        warnings.append("body consumes $ARGUMENTS but frontmatter has no `argument-hint`")
    if "argument-hint" in fm and not uses_args:
        warnings.append(
            "`argument-hint` declared but the body never consumes $ARGUMENTS/$N "
            "(args still arrive as an appended `ARGUMENTS:` line, but wiring them is clearer)"
        )

    # --- tool grants ---
    tools = fm.get("allowed-tools", "")
    if re.search(r"(^|[,\s])Bash($|[,\s])", tools):
        warnings.append("`allowed-tools` grants unscoped `Bash` — scope it, e.g. Bash(git add *)")

    # --- side effects vs invocation control ---
    if fm.get("disable-model-invocation") != "true":
        hits = sorted({label for pat, label in SIDE_EFFECT_PATTERNS if re.search(pat, body)})
        if hits:
            warnings.append(
                f"model-invocable skill contains side-effect commands ({', '.join(hits)}) — "
                "add a confirmation gate in the body or set `disable-model-invocation: true`"
            )

    # --- fork sanity ---
    if fm.get("context") == "fork" and not re.search(r"^\s*(\d+\.|- \[?|\#\# )", body, re.M):
        warnings.append(
            "`context: fork` but the body has no steps/structure — a forked subagent "
            "needs an explicit task, not reference prose"
        )

    # --- links and referenced files ---
    for link in re.findall(r"\]\((?!https?://|#|mailto:)([^)]+)\)", body):
        target = (d / link.split("#")[0]).resolve()
        if not target.exists():
            errors.append(f"broken relative link: {link}")

    # --- body hygiene ---
    n_lines = body.count("\n") + 1
    if n_lines > BODY_LINE_MAX:
        warnings.append(f"body is {n_lines} lines (> {BODY_LINE_MAX}) — move reference material to supporting files")
    for ph in PLACEHOLDER_RE.findall(text):
        # tolerate placeholders inside fenced code blocks (templates are legitimate)
        warnings.append(f"possible unfilled placeholder: {ph!r} (fine if it's a template example)")
        break  # one warning is enough

    if re.search(r"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{40,})", text):
        errors.append("possible credential in skill text")

    return errors, warnings


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    failed = False
    for arg in argv[1:]:
        errors, warnings = validate(arg)
        status = "FAIL" if errors else "PASS"
        print(f"\n{arg}: {status}")
        for e in errors:
            print(f"  ERROR: {e}")
        for w in warnings:
            print(f"  warning: {w}")
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
