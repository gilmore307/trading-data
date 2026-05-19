# Layer 02 - Sector Context Data

This file records the `trading-data` responsibility for Layer 2. It is intentionally narrow: model interpretation belongs to `trading-model`, and global naming authority belongs to `trading-manager`.

## Owned artifact

```text
trading_data.feature_02_sector_context
```

Layer 2 currently consumes a deterministic feature surface built from eligible sector/industry ETF market behavior. There is no accepted separate `source_02_sector_context` artifact.

## Input boundary

`feature_02_sector_context` may include point-in-time sector/industry ETF evidence for:

- relative strength;
- trend;
- volatility;
- correlation;
- breadth;
- dispersion;
- liquidity/spread/optionability support when accepted;
- event/gap/volatility/correlation diagnostics when accepted;
- freshness/missingness diagnostics.

ETF holdings and `stock_etf_exposure` are not core behavior inputs for the SectorContextModel. The Layer 2 feature stage still owns materializing `source_02_target_candidate_holdings` after sector/basket context is available, because that is the deterministic handoff from selected/prioritized sector ETFs into downstream anonymous target candidates.

When reviewed ETFs have mixed provider coverage, daily-derived feature families may use explicit `1Day` bars when present and fall back to the latest regular-session intraday close for dates without explicit daily bars. The fallback must remain point-in-time: current-day partial evidence may only use bars available at or before the snapshot time.

## Field naming

Raw/source columns may use clear provider or observation names without a layer prefix when they are generic facts. Layer-owned feature or model-facing keys use canonical compact prefixes when they represent Layer 2 concepts, for example `2_trend_stability_score` and `2_sector_handoff_state`. Do not introduce `layer02_*` aliases for the same concept.

## Stage flow

```mermaid
flowchart LR
    request["trading-manager task/request<br/>Layer 2 sector context feature need"]
    feeds["provider/feed adapters<br/>sector/industry ETF behavior evidence"]
    feature["trading_data.feature_02_sector_context<br/>relative strength, trend, volatility, correlation, breadth, dispersion"]
    model["trading-model SectorContextModel<br/>consumes Layer 2 features plus Layer 1 context"]
    candidates["trading_data.source_02_target_candidate_holdings<br/>issuer holdings for selected/prioritized sector ETFs"]
    downstream["anonymous target candidate builder / Layer 3<br/>consumes candidate holdings inputs"]
    receipt["completion receipt / manifest / ready signal<br/>validation and handoff evidence"]

    request --> feeds --> feature --> model --> candidates --> downstream
    feature --> receipt
    candidates --> receipt
```

## Layer acceptance

Layer 2 data changes are acceptable when they:

- keep `feature_02_sector_context` as the deterministic Layer 2 feature surface;
- avoid introducing a separate `source_02_sector_context` without an accepted contract;
- keep ETF holdings and `stock_etf_exposure` out of the core SectorContextModel features while materializing `source_02_target_candidate_holdings` in the Layer 2 feature stage for downstream anonymous target construction;
- produce point-in-time validation, row-count, provenance, and completion evidence without committing generated data or secrets;
- route new shared fields, statuses, task-key fields, source names, or feature names through `trading-manager/scripts/` before cross-repository dependence.

Current verification:

```bash
git status --short
find docs -maxdepth 1 -type f | sort
find . -maxdepth 2 -type f | sort
git diff --check
```
