# Model Input Data Organization

This document maps `trading-data` outputs and derived data products to the seven accepted `trading-model` layers. It is an organization contract, not a new raw-source acquisition plan.

## Principles

- Keep raw/source acquisition in source-specific bundles.
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
| `EventOverlayModel` | `event_overlay_model_inputs` | `gdelt_article`, SEC company financials/filings, `trading_economics_calendar_event`, `macro_release_event`, option activity, `equity_abnormal_activity_event` | Event overlay affects all earlier layers plus final risk gate. |
| `PortfolioRiskModel` | `portfolio_risk_model_inputs` | option contract data, positions, fills, PnL, cash/margin, exposures, risk limits, kill-switch state | Portfolio/account state is likely execution/account-owned, not pure `trading-data`. Historical simulation outputs may fill this during research. |

## Derived Data Products Added for Model Needs

### `stock_etf_exposure`

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
- May start model-local, but is registered as a data kind because it is likely useful across model/data boundaries.

### `equity_abnormal_activity_event`

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
- Can feed unified `trading_event` / `event_factor` projection later.

## Known Open Data Gaps

- Implement actual `stock_etf_exposure` builder after ETF-to-issuer mapping is accepted and ETF holdings freshness rules are defined.
- Implement actual equity abnormal activity detector after event thresholds/model standards are defined.
- Define optionability summary shape for SecuritySelectionModel; likely derived from option chain snapshots and liquidity filters.
- Define portfolio/account-state artifact owner for PortfolioRiskModel; likely outside `trading-data`.
