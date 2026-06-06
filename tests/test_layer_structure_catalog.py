from __future__ import annotations

import importlib
import tomllib
import unittest
from pathlib import Path

from data_layers import LAYER_CONTRACTS


REPO_ROOT = Path(__file__).resolve().parents[1]


class LayerStructureCatalogTests(unittest.TestCase):
    def test_catalog_covers_layers_one_through_ten(self) -> None:
        self.assertEqual([contract.layer for contract in LAYER_CONTRACTS], list(range(1, 11)))
        self.assertEqual(len({contract.slug for contract in LAYER_CONTRACTS}), 10)

    def test_each_layer_has_a_top_level_doc(self) -> None:
        for contract in LAYER_CONTRACTS:
            with self.subTest(layer=contract.layer, doc_path=contract.doc_path):
                doc = REPO_ROOT / contract.doc_path
                self.assertTrue(doc.exists(), contract.doc_path)
                text = doc.read_text(encoding="utf-8")
                self.assertIn(f"Layer {contract.layer:02d}", text)
                self.assertIn(contract.model_name, text)

    def test_no_source_layer_docs_do_not_keep_stale_layer_numbers(self) -> None:
        stale_phrases = {
            4: ("dedicated Layer 5 source", "Layer 5-related"),
            5: ("dedicated Layer 4 source", "Layer 4-related"),
            6: ("dedicated Layer 5 source", "Layer 5 may consume", "Layer 4-related"),
            7: ("dedicated Layer 5 source", "Layer 5 may consume", "Layer 4-related"),
        }
        for contract in LAYER_CONTRACTS:
            for stale_phrase in stale_phrases.get(contract.layer, ()):  # currently guards reviewed Layer 4-6 docs.
                with self.subTest(layer=contract.layer, stale_phrase=stale_phrase):
                    text = (REPO_ROOT / contract.doc_path).read_text(encoding="utf-8")
                    self.assertNotIn(stale_phrase, text)

    def test_owned_packages_import_and_have_readmes(self) -> None:
        for contract in LAYER_CONTRACTS:
            for package in contract.source_packages + contract.feature_packages + contract.feed_packages:
                with self.subTest(layer=contract.layer, package=package):
                    package_dir = REPO_ROOT / "src" / Path(*package.split("."))
                    self.assertTrue(package_dir.exists(), package)
                    self.assertTrue((package_dir / "README.md").exists(), f"{package} missing README.md")
                    if (package_dir / "__main__.py").exists():
                        importlib.import_module(f"{package}.__main__")
                    elif (package_dir / "pipeline.py").exists():
                        importlib.import_module(f"{package}.pipeline")
                    elif (package_dir / "generator.py").exists():
                        importlib.import_module(f"{package}.generator")
                    else:
                        self.fail(f"{package} has no importable entry module")

    def test_cli_entrypoints_exist_for_owned_surfaces(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = pyproject["project"]["scripts"]
        for contract in LAYER_CONTRACTS:
            for command in contract.cli_commands:
                with self.subTest(layer=contract.layer, command=command):
                    self.assertIn(command, scripts)

    def test_feature_surfaces_do_not_keep_duplicate_script_wrappers(self) -> None:
        for contract in LAYER_CONTRACTS:
            for package in contract.feature_packages:
                feature_name = package.rsplit(".", 1)[-1]
                script = REPO_ROOT / "scripts" / f"generate_{feature_name}.py"
                with self.subTest(layer=contract.layer, script=script.name):
                    self.assertFalse(script.exists(), script)

    def test_layer_two_current_surface_excludes_candidate_holdings_source(self) -> None:
        layer_2 = next(contract for contract in LAYER_CONTRACTS if contract.layer == 2)
        layer_3 = next(contract for contract in LAYER_CONTRACTS if contract.layer == 3)
        self.assertNotIn("data_source.m02_sector_context_data_acquisition", layer_2.source_packages)
        self.assertIn("data_feature.m02_sector_context_feature_generation", layer_2.feature_packages)
        self.assertNotIn("trading-data-m02-sector-context-data-acquisition", layer_2.cli_commands)
        self.assertNotIn("data_source.m02_sector_context_data_acquisition", layer_3.source_packages)
        self.assertIn("data_source.m03_target_state_vector_data_acquisition", layer_3.source_packages)
        self.assertNotIn("trading-data-m02-sector-context-data-acquisition", layer_3.cli_commands)

    def test_layer_nine_catalog_does_not_own_option_chain_snapshot_acquisition(self) -> None:
        layer_9 = next(contract for contract in LAYER_CONTRACTS if contract.layer == 9)

        self.assertNotIn("data_feed.09_feed_thetadata_option_selection_snapshot", layer_9.feed_packages)
        self.assertNotIn("trading-data-09-feed-thetadata-option-selection-snapshot", layer_9.cli_commands)
        self.assertIn("data_feature.m09_option_expression_feature_generation", layer_9.feature_packages)
        self.assertIn("data_source.m09_option_expression_data_acquisition_contract_path", layer_9.source_packages)

    def test_no_source_layers_are_explicit_and_do_not_have_symmetry_packages(self) -> None:
        for contract in LAYER_CONTRACTS:
            if contract.owns_dedicated_data_surface:
                continue
            with self.subTest(layer=contract.layer):
                self.assertTrue(contract.no_source_reason)
                self.assertEqual(contract.source_packages, ())
                self.assertEqual(contract.feature_packages, ())
                source_name = f"source_{contract.layer:02d}_{contract.slug}"
                feature_name = f"feature_{contract.layer:02d}_{contract.slug}"
                self.assertFalse((REPO_ROOT / "src" / "data_source" / source_name).exists(), source_name)
                self.assertFalse((REPO_ROOT / "src" / "data_feature" / feature_name).exists(), feature_name)

    def test_catalog_test_paths_exist(self) -> None:
        for contract in LAYER_CONTRACTS:
            for test_path in contract.test_paths:
                with self.subTest(layer=contract.layer, test_path=test_path):
                    self.assertTrue((REPO_ROOT / test_path).exists(), test_path)


if __name__ == "__main__":
    unittest.main()
