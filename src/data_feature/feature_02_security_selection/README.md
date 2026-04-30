# feature_02_security_selection

Layer 2 `SecuritySelectionModel` sector/industry rotation feature generator.

- Input: cleaned `source_01_market_regime` bar rows plus reviewed shared CSVs:
  - `market_regime_etf_universe.csv`
  - `market_regime_relative_strength_combinations.csv`
- Scope: combinations with `combination_type` in `sector_rotation` or `daily_context`.
- Output: SQL table `trading_data.feature_02_security_selection`, keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id`.
- Payload: point-in-time relative-strength return, trend, volatility-ratio, and correlation evidence for a candidate sector/industry ETF versus a reviewed comparison ETF.

This module owns candidate-facing sector/industry rotation evidence. Layer 1 may keep broad market structure aggregates, but sector leadership and sector-vs-sector comparison features belong here.
