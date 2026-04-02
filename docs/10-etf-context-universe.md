# 10 ETF Context Universe

This document records the first expanded ETF context universe for `trading-data`.

The purpose is to establish a stable upstream candidate ETF set that the data layer should be prepared to support.

## Category structure

The current ETF context universe is organized into:
- core broad market
- core sector
- macro / commodity / crypto proxy
- industry / sub-industry
- thematic / high-attention
- resource / transition

## Broad market core

Current broad market core symbols:
- `SPY`
- `VOO`
- `IVV`
- `VTI`
- `QQQ`
- `IWM`
- `DIA`

## Core sector ETFs

Current core sector set:
- `XLK`
- `XLF`
- `XLE`
- `XLV`
- `XLI`
- `XLY`
- `XLP`
- `XLB`
- `XLU`
- `XLRE`
- `XLC`

## Macro / commodity / crypto proxies

Current macro/commodity/crypto proxy set:
- `GLD`
- `IAU`
- `SLV`
- `USO`
- `DBC`
- `PDBC`
- `IBIT`
- `ETHA`
- `FSOL`
- `BITW`

## Important industry / sub-industry ETFs

Current industry/sub-industry set includes:
- `SMH`, `SOXX`
- `IGV`, `CLOU`, `BUG`
- `XBI`, `IBB`, `IHI`, `IHF`, `XHE`, `XHS`, `IHE`
- `KRE`, `IAT`, `KBE`, `KIE`, `IAI`
- `ITA`, `IYT`
- `XHB`, `XRT`, `XME`, `XOP`, `XES`, `IEO`, `IEZ`

## Thematic / high-attention ETFs

Current thematic/high-attention set includes:
- `AIQ`, `BOTZ`, `DTCR`, `DRIV`
- `FINX`, `ARKF`, `BKCH`
- `ARKG`, `ARKW`, `HERO`, `SOCL`, `EBIZ`, `ARKX`

## Resource / transition ETFs

Current resource/transition set includes:
- `LIT`
- `NLR`
- `REMX`
- `GDX`

## Machine-readable config

The current ETF context universe is stored at:
- `config/etf_context_universe.json`

The config now includes fields such as:
- `category`
- `priority`
- `sector` or `theme`
- `notes` where useful

## Current role

This ETF universe is the candidate context pool.
`trading-data` should be prepared to support holdings discovery and later market-data support for these context objects.
`trading-model` can later evaluate which of them are actually most informative for a given underlying.
