# 01_feed_alpaca_bars feed

Fetches Alpaca stock/ETF bars, normalizes timestamps to America/New_York, and writes the durable bar rows to SQL table `trading_data.model_01_market_regime_data_acquisition`.

Runtime storage keeps only compact provenance files such as `request_manifest.json`, `schema.json`, and `completion_receipt.json`. It does not retain `equity_bar.jsonl` or `equity_bar.csv` payload copies after SQL storage succeeds.

`<output_root>/completion_receipt.json` is a compact symbol-month summary. The run-local `<output_root>/runs/<run_id>/completion_receipt.json` records only that single run and must not duplicate the full symbol-month run history.
