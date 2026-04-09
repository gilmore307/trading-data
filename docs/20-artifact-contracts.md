# 20 Artifact Contracts

This document defines the canonical retained-artifact contract for `trading-data` outputs.

## Durable destination rule
Durable outputs should land in `trading-storage`, not remain repo-local by default.

## Market-tape contract
Canonical retained market-tape artifacts live under `trading-storage/2_market_tape/2_rolling/`.

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

Current action rule:
- `missing` -> run normally
- `ready` -> skip/reuse
- `partial` -> resume or rebuild the dataset
- `invalid` -> delete and rebuild

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
Canonical low-frequency and cross-symbol context artifacts live under `trading-storage/1_market_regime/1_permanent/`.
Temporary execution traces for that work should live under `trading-storage/1_market_regime/3_temporary/`.

### Current families
- `1_macro/`
- `2_broad_beta/`
- `3_rates_credit_fx_metals/`
- `4_sector_rotation/`
- `5_volatility_and_commodity/`
- `6_crypto_proxy/`
- `7_events_and_calendars/`
- `8_signals/`

### Macro/context rule
- prefer one durable append/upsert file per logical dataset or series
- do not force low-frequency context into market-tape-style month partitions
- preserve source/native frequency by default

## Cross-frequency interpretation rule
When low-frequency context is joined with higher-frequency market data downstream:
- aggregate higher-frequency market data upward to the research timeframe
- treat released macro values as as-of carry-forward state between official releases
- do not pretend low-frequency context has true higher-frequency resolution
