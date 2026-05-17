import os
import unittest
from pathlib import Path
from unittest import mock

from data_runtime import config


class RuntimeConfigTests(unittest.TestCase):
    def test_output_root_uses_task_override(self):
        self.assertEqual(
            config.resolve_output_root({"output_root": "/tmp/out", "task_id": "ignored"}, default_task_id="default"),
            Path("/tmp/out"),
        )

    def test_output_root_uses_storage_env_and_task_id(self):
        with mock.patch.dict(os.environ, {"TRADING_DATA_STORAGE_ROOT": "/tmp/data-storage"}, clear=False):
            self.assertEqual(
                config.resolve_output_root({"task_id": "task-a"}, default_task_id="default"),
                Path("/tmp/data-storage") / "task-a",
            )

    def test_manager_registry_csv_env_override(self):
        with mock.patch.dict(os.environ, {"TRADING_MANAGER_REGISTRY_CSV": "/tmp/registry.csv"}, clear=False):
            self.assertEqual(config.manager_registry_csv(), Path("/tmp/registry.csv"))

    def test_shared_path_uses_storage_repo_env(self):
        with mock.patch.dict(os.environ, {"TRADING_STORAGE_REPO_ROOT": "/tmp/storage-repo"}, clear=False):
            self.assertEqual(config.shared_path("main", "shared", "x.csv"), Path("/tmp/storage-repo/main/shared/x.csv"))

    def test_secret_and_database_paths_use_env_overrides(self):
        with mock.patch.dict(
            os.environ,
            {
                "TRADING_SECRET_ROOT": "/tmp/secrets",
                "TRADING_DATABASE_URL_FILE": "/tmp/db-url",
                "TRADING_ECONOMICS_COOKIE_JAR": "/tmp/te-cookies.txt",
            },
            clear=False,
        ):
            self.assertEqual(config.secret_root(), Path("/tmp/secrets"))
            self.assertEqual(config.database_url_file(), Path("/tmp/db-url"))
            self.assertEqual(config.trading_economics_cookie_jar(), Path("/tmp/te-cookies.txt"))

    def test_database_and_cookie_defaults_are_under_secret_root(self):
        with mock.patch.dict(os.environ, {"TRADING_SECRET_ROOT": "/tmp/secrets"}, clear=False):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TRADING_DATABASE_URL_FILE", None)
                os.environ.pop("TRADING_ECONOMICS_COOKIE_JAR", None)
                self.assertEqual(config.database_url_file(), Path("/tmp/secrets/openclaw/database-url"))
                self.assertEqual(config.trading_economics_cookie_jar(), Path("/tmp/secrets/tradingeconomics-cookies.txt"))


if __name__ == "__main__":
    unittest.main()
