# ThetaData Option Data Kind Templates

ThetaData is the canonical options source. Option acquisition is split by use case, not by endpoint family.

## Bundles

### `thetadata_option_selection_snapshot`

Produces point-in-time option-chain snapshots used to train or apply a future option-selection model. This bundle saves the complete visible, unexpired option chain returned for the requested underlying/snapshot context. It does **not** select contracts and does **not** filter by liquidity, bid/ask, spread, IV, or Greeks availability.

Final output:

- `option_chain_snapshot` — CSV artifact with JSON text columns; see `option_chain_snapshot.preview.csv`.

### `thetadata_option_primary_tracking`

Tracks a specified option contract passed as task parameters. Contract selection is out of scope; the selected contract is an input.

Final output:

- `option_bar` — CSV artifact; see `option_bar.preview.csv`.

### `thetadata_option_event_timeline`

Reports only option-activity events. It may use transient 30Min window state and periodic option-chain snapshots for IV context, but final timeline output contains only triggered events. `headline` is a human-facing news-style title; `summary` carries only triggered abnormal indicator type names. Each event row has a stable random `id` and links through `url` to `<id>.csv`, a compact SQL-shaped detail row for the full event context.

Final output:

- `option_activity_event` — CSV artifact using the same minimal timeline/news fields as `equity_news`; see `option_activity_event.preview.csv`.
- `option_activity_event_detail` — CSV artifact keyed by event `id` with JSON text context columns; see `option_activity_event_detail.preview.csv`.

## Template notes

- `option_chain_snapshot` is now represented as CSV with a `contracts` JSON text column because the CSV preview must match the future SQL long-term row shape.
- `option_activity_event_detail` is now represented as CSV with JSON text context columns because the CSV preview must match the future SQL long-term row shape.
- Flat bars/events remain CSV.
- Raw `option_trade`, `option_quote`, and `option_nbbo` rows are source inputs unless explicitly accepted as final outputs later.
- Professional-only second/third-order Greeks and trade Greeks remain excluded under the current STANDARD entitlement.

## Reusable nested field groups

The option templates reuse common nested leaf names where their semantics match:

- Quote context: `bid`, `ask`, `mid`, `spread`, `bid_size`, `ask_size`, `spread_pct`, `bid_exchange`, `ask_exchange`, `bid_condition`, `ask_condition`.
- IV context: `implied_vol`, `iv_error`, `iv_percentile_by_expiration`, `iv_rank_in_expiration`, `iv_zscore_by_expiration`.
- Greeks context: `delta`, `theta`, `vega`, `rho`, `epsilon`, `lambda`.
- Underlying context: `underlying_price`, `underlying_timestamp`.
- Window context: `window_start`, `window_end`, `window_trade_count`, `window_volume`, `window_notional`.

Scenario-specific event-detail metrics keep explicit event names, such as `price_vs_ask` and `ask_touch_ratio`.

## `option_chain_snapshot`

- **Source:** ThetaData Terminal v3.
- **Bundle:** `thetadata_option_selection_snapshot`.
- **Status:** `preview-confirmed`.
- **Persistence policy:** Persist one SQL-shaped snapshot row; nested visible contracts are encoded as a JSON text/JSONB payload column. Do not filter contracts; do not persist raw provider responses separately.
- **Earliest available range:** `unknown`; live preview confirmed AAPL chain snapshot with 3120 contracts for 2026-04-24 latest-visible timestamps.
- **Default timestamp semantics:** `snapshot_time` records requested/receipt context when available; contract quote/IV/Greeks timestamps remain per-contract ET timestamps.
- **Natural grain:** One snapshot artifact per underlying/snapshot request, containing many contracts.
- **Request parameters:** `underlying`, `snapshot_time`. The caller must provide an explicit `America/New_York` snapshot datetime; no implicit latest/current mode is supported.
- **Pagination/range behavior:** Source returns full visible chain response for requested underlying/expiration scope; no contract filtering in this template. Development preview is CSV; durable production storage should map the JSON text payload to SQL JSONB.
- **Preview file:** see `option_chain_snapshot.preview.csv`.
- **Known caveats:** ThetaData snapshot rows carry per-contract latest timestamps, not one guaranteed identical timestamp across all contracts.

## `option_bar`

