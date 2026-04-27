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

Reports only option-activity events. It may use transient 30Min window state and periodic option-chain snapshots for IV context, but final timeline output contains only triggered events. `headline` is a human-facing news-style title; `summary` carries only triggered abnormal indicator type names. Each event row has a stable random `id` and links through `url` to `<id>.json`, a compact detail JSON artifact for the full event context.

Final output:

- `option_activity_event` — CSV artifact using the same minimal timeline/news fields as `equity_news`; see `option_activity_event.preview.csv`.
- `option_activity_event_detail` — JSON artifact keyed by event `id`; see `option_activity_event_detail.preview.json`.

## Template notes

- `option_chain_snapshot` is intentionally JSON because one snapshot contains nested contracts with quote, IV, Greeks, and underlying context.
- `option_activity_event_detail` is intentionally JSON because one event can carry nested contract, quote, IV, trigger, and source-reference context.
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
- **Persistence policy:** Persist triggered event rows as CSV plus one compact detail JSON per event. Do not persist process data, transient trade_quote rows, or periodic chain snapshots in this bundle.
- **Earliest available range:** `unknown`; trade_quote live preview confirmed AAPL 2026-05-15 270 CALL on 2026-04-24.
- **Default timestamp semantics:** `created_at_et` is the event source time and `updated_at_et` is the detection/report time, both in `America/New_York`.
- **Natural grain:** One detected option-activity event using the shared model-facing timeline fields: `data_kind`, `id`, `headline`, `created_at_et`, `updated_at_et`, `symbols`, `summary`, `url`.
- **Request parameters:** `underlying`, optional contract fields, `start_date`, `end_date`, `timeframe` default `30Min`, event standard/model params.
- **Pagination/range behavior:** Process trade_quote rows within rolling/window state; periodic option_chain_snapshot every `timeframe` can provide IV cross-section context. Emit immediately when the event-time `current_standard` is satisfied; do not wait for the full bar/window to close.
- **Preview file:** see `option_activity_event.preview.csv`.
- **Known caveats:** This output intentionally reuses the simplified news/timeline schema. `id` is a stable random event id, not a semantic timestamp/contract id. `headline` is human-facing and should mention only triggered abnormal indicators. `summary` carries only abnormal indicator type names such as `trade_at_ask;opening_activity`; normal metrics and event scoring are omitted and belong to downstream models. `url` is `<id>.json` and links to the event detail artifact rather than to an external article.

## `option_activity_event_detail`

- **Source:** ThetaData Terminal v3, derived from event trigger state and bounded event-local context.
- **Bundle:** `thetadata_option_event_timeline`.
- **Status:** `preview-designed`.
- **Persistence policy:** Persist compact nested JSON only for emitted option activity events. Do not persist full rolling-window raw rows or periodic chain snapshots by default.
- **Earliest available range:** Same as `option_activity_event`.
- **Default timestamp semantics:** `created_at_et`, `updated_at_et`, and nested timestamps use `America/New_York`.
- **Natural grain:** One detail JSON document per detected option-activity event, keyed by `event_id` matching the CSV row stable random `id`.
- **Request parameters:** Same as `option_activity_event`.
- **Pagination/range behavior:** Written only when an event is emitted; the CSV row `url` points to the detail document as `<id>.json`.
- **Preview file:** see `option_activity_event_detail.preview.json`.
- **Known caveats:** Detail JSON is an evidence/context artifact, not a dump of all transient provider rows. `triggered_indicators` is an object keyed by abnormal indicator type; each child object owns objective observed `statistics` and the event-time `current_standard` produced by the detection model. `current_standard` is not a global fixed rule value; it is the standard used by the model for this event and may change across model versions/runs. It should be enough to audit why the event fired while keeping high-volume source rows transient.
