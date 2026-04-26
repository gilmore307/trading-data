# Task

## Active Tasks

- None.

## Queued Tasks

- Define data provider shortlist and selection criteria for market board, instrument, and option data.
- Define initial data request schema with `trading-main`.
- Define data artifact reference and manifest requirements with `trading-main` and `trading-storage`.
- Define source connector layout and provider inventory format.
- Define secret alias names for first provider credentials through `trading-main` once providers are selected.
- Define raw vs normalized artifact policy.
- Define fixture storage policy for provider responses.
- Define first implementation skeleton after contracts are clear.
- Add unit/fixture test harness once source layout is introduced.

## Open Gaps

- Exact external data providers.
- Secret-alias names for provider credentials.
- Provider quota/rate-limit policy.
- Exact data request schema.
- Exact data artifact schema and reference format.
- Exact manifest and ready-signal schema.
- Shared storage root and partition layout.
- Timestamp/timezone normalization rules.
- Fixture policy and whether recorded provider responses may be stored.
- First supported market/instrument/granularity.
- Data-domain vocabulary registration in `trading-main` if exact domain keys become cross-repository contract values.

## Recently Accepted

- Added optional data-domain and data-source docs for the three data/model lanes and provider connection boundary.
- Created initial `trading-data` docs spine and repository boundary.
- Added initial `.gitignore` for local environments, generated data, artifacts, logs, and secrets.
