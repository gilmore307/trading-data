# feature_02_sector_context

Layer 2 `SectorContextModel` sector/industry behavior-evidence feature generator.

- Input: cleaned `source_01_market_regime` bar rows plus reviewed shared CSVs:
  - `market_regime_etf_universe.csv`
  - `market_regime_relative_strength_combinations.csv`
- Scope: shared CSV combinations with `model_layer = layer_02_sector_context`; current reviewed rows use `combination_type` values such as `sector_rotation` or `daily_context`.
- Output: SQL table `trading_data.feature_02_sector_context`, keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id`.
- Payload: point-in-time relative-strength return, normalized trend distance/slope/spread/alignment, volatility-ratio, and correlation evidence for a sector/industry ETF versus a reviewed comparison ETF. Raw ratio moving-average levels are not generated. The table also emits one `sector_rotation_summary` row per snapshot carrying sector-observation breadth and dispersion aggregates.

This module owns deterministic evidence for Layer 2 conditional sector/basket behavior under market context. Layer 1 should not carry sector/industry rotation evidence; sector leadership, sector-vs-sector comparison, and sector-observation participation belong here. ETF holdings and `stock_etf_exposure` are intentionally outside this feature surface; they are downstream candidate-builder inputs after Layer 2 selects/prioritizes sector baskets.
