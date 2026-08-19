#!/usr/bin/env python3
"""Compare the pinned Claude Code frontmatter snapshot with the live docs.

Checks snapshot age and compares the complete frontmatter field set in both
directions. Exit 0 = fresh, 1 = stale/drifted, 2 = live docs unavailable or
unparseable. CI treats both non-zero outcomes as requiring maintainer review.
"""

import re
import sys
import urllib.request
from datetime import date
from pathlib import Path


SNAPSHOT = Path(__file__).resolve().parent.parent / "references" / "claude-code-frontmatter.md"
DOCS_URL = "https://code.claude.com/docs/en/skills.md"
MAX_AGE_DAYS = 90


def snapshot_date(text):
    match = re.search(r"\*\*Snapshot:\*\*\s*(\d{4})-(\d{2})-(\d{2})", text)
    if not match:
        return None
    return date(int(match[1]), int(match[2]), int(match[3]))


def snapshot_fields(text):
    return set(re.findall(r"^\|\s*`([a-z_-]+)`\s*\|", text, re.M))


def live_frontmatter_section(text):
    lines = text.splitlines()
    in_section = False
    in_table = False
    table_lines = []
    for line in lines:
        if "Frontmatter reference" in line and line.lstrip().startswith("#"):
            in_section = True
            continue
        if not in_section:
            continue
        if re.match(r"^\|\s*Field\s*\|", line):
            in_table = True
        if in_table:
            if line.startswith("|"):
                table_lines.append(line)
            elif table_lines:
                break
    return "\n".join(table_lines)


def live_fields(text):
    section = live_frontmatter_section(text)
    return set(re.findall(r"^\|\s*`([a-z_-]+)`\s*\|", section, re.M))


def compare_fields(pinned, live):
    return sorted(live - pinned), sorted(pinned - live)


def main():
    text = SNAPSHOT.read_text(encoding="utf-8")
    pinned_date = snapshot_date(text)
    if not pinned_date:
        print("ERROR: no parseable **Snapshot:** YYYY-MM-DD header in the reference file")
        return 1

    age = (date.today() - pinned_date).days
    print(f"snapshot age: {age} days")
    if age > MAX_AGE_DAYS:
        print(f"STALE: snapshot older than {MAX_AGE_DAYS} days; re-verify against {DOCS_URL}")
        return 1

    pinned = snapshot_fields(text)
    if not pinned:
        print("ERROR: could not extract field names from the snapshot table")
        return 1

    try:
        request = urllib.request.Request(DOCS_URL, headers={"User-Agent": "agent-skill-builder-spec-check"})
        page = urllib.request.urlopen(request, timeout=30).read().decode("utf-8", "replace")
    except Exception as error:
        print(f"UNAVAILABLE: could not fetch live docs ({error})")
        return 2

    live = live_fields(page)
    if not live:
        print("UNAVAILABLE: fetched docs but could not parse the frontmatter table")
        return 2

    added, removed = compare_fields(pinned, live)
    if added or removed:
        if added:
            print(f"DRIFT: fields added upstream: {added}")
        if removed:
            print(f"DRIFT: fields removed upstream: {removed}")
        return 1

    print(f"fresh: pinned and live frontmatter contain the same {len(live)} fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
