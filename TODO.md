# TODO

## Initial bootstrap

- [x] create local clone of `trading-data`
- [x] seed initial documentation from `trading-model`
- [ ] rewrite seeded docs so they speak purely from the upstream data-repository perspective
- [ ] move market-data acquisition scripts into this repo
- [ ] move canonical data-policy docs into this repo
- [ ] define Alpaca adapter layout
- [ ] define crypto supplemental adapter layout
- [ ] define canonical raw/intermediate/derived/report/manifests structure
- [ ] add repo to autosync watcher configuration
- [ ] register project in workspace memory/handoff system

## Scope rule

`trading-data` should own:
- data acquisition
- source-specific fetch/build adapters
- raw partitioning and retention rules
- canonical shared market-data contracts
- optional enrichment-data contracts

`trading-data` should not own:
- strategy family research
- composite construction logic
- ranking / selection logic
- live trading execution
