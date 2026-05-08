#!/usr/bin/env python3
"""Compatibility wrapper for the feature_02_sector_context SQL runner."""
from __future__ import annotations

import sys

from data_feature.feature_02_sector_context.sql import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
