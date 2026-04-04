# TODO

## Initial bootstrap

- [x] create local clone of `trading-data`
- [x] seed initial documentation from `trading-model`
- [x] replace seeded docs with a fresh numbered `trading-data` doc set
- [x] move first-wave market-data acquisition code into this repo under `src/`
- [x] move first-wave canonical data-policy docs into this repo
- [x] define first-wave Alpaca adapter layout as the primary source structure
- [x] add tracked `data/` tree bootstrap for monthly-partitioned in-repo storage
- [x] define first-wave OKX/Bitget supplemental adapter layout as backup/enrichment source structure
- [x] define canonical raw/intermediate/derived/report/manifests structure
- [x] add repo to autosync watcher configuration
- [x] register project in workspace memory/handoff system
- [x] implement first Alpaca acquisition entrypoints under `src/data/alpaca/`
- [x] verify repo-local Alpaca `.env` auth flow and current-month batch refresh on approved sample universe
- [x] define first ETF/context universe for broad-market, sector, and thematic ETF candidates
- [x] prepare ETF/context data coverage for underlyings and broad-market proxies
- [x] add candidate ETF-context mapping skeleton for future relevance modeling downstream
- [x] add ETF holdings context layer under `context/etf_holdings/`
- [x] define normalized ETF holdings file schema and monthly accumulation behavior inside `context/etf_holdings/<ETF>.json`
- [x] decide whether ETF candidate discovery will use browser-assisted/manual etf.com exploration or a more automation-friendly source
- [x] record SEC Form N-PORT as a candidate authoritative ETF holdings source path
- [~] research SEC Form N-PORT ingestion details and schema mapping
- [x] design a system task that checks the N-PORT source path once per day until the current month's data becomes available, then stops for that month
- [x] define the N-PORT monthly availability signal and local state-tracking file behavior
- [x] add first runnable N-PORT availability-check scaffold under `src/data/common/`
- [x] add first runnable quarterly package discovery scaffold for SEC N-PORT zip datasets
- [x] add first runnable metadata/readme downloader for latest discovered N-PORT package
- [x] add first runnable compact holdings normalization scaffold for candidate N-PORT-like records
- [~] implement ETF ticker -> SEC fund/series/entity identifier mapping path
- [~] implement selective parsing of large N-PORT TSV tables into ETF-specific holdings outputs
- [x] define actionable ETF holdings target universe derived from the broader ETF context universe
- [x] add first N-PORT pipeline runner for the ETF holdings target universe
- [x] define monthly previous-month Alpaca batch-backfill automation strategy
- [x] define daily previous-month N-PORT retry automation strategy
- [x] emit downstream-ready signal files after successful refresh work
- [x] move N-PORT workflows into `src/data/nport/` as a dedicated source family
- [x] automatically continue from N-PORT acquisition into month-directory ETF mapping output build for the configured ETF target list
- [x] generate a month-level ETF holdings coverage manifest for auxiliary inspection
- [x] define `context/constituent_etf_deltas/<SYMBOL>.md` as the ready-to-use downstream ETF context artifact
- [x] add first per-symbol ETF monthly-context builder from monthly ETF holdings base snapshots
- [x] explicitly leave month-over-month delta calculation to downstream layers rather than precomputing it here

## Output compaction / storage efficiency

- [x] audit current tracked JSONL outputs for duplicate-write inflation
- [x] identify `options_snapshots.jsonl` append growth as the current main output-bloat path
- [x] convert Alpaca options snapshot fetcher to resumable canonical overwrite behavior
- [x] add a reusable output audit/compaction tool for safe in-place cleanup of supported datasets
- [x] compact existing duplicated AAPL options snapshot month files in place
- [ ] decide whether options snapshots should remain a single canonical row per `(option_symbol, ts)` or evolve into a more explicitly versioned/event-log contract later
- [x] evaluate whether other large low-change datasets deserve a similar row/meta split after the options path validation
- [x] add a small-file threshold rule so tiny month files do not grow because of sidecar-meta overhead
- [x] consolidate compatibility readers so downstream code has one obvious import path for logical full-row reads
- [ ] decide whether news should stay as-is or also adopt a row/meta split when larger month files accumulate
- [ ] if news volume grows materially, decide whether `source_name` should stay row-level or move into compact month metadata when constant within a month file

## Control-plane responsibility migration to `trading-manager`

The new `trading-manager` repo will absorb part of the orchestration/storage-lifecycle responsibility that should not remain embedded inside `trading-data`.

### Migrate out of `trading-data`
- [ ] move managed-symbol onboarding/request handling into `trading-manager` as a control-plane workflow (while keeping the actual data-fetch/build entrypoints in `trading-data`)
- [ ] move recurring refresh scheduling/timing policy into `trading-manager`; `trading-data` should expose runnable refresh/build entrypoints but not be the long-term scheduler brain
- [ ] move local cleanup eligibility decisions for completed historical scopes into `trading-manager`
- [ ] move cold-archive / rehydration orchestration for completed `symbol + month` scopes into `trading-manager`
- [ ] keep `trading-data` focused on canonical data production, signals, and artifact contracts while removing cross-repo orchestration assumptions over time

### Keep in `trading-data`
- acquisition/fetch/build logic
- source adapters
- canonical month-partitioned storage contract
- downstream-ready signal emission
- data/context artifact definitions

## Scope rule

`trading-data` should own:
- data acquisition
- source-specific fetch/build adapters under `src/`
- raw partitioning and retention rules
- canonical shared market-data contracts
- optional enrichment-data contracts
- runnable refresh/build entrypoints that `trading-manager` can call
- downstream-ready signal emission and data artifact contracts

`trading-data` should not own:
- managed-symbol orchestration policy
- long-term refresh scheduling brain
- cross-repo workflow sequencing
- archive/rehydration control-plane decisions across the trading stack
- strategy family research
- composite construction logic
- ranking / selection logic
- live trading execution
