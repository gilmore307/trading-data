# Macro Data Kind Templates

Macro templates are SQL-shaped long-term CSV rows. The durable table stores release events only; model training jobs later expand release intervals into daily Parquet feature matrices.

### `macro_release`

- **Source:** Official macro providers through `macro_data` acquisition tasks.
- **Bundle:** `macro_data`.
- **Status:** `designed`.
- **Persistence policy:** Persist one row per released metric value. Do not duplicate unchanged values for every model date.
- **Earliest available range:** source-specific; use provider/task evidence before claiming a range.
- **Default timestamp semantics:** `release_time` and `effective_until` are `America/New_York` ISO datetimes.
- **Natural grain:** One macro metric release interval: `metric`, `release_time`, `effective_until`, `value`.
- **Request parameters:** source-specific macro task parameters; the normalized saved row must resolve to the four long-term fields.
- **Pagination/range behavior:** Source-specific fetches normalize into sparse release rows; training builders forward-fill by `release_time <= model_time < effective_until`.
- **Preview file:** see `macro_release.preview.csv`.
- **Known caveats:** No `region`, `source_id`, or vintage fields are included until a concrete model or audit use case requires them. If revisions become part of training semantics, add them through registry/migration rather than ad hoc columns.