- **Source:** ThetaData Terminal v3 `/v3/option/history/ohlc`.
- **Bundle:** `thetadata_option_primary_tracking`.
- **Status:** `implemented`.
- **Persistence policy:** Persist final aggregated contract bars as CSV. Raw 1Sec source rows are transient.
- **Earliest available range:** `unknown`; live preview confirmed AAPL 2026-05-15 270 CALL on 2026-04-24.
- **Default timestamp semantics:** `timestamp` in `America/New_York`.
- **Natural grain:** One option contract/timeframe/timestamp bar.
- **Request parameters:** `underlying`, `expiration`, `right`, `strike`, `start_date`, `end_date`, `timeframe`.
- **Pagination/range behavior:** Segment by contract and date range; `timeframe` is an input parameter and final rows should aggregate transient 1Sec OHLC to requested grain.
- **Preview file:** see `option_bar.preview.csv`.
- **Known caveats:** ThetaData 1Sec OHLC may include zero-volume placeholder rows; final aggregation skips rows whose `volume` and `count` are both zero. VWAP is calculated from active 1Sec close × volume because the source OHLC `vwap` field is not treated as a per-second trade VWAP.

## `option_activity_event`

- **Source:** ThetaData Terminal v3, primarily `/v3/option/history/trade_quote`, with optional transient chain snapshot context for IV anomaly metrics.
- **Bundle:** `thetadata_option_event_timeline`.
- **Status:** `implemented`.
- **Persistence policy:** Persist triggered event rows as CSV plus one compact detail JSON per event. Do not persist process data, transient trade_quote rows, or periodic chain snapshots in this bundle.
- **Earliest available range:** `unknown`; trade_quote live preview confirmed AAPL 2026-05-15 270 CALL on 2026-04-24.
- **Default timestamp semantics:** `created_at` is the event source time and `updated_at` is the detection/report time, both in `America/New_York`.
- **Natural grain:** One detected option-activity event using the shared model-facing timeline fields: `id`, `headline`, `created_at`, `updated_at`, `symbols`, `summary`, `url`.
- **Request parameters:** `underlying`, `expiration`, `right`, `strike`, `start_date`, `end_date`, `timeframe`, and task/model `current_standard` params.
- **Pagination/range behavior:** Process trade_quote rows within event-window state; optional `iv_context` can provide IV cross-section context. Emit a final row only when the supplied event-time `current_standard` is satisfied.
- **Preview file:** see `option_activity_event.preview.csv`.
- **Known caveats:** This output intentionally reuses the simplified news/timeline schema. `id` is a stable random event id, not a semantic timestamp/contract id. `headline` is human-facing and should mention only triggered abnormal indicators. `summary` carries only abnormal indicator type names such as `trade_at_ask;opening_activity`; normal metrics and event scoring are omitted and belong to downstream models. `url` is `<id>.csv` and links to the event detail artifact rather than to an external article. Current implementation evaluates supplied `trade_at_ask`, `opening_activity`, and optional `iv_high_cross_section` standards; model-standard identity/versioning remains downstream `trading-model` work.

## `option_activity_event_detail`

- **Source:** ThetaData Terminal v3, derived from event trigger state and bounded event-local context.
- **Bundle:** `thetadata_option_event_timeline`.
- **Status:** `preview-designed`.
- **Persistence policy:** Persist one SQL-shaped CSV detail row only for emitted option activity events. Do not persist full rolling-window raw rows or periodic chain snapshots by default.
- **Earliest available range:** Same as `option_activity_event`.
- **Default timestamp semantics:** `created_at`, `updated_at`, and nested timestamps use `America/New_York`.
- **Natural grain:** One detail row per detected option-activity event, keyed by `event_id` matching the CSV row stable random `id`.
- **Request parameters:** Same as `option_activity_event`.
- **Pagination/range behavior:** Written only when an event is emitted; the CSV row `url` points to the detail row/artifact as `<id>.csv`.
- **Preview file:** see `option_activity_event_detail.preview.csv`.
- **Known caveats:** Detail row is an evidence/context artifact, not a dump of all transient provider rows. `triggered_indicators` is an object keyed by abnormal indicator type; each child object owns objective observed `statistics` and the event-time `current_standard` produced by the detection model. `current_standard` is not a global fixed rule value; it is the standard used by the model for this event and may change across model versions/runs. It should be enough to audit why the event fired while keeping high-volume source rows transient.
