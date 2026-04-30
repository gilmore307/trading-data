# feature_02_security_selection

Layer 2 `SecuritySelectionModel` sector/industry rotation feature generator.

- Input: cleaned `source_01_market_regime` bar rows plus reviewed shared CSVs:
  - `market_regime_etf_universe.csv`
  - `market_regime_relative_strength_combinations.csv`
- Scope: combinations with `combination_type` in `sector_rotation` or `daily_context`.
- Output: SQL table `trading_data.feature_02_security_selection`, keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id`.
- Payload: point-in-time relative-strength return, trend, volatility-ratio, and correlation evidence for a candidate sector/industry ETF versus a reviewed comparison ETF. The table also emits one `sector_rotation_summary` row per snapshot carrying sector-observation breadth and dispersion aggregates.

This module owns candidate-facing sector/industry rotation evidence and sector-observation breadth/dispersion aggregates. Layer 1 should not carry sector/industry rotation evidence; sector leadership, sector-vs-sector comparison, and sector-observation participation belong here.
