# TODO

## Core contracts
- [x] define `trading-data` as the code-first upstream data repo
- [x] define stable manager-facing fetch/build entrypoints
- [x] define retained market-tape contracts for bars / quotes / trades / news / options snapshots
- [x] define artifact-readiness signal semantics that stay separate from manager control-plane state
- [ ] formalize one final standard retained-artifact contract across bars / quote aggregates / trade aggregates / news / options so every market-data family has explicit canonical grain, dedupe rule, and storage path

## Storage migration
- [x] define the boundary between code repos and `trading-storage`
- [x] repath active market-tape writes into `trading-storage/2_market_tape/`
- [x] repath macro / calendar / signal writes into `trading-storage/1_market_regime/`
- [x] repath compaction / normalize tools away from repo-local `data/` and toward `trading-storage`
- [ ] run clean-storage validation to confirm every active entrypoint lands in the intended storage partitions
- [x] add a single-symbol / single-month Alpaca refresh entrypoint so manager periodic regime rows do not have to misuse shared batch workflows

## Market-tape acquisition
- [x] implement first Alpaca acquisition entrypoints under `src/data/alpaca/`
- [x] verify repo-local Alpaca `.env` auth flow and sample refresh capability
- [x] define monthly previous-month Alpaca batch-backfill strategy
- [x] emit downstream-ready signal files after successful month refresh work
- [ ] decide whether options snapshots should remain one canonical row per `(option_symbol, ts)` or evolve into a more explicitly versioned/event-log contract later
- [ ] if news volume grows materially, decide whether `source_name` should stay row-level or move into compact month metadata when constant within a month file

## Market-regime context
- [x] define the canonical low-frequency macro/economic context contract under `trading-storage/1_market_regime/1_permanent/1_macro/`
- [x] add first FRED / BLS / BEA / Census / Treasury fetchers
- [x] add first official calendar / event builders
- [x] define the initial market-regime benchmark universe and retained granularity plan
- [x] document as-of alignment intent for low-frequency context joined to higher-frequency bars
- [ ] split regime-universe ETF/proxy control into formal reusable core ETFs vs non-reusable watch/secondary ETFs
- [ ] update regime-universe control so only core ETFs such as SPY/QQQ-style large/liquid products are marked K-line reusable for downstream symbol work
- [ ] raise reusable core ETF regime bars to 1-minute target granularity where that is the intended downstream reuse standard

## Boundary cleanup
- [x] make `trading-manager` the documented control-plane owner for scheduling / sequencing / retry policy
- [x] keep `trading-data` docs focused on fetch/build entrypoints plus artifact contracts
- [x] remove stale repo-local research/control-plane leftovers that still implied old layouts or manager ownership
- [x] confirm the manager-facing callable contract for each stable `trading-data` entrypoint
- [x] remove ETF constituent look-through from the active mainline design so ETFs stay regime/context proxies
