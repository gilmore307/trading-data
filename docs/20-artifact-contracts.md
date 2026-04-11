# 20 Artifact Contracts

This document defines the canonical retained-artifact contract for `trading-data` outputs.

## Durable destination rule
Durable outputs should land in `trading-storage`, not remain repo-local by default.

## Market-tape contract
Canonical retained market-tape artifacts live under `trading-storage/2_market_tape/1_data/`.

### Current dataset families
- `1_bars/<symbol>/<YYMM>/bars_1min.jsonl`
- `2_quotes/<symbol>/<YYMM>/quotes_1min.jsonl`
- `3_trades/<symbol>/<YYMM>/trades_1min.jsonl`
- `4_news/<symbol>/<YYMM>/news.jsonl`
- `5_options_snapshots/<symbol>/<YYMM>/options_snapshots.jsonl`

### Partition rule
- partition by symbol and business month
- use `America/New_York` business-month boundaries
- historical months are sealed after completion
- current/open month partitions may be rewritten safely

### Dedupe rule
- `bars_1min.jsonl`: one row per `(symbol, ts)`
- `quotes_1min.jsonl`: one row per `(symbol, minute)`
- `trades_1min.jsonl`: one row per `(symbol, minute)`
- `news.jsonl`: one row per `id`
- `options_snapshots.jsonl`: one row per `(option_symbol, ts)` within a month partition

### Re-run / existing-artifact rule
When a task starts and the target artifact path already exists, do not treat existence alone as success.

Current states:
- `missing` = target file absent
- `ready` = file exists, is readable, and any relevant completion evidence is consistent
- `partial` = file exists but appears incomplete/interrupted
- `invalid` = file exists but is not trustworthy
- `not_applicable` = this dataset family is not part of the required contract for the symbol/asset-class task being evaluated

Current action rule:
- `missing` -> run normally
- `ready` -> skip/reuse
- `partial` -> resume or rebuild the dataset
- `invalid` -> delete and rebuild

### Market-tape symbol capability contract
For ordinary market-tape symbol/month work, completion is based on the symbol's required dataset contract rather than on one universal five-family requirement.

Current pinned contract:
- `stocks` symbols, including ETF symbols when they are being treated as tradable symbols rather than regime context:
  - required = `bars`, `quotes`, `trades`, `news`, `options`
- `crypto` symbols (current validated example: `BTC/USD`):
  - required = `bars`, `news`
  - `quotes`, `trades`, and `options` are currently `not_applicable`

Interpretation rule:
- a tradable ETF such as `QQQ` still follows the full stock-symbol contract when it is being maintained as a market-tape symbol
- an ETF used under the separate regime ledger does **not** inherit this full market-tape contract; regime ETF/proxy work remains bars-only

### Compact month-directory rule
Supported month directories may include:
- shared `_meta.json`
- resumable sidecars such as `quotes_1min.state.json` and `trades_1min.state.json`

Current compact-contract mainline:
- `bars_1min`
- `quotes_1min`
- `trades_1min`
- `options_snapshots`

`news.jsonl` remains outside the compact row/meta split for now.

## Market-regime contract
Canonical low-frequency and cross-symbol context artifacts live under `trading-storage/1_market_regime/1_data/`.
Temporary execution traces for that work should live under `trading-storage/1_market_regime/4_temporary/`.

### Current families
- `macro/`
- `events_and_calendars/`
- `etf/<group_name>/...`
- signal/readiness evidence under `3_credentials/`, structurally aligned with the relevant `1_data/` paths

### Regime ETF/proxy bars contract
Mainline Alpaca regime ETF/proxy retention is now **bars-first**.

Canonical path pattern:
- `trading-storage/1_market_regime/1_data/etf/<group_name>/<SYMBOL>/<YYMM>/bars_<timeframe>.jsonl`

Current rule:
- the target timeframe is driven by `trading-storage/1_market_regime/0_management/market_regime_summary/market_regime_summary.csv`
- use the row's `target_bar_granularity` to choose the retained bars filename for that symbol
- current ETF granularity defaults are now grouped by `group_name`:
  - `1m`: `us_equity_core`, `commodities`, `usd_volatility`
  - `30m`: `rates_curve`, `credit`, `crypto_beta`, `sp500_sector`
  - `1d`: `thematic_growth`, `industry_chain`, `ark_thematic`
- do **not** reuse the ordinary market-tape bundle (`quotes / trades / news / options`) as the default regime contract
- old misplaced nested paths such as `<SYMBOL>/<SYMBOL>/<YYMM>/...` are legacy artifacts, not the active contract

Interpretation rule:
- manager readiness / preflight for regime rollforward should validate the symbol's configured bars artifact, not a hard-coded universal `bars_1min`
- if a symbol's `target_bar_granularity` changes later, the expected retained bars filename should change with it
- rolling readiness signal files for these artifacts should live under `1_market_regime/3_credentials/etf/<group_name>/<symbol>/...` instead of a permanent shared signals directory

### Macro/context rule
- prefer one durable append/upsert file per logical dataset or series
- do not force low-frequency context into market-tape-style month partitions
- preserve source/native frequency by default

## Cross-frequency interpretation rule
When low-frequency context is joined with higher-frequency market data downstream:
- aggregate higher-frequency market data upward to the research timeframe
- treat released macro values as as-of carry-forward state between official releases
- do not pretend low-frequency context has true higher-frequency resolution
