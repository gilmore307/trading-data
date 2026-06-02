"""Optional source-local configuration loader.

Most manager-facing sources keep stable defaults in pipeline code or reviewed
shared artifacts. Use this helper only for source subcomponents that explicitly
own a small reviewed ``config.json`` next to their code, such as detector
threshold defaults.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any


class SourceConfigError(ValueError):
    """Raised when a data source config cannot be loaded."""


def load_source_config(source: str, *, config_path: str | None = None) -> dict[str, Any]:
    """Load a source-local config file.

    ``source`` is the data_source package name that owns a packaged config, e.g.
    ``m10_event_risk_governor_data_acquisition/equity_abnormal_activity``.
    ``config_path`` is an optional task-key override for tests or reviewed one-off
    runs. Normal production use should prefer the reviewed packaged config when
    the component has one.
    """
    if config_path:
        path = Path(config_path)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SourceConfigError(f"missing source config path {config_path!r}") from exc
        except json.JSONDecodeError as exc:
            raise SourceConfigError(f"invalid JSON in source config path {config_path!r}: {exc}") from exc
    package = source.replace("/", ".").replace("\\", ".").strip(" .")
    if not package or ".." in package:
        raise SourceConfigError("source name is required")
    resource = files(f"data_source.{package}").joinpath("config.json")
    try:
        return json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceConfigError(f"missing config.json for data source {source!r}") from exc
    except json.JSONDecodeError as exc:
        raise SourceConfigError(f"invalid JSON in config.json for data source {source!r}: {exc}") from exc


def config_section(config: dict[str, Any], *path: str) -> dict[str, Any]:
    """Return a nested config section as a dict, or an empty dict."""
    current: Any = config
    for key in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return dict(current) if isinstance(current, dict) else {}
