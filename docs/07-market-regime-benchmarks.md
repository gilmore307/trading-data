# 07 Market Regime Benchmarks

This document defines the permanent market-state benchmark set used to assess broad U.S. market conditions.

These instruments/series are not normal sector/theme ETF context candidates.
They should be treated as permanent benchmark context.

## Core idea

Keep a permanent benchmark layer for:
- broad equity benchmarks
- rates / curve shape
- safe-haven and FX context
- volatility and credit context

## Equity benchmarks
- S&P 500 -> `SPY`
- Nasdaq 100 -> `QQQ`
- Dow Jones Industrial Average -> `DIA`
- Russell 2000 -> `IWM`
- S&P 500 Equal Weight -> `RSP`

## Rates / curve
FRED series:
- `DFF`
- `DGS3MO`
- `DGS2`
- `DGS10`
- `DGS30`
- `T10Y2Y`
- `T10Y3M`

Tradeable bond proxies:
- `SHY`
- `IEF`
- `TLT`

## Safe havens / FX
- Gold -> `GLD`
- Dollar proxy -> `UUP`

## Volatility / credit
- `VIXCLS`
- `HYG`
- `LQD`

## Storage rule

- low-frequency series should remain under `trading-storage/2_context/0_permanent/1_macro/`
- tradeable proxy benchmark tape should remain under `trading-storage/1_ingest/1_long_retention/1_bars/` and related tape families when downloaded
- this benchmark set is permanent context and should not be mixed into the normal ETF candidate universe
