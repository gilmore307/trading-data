# context

This directory holds non-market-tape context metadata for `trading-data`.

Use this directory for things like:
- ETF holdings snapshots / normalized holdings exports
- ETF candidate universes
- symbol-to-context mapping skeletons
- local source-state tracking such as N-PORT availability/capture state
- other context metadata that supports downstream modeling but is not itself minute-level market tape data

## Rule

Do not place this material under `data/`.
`data/` is reserved for actual tracked market dataset files such as bars/quotes/trades/news/options snapshots.
