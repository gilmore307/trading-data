# option_chain_state_source

Shared ThetaData option-chain source/cache rows.

This package accepts a target underlying and point-in-time or bounded historical window request, calls the accepted `09_feed_thetadata_option_selection_snapshot` feed once, and writes one SQL row per selected option contract per returned minute to:

```text
trading_data.option_chain_state_source
```

Boundary:

- This is source/cache data, so it may retain contract-level fields needed by downstream reducers.
- Layer 3 must only consume this table through target-level chain-state reduction and must not expose contract identity or executable option terms in model-facing state.
- M05 derives option-expression contract candidates from the same rows instead of downloading independent 30-minute option-chain snapshots.

Historical manager requests may use a day-level ET window where practical. The provider fetch uses the ThetaData Python library, plans a point-in-time selected-contract universe from a bounded EOD Greeks discovery envelope, then fetches exact quote and OHLC activity-summary rows only for selected contracts. Downstream Layer 3 and M05 reducers recover the precise modeling windows from SQL `snapshot_time` ranges.

Default source-side discovery bounds are `max_dte=180` and `strike_range=5`. These bounds apply to the lightweight EOD Greeks discovery envelope, not to broad quote/trade measurement. The measured source rows are selected exact contracts under the accepted Layer 3 role contract.

Current rows include quote, IV, first-order Greeks, underlying context, DTE, and minute OHLC activity-summary fields when the feed has them. Open-interest fields are present as nullable slots for the reviewed future ThetaData OI enrichment route. Raw trade ticks are reserved for event/detail audit paths, not the normal shared source path.
