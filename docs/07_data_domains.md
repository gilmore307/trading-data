# Data Domains

`trading-data` organizes requested data by research purpose before implementation chooses concrete providers or storage paths.

These domains describe why the data is collected and what downstream model lane it may support. They are not final cross-repository type keys until accepted through `trading-main` registry/contracts.

## Domain Summary

| Domain | Chinese Label | Purpose | Later Model Lane |
|---|---|---|---|
| `market_board_data` | 盘面数据 | Study broad market board / market-regime conditions. | Market-board model lane. |
| `instrument_data` | 标的数据 | Study a specific symbol/instrument's own condition. | Instrument model lane. |
| `option_data` | 期权数据 | Study options conditions for a specific underlying. | Options model lane. |

## 1. Market Board Data / 盘面数据

Purpose: collect and normalize data used to study the broad market environment.

Examples may include, once providers are selected:

- index and sector movement;
- broad market breadth;
- volatility/regime indicators;
- macro or calendar context relevant to market state;
- cross-symbol snapshots used to classify market background.

Boundary:

- This repository may collect and clean market-board inputs.
- `trading-model` owns any market-board model training, labeling, inference, or regime discovery.
- `trading-strategy` owns strategy interpretation of the resulting model outputs.

## 2. Instrument Data / 标的数据

Purpose: collect and normalize data used to study a specific tradable symbol or instrument.

Examples may include, once providers are selected:

- historical bars and intraday bars;
- trades, quotes, and liquidity features;
- corporate actions or symbol metadata;
- fundamentals or events when accepted as provider inputs;
- symbol-specific calendar and session context.

Boundary:

- This repository may normalize provider-specific symbol records into accepted data shapes.
- It must not decide whether the symbol is a good trade.
- It must not use strategy returns or profitability to shape upstream data production.

## 3. Option Data / 期权数据

Purpose: collect and normalize data used to study options conditions for an underlying instrument.

Examples may include, once providers are selected:

- option chains;
- contract metadata;
- bid/ask/last/volume/open-interest data;
- implied volatility and Greeks when provided or accepted for calculation;
- expiration, strike, moneyness, and liquidity views.

ThetaData is the currently registered provider term for this domain, but connector and credential layout remain open.

Boundary:

- This repository may clean and structure options data for downstream use.
- `trading-model` owns options-model training or inference.
- `trading-execution` owns live/paper order behavior and broker-specific execution rules.

## Composition Rule

Each domain is a composition of one or more data sources. A single output may combine provider responses, reference metadata, calendars, and validation evidence.

Provider composition must be documented before implementation depends on it:

- source names and roles;
- authentication/secret-alias expectations;
- rate limits and quota risks;
- timestamp/timezone semantics;
- merge and priority rules when sources disagree;
- output schema and validation evidence.

## Output Rule

`trading-data` does not store datasets in Git.

For each domain, `trading-data` should eventually produce cleaned data artifacts plus manifests and ready signals through accepted `trading-main` and `trading-storage` contracts.

Until those contracts are accepted, domain names and output shapes remain documentation-level planning concepts rather than stable cross-repository identifiers.
