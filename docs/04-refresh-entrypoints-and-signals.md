# 04 Refresh Entrypoints and Signals

This document defines the stable refresh/build entrypoints exposed by `trading-data` and the artifact-level outputs they produce.

## Boundary rule

`trading-data` owns:
- runnable data refresh/build entrypoints
- canonical output contracts
- readiness signals attached to completed artifacts

`trading-data` does not own:
- scheduler selection
- queueing / sequencing policy
- cross-repo dependency state machines
- long-lived retry / recovery control-plane policy

Those control-plane concerns belong in `trading-manager`.

## Guiding split

There are two refresh rhythms and they stay separate:
1. market-tape refresh for Alpaca market data
2. context accumulation refresh for N-PORT ETF holdings and other non-market-tape context data

## 1. Alpaca monthly market-data backfill

Runner:
- `src/data/alpaca/update_previous_month_batch.py`

Behavior:
- backfill the previous completed month only
- define month windows using `America/New_York` month boundaries before converting request timestamps to UTC
- write into normal symbol/month market-tape partitions under `data/`
- preserve canonical per-dataset dedupe rules when rerun
- current retained quote/trade outputs are minute-level aggregate files (`quotes_1min.jsonl`, `trades_1min.jsonl`) rather than persisted raw event-tape multipart outputs
- emit a downstream-ready signal file under `context/signals/`

Current downstream signal meaning:
- `market_data_ready`

## 2. ETF holdings / N-PORT context refresh entrypoint

Runner:
- `src/data/nport/update_previous_month_etf_holdings.py`

Behavior:
- attempt discovery/availability for the previous month
- run extraction only when the target month appears available
- continue automatically into ETF data decomposition/output build for the configured ETF target list
- append the new month snapshot set into the permanent context family under `context/etf_holdings/<YYMM>/`
- build/update constituent ETF context outputs directly from the month holdings outputs
- update N-PORT capture state under the holdings context area
- emit a downstream-ready signal file under `context/signals/`

Current retained context artifacts include:
- per-ETF month outputs under `context/etf_holdings/<YYMM>/`
- month manifest under `context/etf_holdings/<YYMM>/_manifest_<YYMM>.json`
- downstream-ready constituent ETF context outputs under `context/constituent_etf_deltas/`

Interpretation rule:
- N-PORT holdings are month-addressed snapshots, but they still belong to the permanent context accumulation layer rather than to market-tape partitions
- the natural retained object is a context month snapshot family, not a `data/<symbol>/<YYMM>/` market-tape partition

Current downstream signal meaning:
- `etf_holdings_ready`

Historical-coverage rule:
- months earlier than the supported N-PORT coverage floor should not be treated as retryable publication delay
- those months should resolve to a stable non-applicable state such as `not_applicable_pre_nport`
- manager may continue forward month construction for the symbol after recording that state

## Partition state-file rule

For the current quote/trade minute builders, resumability should be derived from the retained month file itself rather than from a separate persistent state artifact.

Current rule:
- `quotes_1min` and `trades_1min` should resume from the existing month file tail when present
- successful quote/trade minute builds should not leave behind persistent `*.state.json` files
- the retained month file is the authoritative recovery source for quote/trade minute aggregation progress

## Downstream signal rule

Signals belong under:
- `context/signals/`

Signal payload rule:
- use artifact-readiness semantics only
- include stable fields such as:
  - `kind`
  - `source`
  - `pipeline`
  - `target_month`
  - `generated_at`
  - `contract_version`
  - `readiness`
  - `artifacts`
  - `results`
- do not embed downstream action instructions, scheduler policy, or quasi workflow-state claims inside the signal payload

## Manager-facing callable contract

### Alpaca previous-month batch
- command: `python3 src/data/alpaca/update_previous_month_batch.py --batch <batch_name>`
- expected final stdout JSON fields:
  - `signal_path`
  - `results`

### ETF holdings / N-PORT previous-month retry
- command: `python3 src/data/nport/update_previous_month_etf_holdings.py [--tier <tier> ...] [--symbol <symbol> ...]`
- expected final stdout JSON fields:
  - `available`
  - `captured`
  - `signal_path` when capture succeeds

## Manager integration rule

`trading-manager` decides:
- when monthly Alpaca backfill tasks run
- when retryable N-PORT calls are attempted
- how cross-repo dependency checks are sequenced
- how failures/retries/manual overrides are tracked over time
