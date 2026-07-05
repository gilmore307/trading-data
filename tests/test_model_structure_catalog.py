from __future__ import annotations

import importlib
import tomllib
import unittest
from pathlib import Path

from data_models import MODEL_CONTRACTS


REPO_ROOT = Path(__file__).resolve().parents[1]


class ModelStructureCatalogTests(unittest.TestCase):
    def test_catalog_covers_m01_through_m05(self) -> None:
        self.assertEqual([contract.model for contract in MODEL_CONTRACTS], list(range(1, 6)))
        self.assertEqual(len({contract.slug for contract in MODEL_CONTRACTS}), 5)

    def test_each_model_has_a_top_level_doc(self) -> None:
        for contract in MODEL_CONTRACTS:
            with self.subTest(model=contract.model_marker, doc_path=contract.doc_path):
                doc = REPO_ROOT / contract.doc_path
                self.assertTrue(doc.exists(), contract.doc_path)
                text = doc.read_text(encoding="utf-8")
                self.assertIn(contract.model_marker, text)

    def test_owned_packages_import_and_have_readmes(self) -> None:
        for contract in MODEL_CONTRACTS:
            for package in contract.source_packages + contract.feature_packages + contract.feed_packages:
                with self.subTest(model=contract.model_marker, package=package):
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
        for contract in MODEL_CONTRACTS:
            for command in contract.cli_commands:
                with self.subTest(model=contract.model_marker, command=command):
                    self.assertIn(command, scripts)

    def test_feature_surfaces_do_not_keep_duplicate_script_wrappers(self) -> None:
        for contract in MODEL_CONTRACTS:
            for package in contract.feature_packages:
                feature_name = package.rsplit(".", 1)[-1]
                script = REPO_ROOT / "scripts" / f"generate_{feature_name}.py"
                with self.subTest(model=contract.model_marker, script=script.name):
                    self.assertFalse(script.exists(), script)

    def test_m01_current_surface_excludes_candidate_holdings_source(self) -> None:
        m01 = next(contract for contract in MODEL_CONTRACTS if contract.model == 1)
        m02 = next(contract for contract in MODEL_CONTRACTS if contract.model == 2)
        self.assertNotIn("data_source.m02_sector_context_data_acquisition", m01.source_packages)
        self.assertIn("data_feature.m02_sector_context_feature_generation", m01.feature_packages)
        self.assertNotIn("trading-data-m02-sector-context-data-acquisition", m01.cli_commands)
        self.assertNotIn("data_source.m02_sector_context_data_acquisition", m02.source_packages)
        self.assertIn("data_source.m03_target_state_vector_data_acquisition", m02.source_packages)
        self.assertNotIn("trading-data-m02-sector-context-data-acquisition", m02.cli_commands)

    def test_model_05_catalog_does_not_own_option_chain_snapshot_acquisition(self) -> None:
        m05 = next(contract for contract in MODEL_CONTRACTS if contract.model == 5)

        self.assertNotIn("data_feed.09_feed_thetadata_option_selection_snapshot", m05.feed_packages)
        self.assertNotIn("trading-data-09-feed-thetadata-option-selection-snapshot", m05.cli_commands)
        self.assertIn("data_feature.m05_option_expression_feature_generation", m05.feature_packages)
        self.assertIn("data_source.m05_option_expression_data_acquisition_contract_path", m05.source_packages)

    def test_no_source_models_are_explicit_and_do_not_have_symmetry_packages(self) -> None:
        for contract in MODEL_CONTRACTS:
            if contract.owns_dedicated_data_surface:
                continue
            with self.subTest(model=contract.model_marker):
                self.assertTrue(contract.no_source_reason)
                self.assertEqual(contract.source_packages, ())
                self.assertEqual(contract.feature_packages, ())
                source_name = f"m{contract.model:02d}_{contract.slug}_data_acquisition"
                feature_name = f"m{contract.model:02d}_{contract.slug}_feature_generation"
                self.assertFalse((REPO_ROOT / "src" / "data_source" / source_name).exists(), source_name)
                self.assertFalse((REPO_ROOT / "src" / "data_feature" / feature_name).exists(), feature_name)

    def test_catalog_test_paths_exist(self) -> None:
        for contract in MODEL_CONTRACTS:
            for test_path in contract.test_paths:
                with self.subTest(model=contract.model_marker, test_path=test_path):
                    self.assertTrue((REPO_ROOT / test_path).exists(), test_path)


if __name__ == "__main__":
    unittest.main()
