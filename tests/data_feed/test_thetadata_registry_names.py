import tempfile
import unittest
from importlib import import_module
from pathlib import Path


class ThetaDataRegistryNamesTests(unittest.TestCase):
    def test_registry_csv_is_optional_for_local_field_names(self):
        modules = [
            import_module("data_feed.09_feed_thetadata_option_selection_snapshot.pipeline"),
            import_module("data_feed.10_feed_thetadata_option_primary_tracking.pipeline"),
            import_module("data_feed.11_feed_thetadata_option_event_timeline.pipeline"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            missing_registry = Path(tmp) / "missing_registry.csv"
            for module in modules:
                names = module.RegistryNames(missing_registry)
                self.assertEqual(names.field_name(module.OPTION_UNDERLYING), "underlying")


if __name__ == "__main__":
    unittest.main()
