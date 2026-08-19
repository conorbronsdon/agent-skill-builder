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

    @patch("scripts.check_spec_freshness.urllib.request.urlopen", side_effect=OSError("offline"))
    def test_network_failure_is_not_green(self, _urlopen):
        self.assertEqual(freshness.main(), 2)

    @patch("scripts.check_spec_freshness.urllib.request.urlopen")
    def test_identical_field_set_is_green(self, urlopen):
        pinned = freshness.snapshot_fields(freshness.SNAPSHOT.read_text(encoding="utf-8"))
        rows = "\n".join(f"| `{field}` | No | test |" for field in sorted(pinned))
        urlopen.return_value = FakeResponse(
            "# Frontmatter reference\n\n"
            "| Field | Required | Description |\n| --- | --- | --- |\n"
            f"{rows}\n\n## Next section\n"
        )
        self.assertEqual(freshness.main(), 0)


if __name__ == "__main__":
    unittest.main()
