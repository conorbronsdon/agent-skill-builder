import unittest
from unittest.mock import patch

from scripts import check_spec_freshness as freshness


class FakeResponse:
    def __init__(self, text):
        self.payload = text.encode("utf-8")

    def read(self):
        return self.payload


class SpecFreshnessTests(unittest.TestCase):
    def test_extracts_padded_live_table(self):
        page = """# Frontmatter reference

| Field          | Required | Description |
| :------------- | :------- | :---------- |
| `name`         | No       | Display     |
| `background`   | No       | Fork option |

## Next section
"""
        self.assertEqual(freshness.live_fields(page), {"name", "background"})

    def test_compare_fields_detects_additions_and_removals(self):
        added, removed = freshness.compare_fields(
            {"name", "description"}, {"name", "background"}
        )
        self.assertEqual(added, ["background"])
        self.assertEqual(removed, ["description"])

    @patch("scripts.check_spec_freshness.MAX_AGE_DAYS", 10 ** 6)
    @patch("scripts.check_spec_freshness.urllib.request.urlopen", side_effect=OSError("offline"))
    def test_network_failure_is_not_green(self, _urlopen):
        """Same age-check-before-fetch trap as the green test: without pinning
        MAX_AGE_DAYS this asserts 2 while main() returns 1 once the snapshot is
        stale, so it would have started failing on the calendar too."""
        self.assertEqual(freshness.main(), 2)

    @patch("scripts.check_spec_freshness.MAX_AGE_DAYS", 10 ** 6)
    @patch("scripts.check_spec_freshness.urllib.request.urlopen")
    def test_identical_field_set_is_green(self, urlopen):
        """MAX_AGE_DAYS is pinned because main() runs the age check BEFORE the
        fetch, against date.today(). Without this the test asserts 0 while main
        returns 1 from 2026-11-16 -- CI going red on the calendar, for a reason
        unrelated to the code under test. The age branch has its own test below."""
        pinned = freshness.snapshot_fields(freshness.SNAPSHOT.read_text(encoding="utf-8"))
        rows = "\n".join(f"| `{field}` | No | test |" for field in sorted(pinned))
        urlopen.return_value = FakeResponse(
            "# Frontmatter reference\n\n"
            "| Field | Required | Description |\n| --- | --- | --- |\n"
            f"{rows}\n\n## Next section\n"
        )
        self.assertEqual(freshness.main(), 0)

    @patch("scripts.check_spec_freshness.MAX_AGE_DAYS", -1)
    @patch("scripts.check_spec_freshness.urllib.request.urlopen")
    def test_a_stale_snapshot_is_not_green(self, urlopen):
        """The age branch had no test at all, and it short-circuits before the
        fetch -- so pinning MAX_AGE_DAYS above would have silently removed the
        only thing exercising it. A negative budget makes any snapshot stale."""
        urlopen.side_effect = AssertionError("must not fetch: age check comes first")
        self.assertEqual(freshness.main(), 1)


if __name__ == "__main__":
    unittest.main()
