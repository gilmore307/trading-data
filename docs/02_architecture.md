# Architecture

`trading-data` is organized by the data route, not by broad product domains.

```text
data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

## Module Map

| Docs band | Implementation surface | Purpose |
|---|---|---|
| `10_*` | `src/data_source/source_*`, `src/data_feature/feature_*`, `src/data_models/` | Model-specific data boundaries for M01-M05. |
| `20_*` | `src/data_feed/`, `src/feed_interfaces/`, `src/feed_availability/`, `trading-storage/main/templates/` | Provider feeds, feed availability, and API/data-kind templates. |
| `30_*` | model-input bundle interfaces | Data-output to model-input handoff rules. |
| `40_*` | repository-wide hardening surfaces | Production hardening and non-production safety policy. |
| Runtime substrate | `src/data_runtime/temporal_explorer.py` | Shared calendar/timewheel tables for day/session/event/result/news-index/chart-cache alignment. |

## Repository Surfaces

| Surface | Owns | Examples |
|---|---|---|
| Data feeds | Smallest-unit provider/API/web/file access and feed-level normalization. | Alpaca bars/news/liquidity, ThetaData option endpoints, SEC EDGAR, ETF issuer files, official calendar pages. |
| Data sources | Manager-facing orchestration for accepted model-input or acquisition routes. | SQL outputs use `model_01_market_regime_data_acquisition`, `model_03_target_state_vector_data_acquisition`, `model_03_event_state_data_acquisition`, and `model_05_option_expression_data_acquisition_contract_path` where materialized; `option_chain_state_source` is the shared option-chain source/cache. Retired standalone evidence packages such as `m02_sector_context_data_acquisition` do not define the current candidate route. |
| Data features | Deterministic model-ready feature blocks from accepted source outputs. | SQL outputs use `model_01_market_regime_feature_generation`, `model_02_sector_context_feature_generation`, `model_03_target_state_vector_feature_generation`, `model_03_event_state_feature_generation`, and `model_05_option_expression_feature_generation`. |
| Model catalog | Maintained M01- ownership map for docs/src/CLI/tests. | `src/data_models/catalog.py`. |
| Storage helpers | Low-level persistence helpers for reviewed outputs. | SQL writers and receipt-safe metadata helpers. |
| Temporal substrate | Calendar/day/session/chart-cache SQL contracts for dashboard, replay, and model-context alignment. | `calendar_day`, `calendar_market_session`, `chart_ohlcv_cache`. |
| Downstream consumers | Use accepted outputs without depending on provider internals. | `trading-model`, then strategy/execution/dashboard surfaces after their own contracts. |

## Rules

- Start from the accepted manager request/source contract, not from a broad domain label.
- Treat `source_NN_*` as source-contract identifiers, not model-model numbers.
- Keep provider details in `data_feed`; keep model-input orchestration in `data_source`.
- Prefer accepted SQL outputs for numbered model-input sources.
- Persist only final cleaned artifacts or reviewed SQL rows by default; bulky raw provider payloads stay transient unless an incident/debug artifact is explicitly approved.
- The Temporal Explorer substrate is an index and visualization substrate. It does not materialize  macro/news events until an accepted event-risk route explicitly promotes them. `chart_ohlcv_cache` is a compact visualization cache and is not a training truth source.
- `option_chain_state_source` is the single contract-level ThetaData option-chain source/cache. M02 consumes it only through target-level option-chain reduction; M05 derives option-expression rows from the same source before candidate feature generation.
- Register reusable feed, source, field, status, table, parameter, and artifact names through `trading-manager` before other repositories depend on them.
- Do not use strategy returns, model labels, profitability, or execution outcomes as upstream data-production inputs.
- Keep `src/data_models/catalog.py` current when adding, removing, or intentionally omitting a model data surface.

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

Generated datasets do not belong in Git. File artifacts and runtime evidence default to `trading-storage/storage/01_source_data/`. Durable production handoff uses reviewed SQL/artifact contracts, manifests, artifact references, and ready signals owned with `trading-manager` / `trading-storage`.
