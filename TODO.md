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

## Scope rule

`trading-data` should own:
- data acquisition
- source-specific fetch/build adapters under `src/`
- raw partitioning and retention rules
- canonical shared market-data contracts
- optional enrichment-data contracts

`trading-data` should not own:
- strategy family research
- composite construction logic
- ranking / selection logic
- live trading execution
