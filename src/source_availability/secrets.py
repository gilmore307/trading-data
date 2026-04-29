"""Secret alias loading without exposing values."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SECRET_ROOT = Path("/root/secrets")

ALIAS_ENV = {
    "alpaca": "ALPACA_SECRET_ALIAS",
    "bea": "BEA_SECRET_ALIAS",
    "bls": "BLS_SECRET_ALIAS",
    "census": "CENSUS_SECRET_ALIAS",
    "fred": "FRED_SECRET_ALIAS",
    "okx": "OKX_SECRET_ALIAS",
    "thetadata": "THETADATA_SECRET_ALIAS",
}


@dataclass(frozen=True)
class SecretAlias:
    alias: str
    path: Path
    present: bool
    keys_present: tuple[str, ...]
    values: dict[str, Any]


def configured_alias(default_alias: str) -> str:
    env_name = ALIAS_ENV.get(default_alias)
    if env_name:
        return os.environ.get(env_name, default_alias)
    return default_alias


def load_secret_alias(default_alias: str) -> SecretAlias:
    alias = configured_alias(default_alias)
    path = SECRET_ROOT / f"{alias}.json"
    if not path.exists():
        return SecretAlias(alias, path, False, (), {})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SecretAlias(alias, path, True, (), {})
    if not isinstance(payload, dict):
        return SecretAlias(alias, path, True, (), {})
    return SecretAlias(
        alias=alias,
        path=path,
        present=True,
        keys_present=tuple(sorted(str(key) for key in payload.keys())),
        values=payload,
    )


def public_secret_summary(secret: SecretAlias | None) -> dict[str, Any] | None:
    if secret is None:
        return None
    return {
        "alias": secret.alias,
        "path": str(secret.path),
        "present": secret.present,
        "keys_present": list(secret.keys_present),
    }
