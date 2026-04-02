# Data Ingestion Architecture

This document isolates the `crypto-trading` data ingestion layer from downstream research and runtime consumers.

## Scope

The ingestion layer is responsible for:

- extending existing symbol datasets to the latest available data
- bootstrapping new symbols from a chosen start point
- writing canonical raw data directly into monthly partitions
- keeping storage layout aligned with the `data` repo structure

It is **not** responsible for:

- building research datasets
n- strategy utility artifacts
- runtime execution decisions

## Two supported ingestion modes

### 1. Extend existing data

Use this when a symbol/dataset already exists.

Behavior:

- inspect existing monthly files under `raw/<symbol>/<dataset>/`
- continue from the latest known timestamp
- append/update only the currently open month and any missing recent month partitions
- do not rebuild a whole-history monolith first

### 2. Bootstrap a new symbol

Use this when a symbol does not exist yet.

Behavior:

- choose an explicit start point
- fetch historical data directly into month files
- write each month partition as canonical storage from the beginning
- avoid the old pattern of downloading one giant file and splitting later

## Canonical raw layout

Raw storage should use short project-oriented paths:

- `raw/<symbol>/candles/<YYYY-MM>.jsonl`
- `raw/<symbol>/funding/<YYYY-MM>.jsonl`
- `raw/<symbol>/basis_proxy/<YYYY-MM>.jsonl`
- additional datasets should follow:
  - `raw/<symbol>/<dataset>/<YYYY-MM>.jsonl`

Examples:

- `raw/BTC-USDT-SWAP/candles/2026-04.jsonl`
- `raw/BTCUSDT/funding/2026-04.jsonl`
- `raw/BTCUSDT/basis_proxy/2026-04.jsonl`

## Month boundary rule

Canonical partition boundaries follow the project business month policy:

- month key timezone: `America/New_York`
- file name: `YYYY-MM.jsonl`

## Current ingestion entrypoints

- `scripts/data/fetch_okx_history_candles.py`
- `scripts/data/fetch_bitget_derivatives_context.py`

These scripts now write directly to monthly partition directories instead of first producing a whole-history monolith.

## Downstream contract

Downstream consumers should read either:

- a single JSONL file
- or a directory of monthly JSONL partitions

Shared loader:

- `src/research/monthly_jsonl.py`

Current downstream consumers already moving to this contract:

- `src/runners/build_crypto_market_state_dataset.py`
- `src/runners/build_ma_parameter_utility_dataset.py`
- `src/runners/build_donchian_parameter_utility_dataset.py`
- `src/runners/build_bollinger_parameter_utility_dataset.py`

## Pending completion work

Before monthly automation is registered, finish these items:

- earliest-available discovery for new symbols
- explicit month-level progress tracking for bootstrap runs
- incomplete-month safeguards / markers
- end-to-end validation from ingestion -> research dataset build -> utility dataset build

## Cleanup policy

Once this ingestion layer is fully stable and all callers are moved over, legacy one-off fetch paths and transitional scripts can be audited and removed with confidence.
