# Data Organization

`trading-data` organizes work around source-backed, control-plane-facing data sources and accepted SQL outputs.

The older three-domain language — market board data / 盘面数据, instrument data / 标的数据, and option data / 期权数据 — remains useful as historical intent, but it is no longer the primary docs boundary. It was too broad once concrete model-layer sources and feed interfaces appeared.

## Current Organization

| Layer | Owns | Examples |
|---|---|---|
| Data feeds | Smallest-unit provider or approved local source access and normalization. | Alpaca bars/quotes/trades/news, ThetaData option snapshots, official calendar or agency pages, ETF issuer holdings. |
| Data sources | Manager-facing orchestration for one accepted model-input or acquisition route. | `source_01_market_regime`, `source_02_security_selection`, `source_03_strategy_selection`, `source_05_option_expression`, `source_07_event_overlay`. |
| Storage/output contracts | Reviewed SQL tables, development receipts, and future durable handoff references. | `source_01_market_regime`, `source_02_security_selection`, completion receipts under ignored runtime storage where still used. |
| Downstream consumers | Model, strategy, dashboard, and execution repositories consume accepted outputs without depending on provider internals. | `trading-model` layer inputs; later strategy/execution/dashboard reads. |

## Boundary Rules

- Start from the accepted control-plane task key or source contract, not from a broad domain label.
- Keep provider/source details in `src/data_feed/` and source/source README files.
- Keep control-plane-facing orchestration in `src/data_source/`.
- Keep final model-facing outputs SQL-only for accepted numbered sources unless a reviewed exception exists.
- Do not use profitability, strategy returns, model labels, or execution outcomes as upstream data-production inputs.
- Register reusable feed, source, field, status, table, and parameter names through `trading-manager` before other repositories depend on them.

## Historical Domain Mapping

The original planning categories map roughly to current source/layer organization as follows:

| Historical planning label | Current home |
|---|---|
| Market board data / 盘面数据 | Market-regime and broad-market source-backed sources, especially `source_01_market_regime`. |
| Instrument data / 标的数据 | Symbol, ETF holdings, liquidity, event, and security-selection sources such as `source_02_security_selection`, `source_03_strategy_selection`, and `source_07_event_overlay`. |
| Option data / 期权数据 | Options feed interfaces and option model sources such as `source_05_option_expression` and `source_06_position_execution`. |

Use the historical labels only when discussing original product intent or Chinese/English conceptual grouping. Do not introduce new runtime keys, registry rows, storage paths, or package names from those labels without review.

## Composition Rule

A data source may compose multiple feeds. Before implementation depends on a composition, document:

- source names and roles;
- authentication/secret-alias expectations;
- rate limits and quota risks;
- timestamp/timezone semantics;
- merge and priority rules when sources disagree;
- output table/schema and validation evidence;
- task-key parameters consumed by the source.

## Output Rule

`trading-data` does not store generated datasets in Git.

Accepted outputs should be reviewed SQL tables or explicitly reviewed development artifacts. Runtime receipts and legacy local files remain under ignored `storage/` unless and until `trading-storage` accepts a durable contract.
