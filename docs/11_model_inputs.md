# Source Outputs For Model Layers

This document maps `trading-data` source-backed outputs to the seven accepted `trading-model` layers. It is an organization contract for external/source observations, not a complete training-data or derived-data plan.

## Principles

- Keep raw/source acquisition in smallest-unit modules under `src/data_feed/`.
- Keep manager-facing model-input orchestration under `src/data_source/`.
- Keep task inputs in manager task keys, stable source contracts/defaults in code, and shared reviewed universes in shared artifacts; avoid source-local config files unless operators must routinely change the value outside code review.
- Keep final model-facing outputs SQL-only for accepted numbered data sources.
- Preserve point-in-time semantics. Model inputs must not use information unavailable at decision time.
- Keep model outputs, model-evaluation labels, training runs, strategy/backtest artifacts, and promotion decisions outside `trading-data`. This repository may perform feed acquisition, source construction, and deterministic point-in-time feature construction needed by models.
- Register reusable names through `trading-main` before other repositories depend on them.

## Layer Input Sources

| Model layer | Input source | Core data products | Notes |
|---|---|---|---|
| `MarketRegimeModel` | `source_01_market_regime` | ETF/broad-market bars | Alpaca is the primary source for ETF bars. ETF holdings are not required for the first regime model except as explanatory metadata. |
| `SecuritySelectionModel` | `source_02_security_selection` | filtered US-listed ETF holdings | Bridges sector/style/theme strength to tradable stocks through holdings-derived universes. |
| `StrategySelectionModel` | `source_03_strategy_selection` | selected-symbol bars and liquidity | Chooses strategy family/variant for candidate symbols. |
| `TradeQualityModel` | _(no trading-data source)_ | candidate signals, upstream context, bars/liquidity, realized outcomes/labels | Does not require new source acquisition, SQL view, or manifest contract in `trading-data`; generated candidates/outcomes/labels belong outside the data-production layer unless a deterministic feature contract is explicitly accepted. |
| `OptionExpressionModel` | `source_05_option_expression` | contract-level option-chain snapshots at entry/exit decision points | Chooses theoretically best-return and most risk-controllable long call / long put contracts from one row per visible contract per snapshot. |
| `PositionExecutionModel` | `source_06_position_execution` | selected-contract option time series | Studies how to execute the selected contracts from entry through exit plus one hour. |
| `EventOverlayModel` | `source_07_event_overlay` | one-row-per-event overview table | Combines lagging evidence and prior-signal events while details remain behind URL/path references. |

## Implemented Model Input Sources

Each accepted model layer that needs new `trading-data` acquisition has a manager-facing source-backed source under `src/data_source/NN_source_<layer>/`. These sources fetch/prepare external observations needed by the layer; they are not the complete model-input or training-data universe.

Layer 1 accepts `params.start` and `params.end`, reads the reviewed `market_regime_etf_universe.csv` for ETF scope and bar grains, fetches Alpaca bars, and writes one combined SQL long table, `source_01_market_regime`.

Layer 2 accepts `params.start` and `params.end`, reads the reviewed `market_regime_etf_universe.csv` for ETF scope/issuer/exposure labels, keeps only `universe_type = sector_observation_etf` for holdings analysis, collects ETF holdings snapshots, filters them to US-listed equity constituents only, and writes SQL table `source_02_security_selection`.

Layer 3 accepts manager-supplied `params.start`, `params.end`, and `params.symbols`, defaults to 1Min, fetches Alpaca bars plus transient trade/quote liquidity inputs, and writes SQL table `source_03_strategy_selection`.

Layer 4 has no manager-facing `trading-data` source: it consumes upstream SQL outputs plus model/derived candidates without new source acquisition or manifest/view contract here.

Layer 5 accepts manager-supplied `params.underlying`, `params.snapshot_time`, and optional `params.snapshot_type` (`entry`/`exit`, default `entry`), calls the ThetaData option selection snapshot interface, and writes SQL table `source_05_option_expression` as one row per visible option contract per snapshot. `snapshot_time` is the point-in-time clock; quote/IV/Greeks provider row timestamps are intentionally omitted from the business table.

Layer 6 accepts `params.selected_contracts` from Layer 5 and writes SQL table `source_06_position_execution`, containing selected option contract market data from entry time through exit time plus one hour.

Layer 7 accepts `params.start`, `params.end`, focus sectors/symbols, and event overview rows, then writes SQL table `source_07_event_overlay`, one row per event. Full news, SEC, macro, and detector details remain behind references.

## Source-Backed Aggregations That Need Migration Review

### `stock_etf_exposure`

Integrated step: `src/data_source/source_02_security_selection/pipeline.py`

Purpose: point-in-time stock-to-ETF exposure table for `SecuritySelectionModel`.

It derives from issuer-published `etf_holding_snapshot` rows and current ETF/sector/style scores from model research. It lets Layer 2 transmit ETF/sector/theme strength to individual stocks.

Important fields:

- `as_of_date`
- `symbol`
- `exposed_etfs`
- `top_exposure_etf`
- `total_etf_exposure_score`
- `weighted_sector_score`
- `weighted_theme_score`
- `exposure_tags`
- `source_etf_count`
- `source_snapshot_refs`
- `available_time`

Boundary:

- Source-backed aggregation, not a raw provider table.
- Must preserve `available_time`; do not assume a holdings file is usable before it was visible.
- Superseded as the primary Layer 2 source output by `source_02_security_selection`.
- Future stock-level exposure features that combine source holdings with model scores need explicit boundary review; deterministic source-derived features may live in `trading-data`, while model-derived scores belong in `trading-model`.

### `equity_abnormal_activity_event`

Source: `src/data_source/source_07_event_overlay/equity_abnormal_activity/`

Config: `src/data_source/source_07_event_overlay/equity_abnormal_activity/config.json`

Purpose: EventOverlayModel prior-signal row for abnormal stock/ETF price, volume, relative-strength, gap, or liquidity behavior.

It is analogous to option activity events but uses equity/ETF market data:

- return z-score
- volume z-score
- relative strength z-score versus benchmark/sector ETF
- gap percentage
- spread/liquidity abnormality
- evidence window and source refs

Boundary:

- Source-backed event-style aggregation, not raw trades/quotes.
- Should be created only from observable market data at/after the event effective time.
- Implemented first as a conservative detector over saved `equity_bar.csv`, optional benchmark bars, and optional `equity_liquidity_bar.csv` inputs.
- If this becomes a generated signal/candidate/label rather than source evidence, move it to `trading-data`.

## Known Open Data Gaps

- Revise Layer 5 from nested option snapshot payloads to contract-level entry/exit snapshot rows.
- Clean accepted SQL business tables so `run_id`, `task_id`, and write audit timestamps stay in receipts/run metadata rather than business rows.
- Harden ETF-symbol-to-issuer mapping and ETF holdings freshness/available-time rules for production runs.
- Calibrate equity abnormal activity thresholds/model standards against historical distributions before training labels consume them.
- Define optionability summary shape for SecuritySelectionModel; likely derived from option chain snapshots and liquidity filters.
