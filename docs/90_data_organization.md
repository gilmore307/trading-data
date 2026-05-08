# Data Organization

`trading-data` is organized by the data route, not by broad product domains.

```text
data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

## Layers

| Layer | Owns | Examples |
|---|---|---|
| Data feeds | Smallest-unit provider/API/web/file access and feed-level normalization. | Alpaca bars/news/liquidity, ThetaData option endpoints, SEC EDGAR, ETF issuer files, official calendar pages. |
| Data sources | Manager-facing orchestration for accepted model-input or acquisition routes. | `source_01_market_regime`, `source_02_target_candidate_holdings`, `source_03_target_state`, `source_04_event_overlay`, `source_05_option_expression`, `source_06_position_execution`. |
| Data features | Deterministic layer-ready feature blocks from accepted source outputs. | `feature_01_market_regime`, `feature_02_sector_context`, `feature_03_target_state_vector`, `feature_04_event_overlay`, `feature_08_option_expression`. |
| Layer catalog | Maintained Layer 1-8 ownership map for docs/src/CLI/tests. | `src/data_layers/catalog.py`. |
| Storage helpers | Low-level persistence helpers for reviewed outputs. | SQL writers and receipt-safe metadata helpers. |
| Downstream consumers | Use accepted outputs without depending on provider internals. | `trading-model`, then strategy/execution/dashboard surfaces after their own contracts. |

## Rules

- Start from the accepted manager request/source contract, not from a broad domain label.
- Keep provider details in `data_feed`; keep model-input orchestration in `data_source`.
- Prefer accepted SQL outputs for numbered model-input sources.
- Persist only final cleaned artifacts or reviewed SQL rows by default; bulky raw provider payloads stay transient unless an incident/debug artifact is explicitly approved.
- Register reusable feed, source, field, status, table, parameter, and artifact names through `trading-manager` before other repositories depend on them.
- Do not use strategy returns, model labels, profitability, or execution outcomes as upstream data-production inputs.
- Keep `src/data_layers/catalog.py` current when adding, removing, or intentionally omitting a layer surface.

## Historical Labels

The original planning labels were:

| Historical label | Current interpretation |
|---|---|
| Market board data / 盘面数据 | Broad-market and market-regime source/feature outputs. |
| Instrument data / 标的数据 | Target candidate, target state, issuer/holding, liquidity, and event evidence. |
| Option data / 期权数据 | Option snapshot, selected-contract tracking, and option event evidence. |

Use those labels only for product discussion. Do not create runtime keys, registry rows, storage paths, or package names from them without review.

## Source Composition Checklist

Before a source composes feeds, document:

- source names and roles;
- credential or no-key expectations;
- rate limits and quota risks;
- timestamp/timezone semantics;
- merge and priority rules;
- output table/schema and validation evidence;
- manager request/task parameters consumed by the source.

## Output Rule

Generated datasets do not belong in Git. Local ignored `storage/` files are development evidence. Durable production handoff uses reviewed SQL/artifact contracts, manifests, artifact references, and ready signals owned with `trading-manager` / `trading-storage`.
