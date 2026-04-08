# 07 Market Regime Benchmarks

This document defines the permanent market-state benchmark set used to assess broad U.S. market conditions.

These instruments/series are not normal sector/theme ETF context candidates.
They should be treated as permanent benchmark context.

## Storage / granularity rule

Each retained market proxy should have one chosen primary stored bar granularity rather than multiple redundant default granularities.
Official macro series remain at their original source frequency.

## 1-minute retained benchmark proxies
- `SPY`
- `QQQ`
- `IWM`
- `RSP`
- `DIA`

Use these for:
- broad beta
- growth vs broad market
- small-cap vs large-cap
- breadth / concentration
- old economy / blue-chip benchmark confirmation

## 30-minute retained benchmark proxies
- `SHY`
- `IEF`
- `TLT`
- `HYG`
- `UUP`
- `GLD`
- `SLV`
- `IBIT`
- `ETHA`
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
- relatively independent industry/thematic ETFs:
  - `SMH`
  - `SOXX`
  - `KRE`
  - `ITA`
  - `IYT`
  - `LIT`
  - `GDX`
  - `BOTZ`

Use these for:
- duration and rates sensitivity
- credit risk appetite
- dollar pressure
- metals / safe-haven response
- crypto proxy context
- sector rotation
- relatively independent industry/thematic regime context

## Daily retained benchmark proxies
- `LQD`
- `VIXCLS`
- `VXN`
- `MOVE`
- `DBC`
- `PDBC`
- `USO`

Use these for:
- higher-grade credit context
- volatility / fear context when only daily reliable sources are available
- broad commodity and energy shock context

## Original-frequency macro series
Keep the following at source/native frequency rather than converting into retained benchmark bars:
- rates / curve: `DFF`, `DGS3MO`, `DGS2`, `DGS10`, `DGS30`, `T10Y2Y`, `T10Y3M`
- inflation: `CPIAUCSL`, `CPILFESL`
- labor / growth: `UNRATE`, `PAYEMS`, `ICSA`, `GDPC1`
- official source families: BLS, BEA, Census, Treasury Fiscal Data

## Practical interpretation
- do not store multiple default bar granularities for the same benchmark proxy
- if a different higher/lower frequency is needed later, treat it as a separate scoped acquisition task rather than the default retained benchmark layer
