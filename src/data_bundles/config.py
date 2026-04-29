"""Bundle-local configuration loader.

Each manager-facing data bundle owns its own ``config.json`` next to the bundle
code. The task key may override config values for one run, but stable bundle
choices such as ETF lists, issuers, grains, and detector defaults should live
with the bundle that uses them.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any


class BundleConfigError(ValueError):
    """Raised when a data bundle config cannot be loaded."""


def load_bundle_config(bundle: str, *, config_path: str | None = None) -> dict[str, Any]:
    """Load a bundle-local config file.

    ``bundle`` is the data_bundles package name, e.g. ``stock_etf_exposure``.
    ``config_path`` is an optional task-key override for tests or reviewed one-off
    runs. Normal production use should prefer the packaged bundle config.
    """
    if config_path:
        path = Path(config_path)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BundleConfigError(f"missing bundle config path {config_path!r}") from exc
        except json.JSONDecodeError as exc:
            raise BundleConfigError(f"invalid JSON in bundle config path {config_path!r}: {exc}") from exc
    safe = bundle.replace("/", "_").replace("\\", "_").strip()
    if not safe:
        raise BundleConfigError("bundle name is required")
    resource = files(f"data_bundles.{safe}").joinpath("config.json")
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BundleConfigError(f"missing config.json for data bundle {bundle!r}") from exc
    except json.JSONDecodeError as exc:
        raise BundleConfigError(f"invalid JSON in config.json for data bundle {bundle!r}: {exc}") from exc


def config_section(config: dict[str, Any], *path: str) -> dict[str, Any]:
    """Return a nested config section as a dict, or an empty dict."""
    current: Any = config
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return dict(current) if isinstance(current, dict) else {}
