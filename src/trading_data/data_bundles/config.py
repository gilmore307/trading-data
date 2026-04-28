"""Bundle configuration loader.

Configuration files keep reusable data-request parameters out of manager task
keys when they are stable project choices, e.g. ETF baskets, issuer labels,
bar grains, and detector defaults. Task keys may still override values for a
specific run.
"""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

CONFIG_PACKAGE = "trading_data.data_bundles.configs"


class BundleConfigError(ValueError):
    """Raised when a data bundle config cannot be loaded."""


def load_bundle_config(name: str = "model_inputs") -> dict[str, Any]:
    """Load a packaged JSON bundle config by stem name."""
    safe = name.replace("/", "_").replace("\\", "_").strip() or "model_inputs"
    resource = files(CONFIG_PACKAGE).joinpath(f"{safe}.json")
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleConfigError(f"unknown bundle config {name!r}") from exc
    except json.JSONDecodeError as exc:
        raise BundleConfigError(f"invalid JSON in bundle config {name!r}: {exc}") from exc


def config_section(config: dict[str, Any], *path: str) -> dict[str, Any]:
    """Return a nested config section as a dict, or an empty dict."""
    current: Any = config
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return dict(current) if isinstance(current, dict) else {}
