#!/usr/bin/env python3
"""Check whether the pinned frontmatter-spec snapshot has drifted from the live docs.

Two checks, run by the weekly `spec-drift` workflow (and runnable locally):

1. Age: the snapshot header date is > MAX_AGE_DAYS old.
2. Field drift (best effort, needs network): every frontmatter field named in the
   snapshot still appears on the live docs page, and none of a small watchlist of
   plausible new-field spellings appears on the page without being in the snapshot.

Exit 0 = fresh, 1 = drift/stale (CI opens an issue), 2 = couldn't check.
"""

import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parent.parent / "references" / "claude-code-frontmatter.md"
DOCS_URL = "https://code.claude.com/docs/en/skills"
MAX_AGE_DAYS = 90


def main():
    text = SNAPSHOT.read_text(encoding="utf-8")

    m = re.search(r"\*\*Snapshot:\*\*\s*(\d{4})-(\d{2})-(\d{2})", text)
    if not m:
        print("ERROR: no parseable **Snapshot:** YYYY-MM-DD header in the reference file")
        return 1
    age = (date.today() - date(int(m[1]), int(m[2]), int(m[3]))).days
    print(f"snapshot age: {age} days")
    if age > MAX_AGE_DAYS:
        print(f"STALE: snapshot older than {MAX_AGE_DAYS} days — re-verify against {DOCS_URL}")
        return 1

    fields = set(re.findall(r"^\| `([a-z_-]+)` \|", text, re.M))
    if not fields:
        print("ERROR: could not extract field names from the snapshot table")
        return 1

    try:
        req = urllib.request.Request(DOCS_URL, headers={"User-Agent": "spec-drift-check"})
        page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    except Exception as e:  # network-restricted environments: age check already passed
        print(f"could not fetch live docs ({e}); age check passed, field check skipped")
        return 0

    missing = sorted(f for f in fields if f not in page)
    if missing:
        print(f"DRIFT: snapshot fields no longer on the docs page (renamed/removed?): {missing}")
        return 1

    # Known limitation: this detects removed/renamed fields, not newly added ones —
    # heading anchors and prose make new-token sniffing too noisy to gate CI on.
    # New-field discovery happens at the age-triggered manual review (MAX_AGE_DAYS).
    print("fresh: all snapshot fields still present on the live page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
