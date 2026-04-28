import tempfile
import unittest
from pathlib import Path

from trading_data.template_generators.data_kind_previews import (
    DEFAULT_REGISTRY_CSV,
    DEFAULT_TEMPLATE_ROOT,
    all_template_paths,
    check_templates,
    generate_templates,
)


class DataKindPreviewGenerationTests(unittest.TestCase):
    def test_committed_preview_templates_are_generated_from_registry_ids(self):
        changed = check_templates(
            registry_csv=DEFAULT_REGISTRY_CSV,
            template_root=DEFAULT_TEMPLATE_ROOT,
        )
        self.assertEqual(changed, [])

    def test_generator_writes_all_expected_preview_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            written = generate_templates(registry_csv=DEFAULT_REGISTRY_CSV, template_root=root)
            self.assertEqual(sorted(path.relative_to(root) for path in written), sorted(all_template_paths()))

            option_event = root / "thetadata" / "option_activity_event.preview.csv"
            self.assertIn(
                "id,timeline_headline,created_at,updated_at,symbols,summary,event_link_url",
                option_event.read_text(encoding="utf-8"),
            )

            self.assertNotIn(root / "macro" / "macro_release.preview.csv", written)

            macro_release_event = root / "events" / "macro_release_event.preview.csv"
            macro_event_text = macro_release_event.read_text(encoding="utf-8")
            self.assertIn("event_type", macro_event_text)
            self.assertIn("macro_release_event", macro_event_text)
            self.assertIn("impact_scope", macro_event_text)

            option_detail = root / "thetadata" / "option_activity_event_detail.preview.csv"
            text = option_detail.read_text(encoding="utf-8")
            self.assertIn("triggered_indicators", text)
            self.assertIn("current_standard", text)


if __name__ == "__main__":
    unittest.main()
