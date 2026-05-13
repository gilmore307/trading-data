from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
THETADATA_FEED_DIRS = (
    REPO_ROOT / "src/data_feed/09_feed_thetadata_option_selection_snapshot",
    REPO_ROOT / "src/data_feed/10_feed_thetadata_option_primary_tracking",
    REPO_ROOT / "src/data_feed/11_feed_thetadata_option_event_timeline",
)
FORBIDDEN_SNIPPETS = ('row["payload"]', "row['payload']", "names.payload", "def payload(")


class RegistryPayloadBoundaryTests(unittest.TestCase):
    def test_thetadata_feeds_do_not_infer_field_names_from_registry_payload(self) -> None:
        offenders: list[str] = []
        for root in THETADATA_FEED_DIRS:
            for path in root.rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8")
                for snippet in FORBIDDEN_SNIPPETS:
                    if snippet in text:
                        offenders.append(f"{path.relative_to(REPO_ROOT)} contains {snippet}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
