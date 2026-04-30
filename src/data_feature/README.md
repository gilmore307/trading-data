# data_feature

Deterministic point-in-time feature builders owned by `trading-data`.

## Boundary

Feature packages transform accepted feed/source data into model-facing feature tables. They do not call providers directly and do not own model outputs, labels, evaluation runs, or promotion decisions.

## Packages

- `feature_01_market_regime/` — Layer 1 MarketRegimeModel V1 feature generator and SQL runner for `trading_data.feature_01_market_regime`.
