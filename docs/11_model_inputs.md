# Model Input Data Organization

This document maps `trading-data` outputs and derived data products to the seven accepted `trading-model` layers. It is an organization contract, not a new raw-source acquisition plan.

## Principles

- Keep raw/source acquisition in smallest-unit modules under `src/trading_data/data_sources/`.
- Keep manager-facing model-input orchestration under `src/trading_data/data_bundles/`.
- Keep task inputs in manager task keys, stable bundle contracts/defaults in code, and shared reviewed universes in shared artifacts; avoid bundle-local config files unless operators must routinely change the value outside code review.
- Keep final model-facing outputs SQL-only for accepted numbered data bundles.
- Preserve point-in-time semantics. Model inputs must not use information unavailable at decision time.
- Use derived model-input tables only when they clarify layer boundaries or avoid repeated feature construction.
- Register reusable names through `trading-main` before other repositories depend on them.

## Layer Input Bundles

| Model layer | Input bundle | Core data products | Notes |
|---|---|---|---|
| `MarketRegimeModel` | `01_bundle_market_regime` | ETF/broad-market bars | Alpaca is the primary source for ETF bars. ETF holdings are not required for the first regime model except as explanatory metadata. |
| `SecuritySelectionModel` | `02_bundle_security_selection` | filtered US-listed ETF holdings | Bridges sector/style/theme strength to tradable stocks through holdings-derived universes. |
| `StrategySelectionModel` | `03_bundle_strategy_selection` | selected-symbol bars and liquidity | Chooses strategy family/variant for candidate symbols. |
| `TradeQualityModel` | _(no trading-data bundle)_ | candidate strategy signals, upstream context, bars/liquidity, realized outcomes/labels | Does not require new data acquisition, SQL view, or manifest contract in `trading-data`; `trading-model` consumes upstream SQL outputs directly. |
| `OptionExpressionModel` | `05_bundle_option_expression` | option-chain snapshots at entry/exit decision points | Chooses theoretically best-return and most risk-controllable long call / long put contracts. Contract-level snapshot revision is pending. |
| `PositionExecutionModel` | `06_bundle_position_execution` | selected-contract option time series | Studies how to execute the selected contracts from entry through exit plus one hour. |
| `EventOverlayModel` | `07_bundle_event_overlay` | one-row-per-event overview table | Combines lagging evidence and prior-signal events while details remain behind URL/path references. |

## Implemented Model Input Bundles

Each accepted model layer that needs new `trading-data` acquisition has a manager-facing bundle under `src/trading_data/data_bundles/NN_bundle_<layer>/`. These bundles fetch/prepare the data needed by the layer; they are not the complete model-input universe.

Layer 1 accepts `params.start` and `params.end`, reads the reviewed `market_etf_universe.csv` for ETF scope and bar grains, fetches Alpaca bars, and writes one combined SQL long table, `model_inputs.trading_data_01_bundle_market_regime`.

Layer 2 accepts `params.start` and `params.end`, reads the reviewed `market_etf_universe.csv` for ETF scope/issuer/exposure labels, collects ETF holdings snapshots, filters them to US-listed equity constituents only, and writes SQL table `model_inputs.trading_data_02_bundle_security_selection`.

Layer 3 accepts manager-supplied `params.start`, `params.end`, and `params.symbols`, defaults to 1Min, fetches Alpaca bars plus transient trade/quote liquidity inputs, and writes SQL table `model_inputs.trading_data_03_bundle_strategy_selection`.

Layer 4 has no `trading-data` bundle: it consumes upstream SQL outputs and model/strategy candidates without new data acquisition or manifest/view contract.

Layer 5 currently accepts manager-supplied `params.underlying` and `params.snapshot_time`, calls the ThetaData option selection snapshot interface, and writes SQL table `model_inputs.trading_data_05_bundle_option_expression`. This is scheduled to become contract-level entry/exit snapshot rows because the model compares contracts.

Layer 6 accepts `params.selected_contracts` from Layer 5 and writes SQL table `model_inputs.trading_data_06_bundle_position_execution`, containing selected option contract market data from entry time through exit time plus one hour.

Layer 7 accepts `params.start`, `params.end`, focus sectors/symbols, and event overview rows, then writes SQL table `model_inputs.trading_data_07_bundle_event_overlay`, one row per event. Full news, SEC, macro, and detector details remain behind references.

## Derived Data Products Added for Model Needs

### `stock_etf_exposure`

Integrated step: `src/trading_data/data_bundles/02_bundle_security_selection/pipeline.py`

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

- Derived feature artifact, not a raw provider table.
- Must preserve `available_time`; do not assume a holdings file is usable before it was visible.
- Superseded as the primary Layer 2 bundle output by `model_inputs.trading_data_02_bundle_security_selection`. Future stock-level exposure features should derive from the SQL holdings table plus reviewed ETF/sector/theme scores.

### `equity_abnormal_activity_event`

Bundle: `src/trading_data/data_bundles/07_bundle_event_overlay/equity_abnormal_activity/`

Config: `src/trading_data/data_bundles/07_bundle_event_overlay/equity_abnormal_activity/config.json`

Purpose: EventOverlayModel prior-signal row for abnormal stock/ETF price, volume, relative-strength, gap, or liquidity behavior.

It is analogous to option activity events but uses equity/ETF market data:

- return z-score
- volume z-score
- relative strength z-score versus benchmark/sector ETF
- gap percentage
- spread/liquidity abnormality
- evidence window and source refs

Boundary:

- Derived event-style row, not raw trades/quotes.
- Should be created only from observable market data at/after the event effective time.
- Implemented first as a conservative derived detector over saved `equity_bar.csv`, optional benchmark bars, and optional `equity_liquidity_bar.csv` inputs.
- Can feed the Layer 7 `trading_data_07_bundle_event_overlay` overview table as a `prior_signal`.

## Known Open Data Gaps

- Revise Layer 5 from nested option snapshot payloads to contract-level entry/exit snapshot rows.
- Clean accepted SQL business tables so `run_id`, `task_id`, and write audit timestamps stay in receipts/run metadata rather than business rows.
- Harden ETF-symbol-to-issuer mapping and ETF holdings freshness/available-time rules for production runs.
- Calibrate equity abnormal activity thresholds/model standards against historical distributions before training labels consume them.
- Define optionability summary shape for SecuritySelectionModel; likely derived from option chain snapshots and liquidity filters.
