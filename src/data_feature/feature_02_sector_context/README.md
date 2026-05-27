# feature_02_sector_context

Layer 2 `SectorContextModel` sector/industry behavior-evidence feature generator.

- Input: cleaned `source_01_market_regime` bar rows plus reviewed shared CSVs:
  - `layer_01_02_market_context_etf_universe.csv`
  - `layer_01_02_market_context_relative_strength_combinations.csv`
- Scope: shared CSV combinations with `model_layer = layer_02_sector_context`; current reviewed rows use canonical `1m` `feature_bar_grain` values and `combination_type` values such as `sector_rotation` or `context_rotation`.
- Output: SQL table `trading_data.feature_02_sector_context`, keyed by `snapshot_time + candidate_symbol + comparison_symbol + rotation_pair_id`.
- Payload: point-in-time relative-strength return, normalized trend distance/slope/spread/alignment, volatility-ratio, and correlation evidence for a sector/industry ETF versus a reviewed comparison ETF. Raw ratio moving-average levels are not generated. The table also emits one `sector_rotation_summary` row per snapshot carrying sector-observation breadth and dispersion aggregates.
- Source bars are canonical `1Min` rows from `source_01_market_regime`; current shared ETF rows use `1m` as the reviewed feature grain. Longer-horizon trend, volatility, and correlation diagnostics are still derived locally from the same 1-minute source rows.

This module owns deterministic evidence for Layer 2 conditional sector/basket behavior under market context. Layer 1 should not carry sector/industry rotation evidence; sector leadership, sector-vs-sector comparison, and sector-observation participation belong here. ETF holdings and `stock_etf_exposure` are intentionally outside this feature table, but the Layer 2 feature stage materializes `source_02_target_candidate_holdings` as the downstream candidate-builder handoff after sector/basket context is available.

## Execution

Preferred manager-runtime path after approved feed acquisition:

```bash
PYTHONPATH=src python3 -m data_feature.feature_02_sector_context.from_feed_artifacts \
  --month 2016-01
```

This reads existing `01_feed_alpaca_bars` completion receipts/artifacts from local storage, upserts their saved `equity_bar.csv` rows into `trading_data.source_01_market_regime`, then generates `feature_02_sector_context`. It performs zero provider calls.

Direct SQL generation remains available when the source table is already materialized:

```bash
PYTHONPATH=src python3 -m data_feature.feature_02_sector_context \
  --database-url postgresql://... \
  --source-schema trading_data \
  --source-table source_01_market_regime \
  --target-schema trading_data \
  --target-table feature_02_sector_context
```
