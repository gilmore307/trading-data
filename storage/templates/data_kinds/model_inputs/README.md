# Model input data-kind templates

This directory owns preview shapes for derived model-input data products that are not raw provider tables but are important enough to register as shared data kinds.

Boundary:

- Source acquisition remains in source-specific bundles such as Alpaca, ETF holdings, GDELT, SEC, and ThetaData.
- Model-input data kinds are point-in-time derived rows used to connect data outputs to `trading-model` layer needs.
- Generated model features/artifacts should not be committed here; this directory only owns tiny schema previews.

Current templates:

- `stock_etf_exposure.preview.csv` — stock-to-ETF exposure row used by `SecuritySelectionModel` to transmit ETF/sector/theme strength into candidate symbol selection.
