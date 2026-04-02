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
- [ ] implement first Alpaca acquisition entrypoints under `src/data/alpaca/`

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
