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
- [ ] define canonical raw/intermediate/derived/report/manifests structure
- [x] add repo to autosync watcher configuration
- [x] register project in workspace memory/handoff system
- [x] implement first Alpaca acquisition entrypoints under `src/data/alpaca/`
- [x] define first ETF/context universe for broad-market, sector, and thematic ETF candidates
- [ ] prepare ETF/context data coverage for underlyings and broad-market proxies
- [ ] add candidate ETF-context mapping skeleton for future relevance modeling downstream
- [x] add ETF holdings context layer under `context/etf_holdings/`
- [ ] define normalized ETF holdings file schema and monthly accumulation behavior inside `context/etf_holdings/<ETF>.json`
- [ ] decide whether ETF candidate discovery will use browser-assisted/manual etf.com exploration or a more automation-friendly source
- [x] record SEC Form N-PORT as a candidate authoritative ETF holdings source path
- [ ] research SEC Form N-PORT ingestion details and schema mapping
- [ ] design a system task that checks the N-PORT source path once per day until the current month's data becomes available, then stops for that month

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
