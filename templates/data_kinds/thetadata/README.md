# ThetaData Option Data Kind Templates

ThetaData is the canonical options source. Option acquisition is split by use case, not by endpoint family.

## Bundles

### `thetadata_option_selection_snapshot`

Produces point-in-time option-chain snapshots used to train or apply a future option-selection model. This bundle saves the complete visible, unexpired option chain returned for the requested underlying/snapshot context. It does **not** select contracts and does **not** filter by liquidity, bid/ask, spread, IV, or Greeks availability.

Final output:

- `option_chain_snapshot` — JSON artifact; see `option_chain_snapshot.preview.json`.

### `thetadata_option_primary_tracking`

Tracks a specified option contract passed as task parameters. Contract selection is out of scope; the selected contract is an input.

Final output:

- `option_bar` — CSV artifact; see `option_bar.preview.csv`.

### `thetadata_option_event_timeline`

Reports only option-activity events. It may use transient 30Min window state and periodic option-chain snapshots for IV context, but final output contains only triggered events. `headline` is a human-facing news-style title; `summary` carries only triggered abnormal indicator details.

Final output:

- `option_activity_event` — CSV artifact using the same timeline/news fields as `equity_news`; see `option_activity_event.preview.csv`.

## Template notes

- `option_chain_snapshot` is intentionally JSON because one snapshot contains nested contracts with quote, IV, Greeks, and underlying context.
- Flat bars/events remain CSV.
- Raw `option_trade`, `option_quote`, and `option_nbbo` rows are source inputs unless explicitly accepted as final outputs later.
- Professional-only second/third-order Greeks and trade Greeks remain excluded under the current STANDARD entitlement.

## `option_chain_snapshot`

- **Source:** ThetaData Terminal v3.
- **Bundle:** `thetadata_option_selection_snapshot`.
- **Status:** `preview-confirmed`.
- **Persistence policy:** Persist complete nested JSON snapshot. Do not filter contracts; do not persist raw provider responses separately.
- **Earliest available range:** `unknown`; live preview confirmed AAPL chain snapshot with 3120 contracts for 2026-04-24 latest-visible timestamps.
- **Default timestamp semantics:** `snapshot_time_et` records requested/receipt context when available; contract quote/IV/Greeks timestamps remain per-contract ET timestamps.
- **Natural grain:** One snapshot artifact per underlying/snapshot request, containing many contracts.
- **Request parameters:** `underlying`, `snapshot_time` or provider-supported latest snapshot context; optional expiration filters only if explicitly requested.
- **Pagination/range behavior:** Source returns full visible chain response for requested underlying/expiration scope; no contract filtering in this template.
- **Preview file:** see `option_chain_snapshot.preview.json`.
- **Known caveats:** ThetaData snapshot rows carry per-contract latest timestamps, not one guaranteed identical timestamp across all contracts.

## `option_bar`

- **Source:** ThetaData Terminal v3 `/v3/option/history/ohlc`.
- **Bundle:** `thetadata_option_primary_tracking`.
- **Status:** `preview-confirmed`.
- **Persistence policy:** Persist final aggregated contract bars as CSV. Raw 1Sec source rows are transient.
- **Earliest available range:** `unknown`; live preview confirmed AAPL 2026-05-15 270 CALL on 2026-04-24.
- **Default timestamp semantics:** `timestamp_et` in `America/New_York`.
- **Natural grain:** One option contract/timeframe/timestamp bar.
- **Request parameters:** `underlying`, `expiration`, `right`, `strike`, `start_date`, `end_date`, `timeframe`.
- **Pagination/range behavior:** Segment by contract and date range; `timeframe` is an input parameter and final rows should aggregate transient 1Sec OHLC to requested grain.
- **Preview file:** see `option_bar.preview.csv`.
- **Known caveats:** ThetaData 1Sec OHLC may include zero-volume placeholder rows; final aggregation must not treat zero-volume placeholders as real trades.

## `option_activity_event`

- **Source:** ThetaData Terminal v3, primarily `/v3/option/history/trade_quote`, with optional transient chain snapshot context for IV anomaly metrics.
- **Bundle:** `thetadata_option_event_timeline`.
- **Status:** `preview-designed`.
- **Persistence policy:** Persist triggered event rows only as CSV. Do not persist process data, transient trade_quote rows, or periodic chain snapshots in this bundle.
- **Earliest available range:** `unknown`; trade_quote live preview confirmed AAPL 2026-05-15 270 CALL on 2026-04-24.
- **Default timestamp semantics:** `created_at_et` is the event source time and `updated_at_et` is the detection/report time, both in `America/New_York`.
- **Natural grain:** One detected option-activity event.
- **Request parameters:** `underlying`, optional contract fields, `start_date`, `end_date`, `timeframe` default `30Min`, event threshold params.
- **Pagination/range behavior:** Process trade_quote rows within rolling/window state; periodic option_chain_snapshot every `timeframe` can provide IV cross-section context. Emit immediately when thresholds are met; do not wait for the full bar/window to close.
- **Preview file:** see `option_activity_event.preview.csv`.
- **Known caveats:** This output intentionally reuses the news/timeline schema. `headline` is human-facing and should mention only triggered abnormal indicators. `summary` carries only triggered abnormal indicator names/details; normal metrics and event scoring are omitted and belong to downstream models.
