"""Runtime path/config defaults for trading-data.

The manager task key remains the authoritative source for a run. These helpers
only centralize local defaults so feeds/sources do not hard-code host paths or
repeat output-root logic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


def repo_root() -> Path:
    return Path(os.environ.get("TRADING_DATA_REPO_ROOT") or Path(__file__).resolve().parents[2])


def projects_root() -> Path:
    return Path(os.environ.get("TRADING_PROJECTS_ROOT") or repo_root().parent)


def storage_root() -> Path:
    """Return the storage-owned data artifact root.

    Data code produces source/evidence files, but durable filesystem ownership
    belongs to trading-storage. Relative task-key roots such as
    `storage/monthly_backfill/...` are resolved under this component root.
    """

    return Path(os.environ.get("TRADING_DATA_STORAGE_ROOT") or shared_storage_repo_root() / "storage" / "source_data")


def secret_root() -> Path:
    return Path(os.environ.get("TRADING_SECRET_ROOT") or "/root/secrets")


def database_url_file() -> Path:
    return Path(os.environ.get("TRADING_DATABASE_URL_FILE") or secret_root() / "openclaw" / "database-url")


def trading_economics_cookie_jar() -> Path:
    return Path(os.environ.get("TRADING_ECONOMICS_COOKIE_JAR") or secret_root() / "tradingeconomics-cookies.txt")


def manager_registry_csv() -> Path:
    return Path(
        os.environ.get("TRADING_MANAGER_REGISTRY_CSV")
        or projects_root() / "trading-manager" / "scripts" / "registry" / "current.csv"
    )


def shared_storage_repo_root() -> Path:
    return Path(os.environ.get("TRADING_STORAGE_REPO_ROOT") or projects_root() / "trading-storage")


def shared_path(*parts: str) -> Path:
    return shared_storage_repo_root().joinpath(*parts)


def resolve_output_root(task_key: Mapping[str, Any], *, default_task_id: str) -> Path:
    explicit = task_key.get("output_root")
    if explicit:
        path = Path(str(explicit))
        if path.is_absolute():
            return path
        parts = path.parts
        if parts and parts[0] == "storage":
            return storage_root().joinpath(*parts[1:])
        return storage_root() / path
    task_id = str(task_key.get("task_id") or default_task_id)
    return storage_root() / task_id


__all__ = [
    "database_url_file",
    "manager_registry_csv",
    "projects_root",
    "repo_root",
    "resolve_output_root",
    "secret_root",
    "shared_path",
    "shared_storage_repo_root",
    "storage_root",
    "trading_economics_cookie_jar",
]
