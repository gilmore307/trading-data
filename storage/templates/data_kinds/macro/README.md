# Macro Data Kind Templates

Macro provider values are normalized here as transient source evidence. `macro_release_event` in `../events/` is the final saved/model-facing market-impact event created by a macro publication. Market-state models should use index/ETF price-volume data; event models should use macro release events to explain shocks and abnormal moves.

### `macro_release`

- **Source:** Official macro providers through `macro_data` acquisition tasks.
- **Bundle:** `macro_data`.
- **Status:** `transient-evidence`.
- **Persistence policy:** Keep one cleaned run-local evidence row per released metric value. Do not save as final/model-facing CSV and do not use as an independent alpha table.
- **Earliest available range:** source-specific; use provider/task evidence before claiming a range.
- **Default timestamp semantics:** `release_time` and `effective_until` are `America/New_York` ISO datetimes.
- **Natural grain:** One macro metric release interval: `metric`, `release_time`, `effective_until`, `value`.
- **Request parameters:** source-specific macro task parameters; the normalized cleaned row must resolve to the four evidence fields.
- **Pagination/range behavior:** Source-specific fetches normalize into sparse release evidence rows; final event projection emits `macro_release_event` rows.
- **Preview file:** retained only as a transient evidence shape reference; not a final saved output.
- **Known caveats:** No `region`, `source_id`, or vintage fields are included until a concrete model or audit use case requires them. If revisions become part of training semantics, add them through registry/migration rather than ad hoc columns. Consensus/surprise is not assumed from official macro APIs; `macro_release_event` leaves surprise semantics pending until a legal/stable consensus source is accepted.

### Event projection

Every cleaned `macro_release` evidence row from the `macro_data` bundle emits a final `saved/macro_release_event.csv` row. The event row uses `event_type=macro_release_event`, `source_type=official_macro_release`, and defaults to `impact_scope=market`, `impacted_universe=US_MARKET;rates;USD;equities`, and `primary_impact_target=US_MARKET` unless task params override those values.
