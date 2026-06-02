"""CLI entrypoint for m10_event_risk_governor_feature_generation SQL generation."""
from __future__ import annotations

from .sql import main

if __name__ == "__main__":
    raise SystemExit(main())
