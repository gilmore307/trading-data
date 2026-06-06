# m02_sector_context_feature_generation

Layer 2 `SectorContextModel` sector/industry behavior-evidence feature generator.

- Input: cleaned `m01_market_regime_data_acquisition` bar rows plus reviewed shared CSVs:
  - `layer_01_02_market_context_etf_universe.csv`
  - `layer_01_02_market_context_relative_strength_combinations.csv`
- Scope: shared CSV combinations with `model_layer = layer_02_sector_context`; current reviewed rows use canonical `1m` `feature_bar_grain` values and `combination_type` values such as `sector_rotation` or `context_rotation`.
- Output: SQL table `trading_data.m02_sector_context_feature_generation`, keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id`.
- Payload: point-in-time relative-strength return, normalized trend distance/slope/spread/alignment, volatility-ratio, and correlation evidence for a sector/industry ETF versus a reviewed comparison ETF. Raw ratio moving-average levels are not generated. The table also emits one `sector_rotation_summary` row per snapshot carrying sector-observation breadth and dispersion aggregates.
- Source bars are canonical `1Min` rows from `m01_market_regime_data_acquisition`; current shared ETF rows use `1m` as the reviewed feature grain. Longer-horizon trend, volatility, and correlation diagnostics are still derived locally from the same 1-minute source rows.

This module owns deterministic evidence for Layer 2 conditional ETF-context behavior under market context. Layer 1 should not carry sector/industry rotation evidence; sector leadership, sector-vs-sector comparison, and sector-observation participation belong here.

The model contract uses this feature surface to build per-ETF `context_etf_state` rows and a possible global/group `cross_etf_summary`. Per-ETF cross-section calculations are construction evidence and should not become a separate downstream `context_etf_cross_section_row` when the same values are embedded in `context_etf_state`.

ETF holdings and `stock_etf_exposure` are intentionally outside this feature table and outside the current Layer 2 feature stage. They do not define ordinary candidates, the realtime total pool, or historical replay candidates. Target-specific context attachment should use accepted target-context mappings now, with the future direction being dynamic `target_context_profile` weighting based on correlation, lead-lag, influence direction, and confidence.

## Execution

Preferred manager-runtime path after approved feed acquisition:

```bash
PYTHONPATH=src python3 -m data_feature.m02_sector_context_feature_generation.from_feed_artifacts \
  --month 2016-01
```

This reads existing `01_feed_alpaca_bars` completion receipts from local storage, confirms bars are already retained in `trading_data.m01_market_regime_data_acquisition`, then generates `m02_sector_context_feature_generation`. It performs zero provider calls and does not require saved `equity_bar.csv` or `equity_bar.jsonl` payloads.

Direct SQL generation remains available when the source table is already materialized:

```bash
PYTHONPATH=src python3 -m data_feature.m02_sector_context_feature_generation \
  --database-url postgresql://... \
  --source-schema trading_data \
  --source-table m01_market_regime_data_acquisition \
  --target-schema trading_data \
  --target-table m02_sector_context_feature_generation
```
