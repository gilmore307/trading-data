# option_chain_state_source

Shared ThetaData option-chain source/cache rows.

This package accepts a target underlying and point-in-time or bounded historical window request, calls the accepted `09_feed_thetadata_option_selection_snapshot` feed once, and writes one SQL row per visible option contract per returned minute to:

```text
trading_data.option_chain_state_source
```

Boundary:

- This is source/cache data, so it may retain contract-level fields needed by downstream reducers.
- Layer 3 must only consume this table through target-level chain-state reduction and must not expose contract identity or executable option terms in model-facing state.
- Layer 9 derives option-expression contract candidates from the same rows instead of downloading independent 30-minute option-chain snapshots.

Historical manager requests should use a day-level ET window where practical. The provider fetch is serialized through one ThetaData Python-library session; downstream Layer 3 and Layer 9 reducers recover the precise modeling windows from SQL `snapshot_time` ranges.

Current rows include quote, IV, first-order Greeks, underlying context, DTE, and minute trade-summary fields when the feed has them. Open-interest fields are present as nullable slots for the reviewed future ThetaData OI enrichment route.
