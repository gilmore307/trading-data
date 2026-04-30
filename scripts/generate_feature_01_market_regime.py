#!/usr/bin/env python3
"""Compatibility wrapper for the feature_01_market_regime SQL runner."""
from __future__ import annotations

import sys

from data_feature.feature_01_market_regime.sql import *  # noqa: F403
from data_feature.feature_01_market_regime.sql import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
