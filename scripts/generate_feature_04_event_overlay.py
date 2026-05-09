#!/usr/bin/env python3
"""Compatibility wrapper for the feature_04_event_overlay SQL runner."""

from __future__ import annotations

from data_feature.feature_04_event_overlay.sql import main

if __name__ == "__main__":
    raise SystemExit(main())
