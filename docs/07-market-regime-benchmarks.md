# 07 Market Regime Benchmarks

This document defines the permanent market-state benchmark set used to assess broad U.S. market conditions.

These instruments/series are not normal sector/theme ETF context candidates.
They should be treated as permanent benchmark context.

## Storage / granularity rule

Each retained market proxy should have one chosen primary stored bar granularity rather than multiple redundant default granularities.
Official macro series remain at their original source frequency.

## 30-minute retained benchmark proxies
- `SPY`
- `QQQ`
- `IWM`
- `RSP`

Use these for:
- broad beta
- growth vs broad market
- small-cap vs large-cap
- breadth / concentration

## 1-hour retained benchmark proxies
- `TLT`
- `HYG`
- `UUP`
- sector rotation ETFs:
  - `XLB`
  - `XLC`
  - `XLE`
  - `XLF`
  - `XLK`
  - `XLI`
  - `XLP`
  - `XLRE`
  - `XLU`
  - `XLV`
  - `XLY`

Use these for:
- rates impulse / duration sensitivity
- credit risk appetite
- dollar pressure
- sector rotation

## Daily retained benchmark proxies
- `DIA`
- `SHY`
- `IEF`
- `GLD`
- `SLV`
- `LQD`
- `DBC`
- `USO`

Use these for:
- old economy / blue-chip benchmark
- shorter-duration and intermediate-duration bond context that does not need sub-daily storage by default
- metals and commodity shock context
- higher-grade credit context

## Original-frequency macro series
Keep the following at source/native frequency rather than converting into retained benchmark bars:
- rates / curve: `DFF`, `DGS3MO`, `DGS2`, `DGS10`, `DGS30`, `T10Y2Y`, `T10Y3M`
- inflation: `CPIAUCSL`, `CPILFESL`
- labor / growth: `UNRATE`, `PAYEMS`, `ICSA`, `GDPC1`
- volatility / fear: `VIXCLS`, `VXNCLS`, `MOVE`
- official source families: BLS, BEA, Census, Treasury Fiscal Data

## Practical interpretation
- do not store multiple default bar granularities for the same benchmark proxy
- if a higher-frequency study is needed later, treat it as a separate scoped acquisition task rather than the default retained benchmark layer
