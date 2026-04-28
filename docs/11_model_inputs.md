# Model Input Data Organization

This document maps `trading-data` outputs and derived data products to the seven accepted `trading-model` layers. It is an organization contract, not a new raw-source acquisition plan.

## Principles

- Keep raw/source acquisition in smallest-unit modules under `src/trading_data/data_sources/`.
- Keep manager-facing model-input orchestration under `src/trading_data/data_bundles/`.
- Keep reusable bundle parameters in config files, e.g. ETF lists, issuer labels, grains, and detector defaults.
- Keep final model-facing flat outputs as CSV unless an explicit JSON contract is accepted.
- Preserve point-in-time semantics. Model inputs must not use information unavailable at decision time.
- Use derived model-input tables only when they clarify layer boundaries or avoid repeated feature construction.
- Register reusable names through `trading-main` before other repositories depend on them.

## Layer Input Bundles

| Model layer | Input bundle | Core data products | Notes |
|---|---|---|---|
| `MarketRegimeModel` | `market_regime_model_inputs` | ETF/broad-market `equity_bar`; cross-asset ETF basket bars; ratios and market-only features derived later | Alpaca is the primary source for ETF bars. ETF holdings are not required for the first regime model, except as explanatory metadata. |
| `SecuritySelectionModel` | `security_selection_model_inputs` | `etf_holding_snapshot`, `stock_etf_exposure`, equity bars/liquidity, optionability summaries, event exclusions | Bridges sector/style strength to tradable stocks. Uses both ETF holdings-driven universe and full-market scan universe. |
| `StrategySelectionModel` | `strategy_selection_model_inputs` | equity bars/liquidity from Alpaca, crypto bars/liquidity from OKX, selected candidate pools from Layer 2 | Chooses strategy family/variant for candidate symbols. |
| `TradeQualityModel` | `trade_quality_model_inputs` | candidate strategy signals, upstream context, bars/liquidity, realized outcomes/labels | Does not require a new raw provider; mostly consumes model-generated signals and source-market features. |
| `OptionExpressionModel` | `option_expression_model_inputs` | option chain snapshot, option bars/contract tracking, IV/Greeks/liquidity, upstream signal forecast | V1 supports long call / long put only; no multi-leg option structures. |
| `EventOverlayModel` | `event_overlay_model_inputs` | `gdelt_article`, SEC company financials/filings, `trading_economics_calendar_event`, option activity, `equity_abnormal_activity_event` | Event overlay affects all earlier layers plus final risk gate. Trading Economics is the accepted macro calendar/value surface. |
| `PortfolioRiskModel` | `portfolio_risk_model_inputs` | option contract data, positions, fills, PnL, cash/margin, exposures, risk limits, kill-switch state | Portfolio/account state is likely execution/account-owned, not pure `trading-data`. Historical simulation outputs may fill this during research. |

## Derived Data Products Added for Model Needs

### `stock_etf_exposure`

Bundle: `src/trading_data/data_bundles/stock_etf_exposure/`

Config: `src/trading_data/data_bundles/stock_etf_exposure/config.json`

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
- `style_tags`
- `source_etf_count`
- `source_snapshot_refs`
- `available_time_et`

Boundary:

- Derived feature artifact, not a raw provider table.
- Must preserve `available_time_et`; do not assume a holdings file is usable before it was visible.
- Implemented first as a conservative derived bundle over saved `etf_holding_snapshot.csv` inputs and caller-supplied ETF/sector/theme scores.

### `equity_abnormal_activity_event`

Bundle: `src/trading_data/data_bundles/equity_abnormal_activity/`

Config: `src/trading_data/data_bundles/equity_abnormal_activity/config.json`

Purpose: EventOverlayModel evidence row for abnormal stock/ETF price, volume, relative-strength, gap, or liquidity behavior.

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
- Can feed unified `trading_event` / `event_factor` projection later.

## Known Open Data Gaps

- Harden ETF-to-issuer mapping and ETF holdings freshness/available-time rules for production `stock_etf_exposure` runs.
- Calibrate equity abnormal activity thresholds/model standards against historical distributions before training labels consume them.
- Define optionability summary shape for SecuritySelectionModel; likely derived from option chain snapshots and liquidity filters.
- Define portfolio/account-state artifact owner for PortfolioRiskModel; likely outside `trading-data`.
