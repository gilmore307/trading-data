# Task

## Active Tasks

- None.

## Queued Tasks

- Define remaining data provider shortlist and selection criteria for non-OKX market board, instrument, and option data needs.
- Define initial manager-issued data task key file schema with `trading-main`.
- Define data artifact reference and manifest requirements with `trading-main` and `trading-storage`.
- Define storage-resident data task completion receipt schema with `trading-main` and `trading-storage`.
- Define storage SQL table/partition contract for data-task outputs.
- Define source connector layout and provider inventory format.
- Finalize historical acquisition script bundle names and invocation contract.
- Define macro release event inventory, release-key naming, and per-release bundle boundaries.
- Define any additional provider secret alias names through `trading-main` once providers are selected.
- Define ThetaData connector, ThetaTerminal JAR, and creds.txt placement policy.
- Define raw vs normalized artifact policy.
- Define fixture storage policy for provider responses.
- Define first implementation skeleton after contracts are clear.
- Add unit/fixture test harness once source layout is introduced.

## Open Gaps

- Exact external data providers beyond OKX.
- Secret-alias names for any provider credentials beyond registered OKX aliases.
- Provider quota/rate-limit policy.
- Exact manager task key file/request schema.
- Exact data artifact schema and reference format.
- Exact completion receipt schema and storage location.
- Exact storage SQL table/partition destination contract.
- Exact manifest and ready-signal schema.
- Shared storage root and partition layout.
- Timestamp/timezone normalization rules.
- Fixture policy and whether recorded provider responses may be stored.
- First supported market/instrument/granularity.
- Data-domain vocabulary registration in `trading-main` if exact domain keys become cross-repository contract values.

## Recently Accepted

- Re-scoped macro acquisition from one broad bundle into per-release-event bundles based on publication time/cadence.
- Formalized manager-driven historical data task workflow: task key file in, specified historical script executes, SQL output target written, storage-resident completion receipt produced.
- Recorded FOMC calendar, official macro release calendar discovery, and ETF issuer holdings source-of-truth rules.
- Recorded U.S. Treasury Fiscal Data as an open/no-key provider term with documentation path.
- Added provider documentation URLs to data-source planning docs, matching registry provider term paths.
- Recorded FRED, Census, BEA, and BLS as registered economic/macro provider config surfaces using source-level secret aliases.
- Recorded ThetaData as registered provider terminology for option data, with connector/JAR/credential layout deferred.
- Recorded Alpaca as first registered stock/ETF data provider config surface using source-level secret alias `alpaca`.
- Recorded OKX as first registered crypto provider config surface using a `trading-main` source-level secret alias and non-secret metadata.
- Added optional data-domain and data-source docs for the three data/model lanes and provider connection boundary.
- Created initial `trading-data` docs spine and repository boundary.
- Added initial `.gitignore` for local environments, generated data, artifacts, logs, and secrets.
