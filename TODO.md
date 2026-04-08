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
- [x] decide that reverse symbol map should not be a required retained artifact when constituent ETF context outputs already exist
- [x] remove reverse-symbol-map generation from the active ETF holdings pipeline and retire the old dedicated script

## Storage split / trading-storage

- [x] define the new `trading-storage` project as the storage-first sibling for downloaded/context/intermediate/report/output artifacts
- [ ] decide which current `trading-data` artifact families should remain repo-local versus move/copy into `trading-storage`
- [ ] document the boundary between code repos and the storage-only repo clearly enough that future artifact placement is consistent

## Macro / economic context

- [ ] define the canonical low-frequency macro/economic context contract under `context/macro/`
- [ ] add first FRED historical series fetcher with full-history backfill + append/update behavior
- [ ] add first BLS fetcher for key labor / inflation series
- [ ] add first BEA fetcher for GDP / spending-side series
- [ ] add first Census fetcher for key retail / housing/activity series
- [ ] add first Treasury Fiscal Data fetcher for selected fiscal/liquidity datasets
- [ ] add first Federal Reserve official event/calendar fetcher for FOMC and related policy events
- [x] define the initial core macro series set needed for bar-aligned downstream context
- [x] define the permanent market-regime benchmark universe and primary stored granularity for each retained market proxy
- [x] finalize the retained benchmark granularity plan as: 1m broad-beta/style layer, 30m rates-credit-fx-metals-sector layer, 1d volatility/commodity layer, plus original-frequency official macro series
- [ ] document how low-frequency macro series should later be joined to market bars via as-of alignment downstream
- [ ] keep macro/economic artifacts in append/upsert per-series files rather than market-tape-style month partitions

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

## Boundary cleanup after `trading-manager` split

- [x] make `trading-manager` the documented control-plane owner for scheduling / sequencing / retry policy
- [x] keep `trading-data` documentation focused on runnable fetch/build entrypoints plus artifact contracts
- [x] remove stale repo-local research/control-plane leftovers that still reference old `scripts/data/` and `data/raw|intermediate|derived|reports` layouts
- [x] review whether any remaining helper/state files in `trading-data` still imply manager ownership instead of artifact ownership
- [x] tighten signal payload semantics so they remain artifact-readiness signals rather than quasi workflow-state records
- [x] confirm the exact manager-facing callable contract for each stable `trading-data` entrypoint

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
