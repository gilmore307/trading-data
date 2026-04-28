# Unified event database templates

This directory owns source-neutral event database preview templates. These are not raw provider outputs. They are the common event/factor/report surfaces used to study financial reports, SEC corporate events, news, option activity, macro releases, and market anomalies together.

## Design boundary

Raw acquisition remains source-specific:

- `alpaca_news` owns raw/news-provider article acquisition.
- `sec_company_financials` owns official SEC submissions/companyfacts/companyconcept/frame acquisition.
- `thetadata_option_event_timeline` owns option-market abnormal activity detection.
- Equity abnormal activity builders own stock/ETF price, volume, relative-strength, gap, and liquidity anomaly detection from observable market data.
- Future SEC filing-event builders, market anomaly builders, and macro release builders should project their source outputs into this event layer.

The event database layer owns common research rows:

- `trading_event` — factual event row and artifact links.
- `event_analysis_report` — index row for long-form agent/model analysis artifacts.
- `event_factor` — model-facing numeric features derived from events.
- `equity_abnormal_activity_event` — derived event-style row for abnormal stock/ETF market activity used by EventOverlayModel.

Long text belongs in report artifacts, not inside event CSV rows. Event rows store short titles/summaries and `analysis_report_url` / sidecar references.

## Source priority and news coverage filtering

Do not delete raw news just because the same event is covered by SEC or another official source. Preserve raw source data in the source bundle, but prevent duplicate event alpha in the unified event layer.

## Impact scope

Every event should identify the layer it primarily affects:

- `market` — broad market event, e.g. Fed decision affecting `US_MARKET`.
- `sector` — sector-level event, e.g. banking regulation affecting `financials`.
- `industry` — narrower industry event, e.g. export controls affecting `semiconductors`.
- `theme` — cross-sector theme, e.g. AI infrastructure or GLP-1 beneficiaries.
- `security` — single-name event, e.g. one company's 10-K filing.
- `multi_security` — specific basket/peer group event.
- `macro` — macroeconomic release or policy event whose target universe is defined separately.
- `unknown` — unresolved during extraction; should be reviewed before model training.

Use `impact_scope`, `impacted_universe`, and `primary_impact_target` together. For example, a CPI release might use `impact_scope=market`, `impacted_universe=US_MARKET;rates;USD`, and `primary_impact_target=US_MARKET`; an Apple 10-K would usually use `impact_scope=security`, `impacted_universe=AAPL`, and `primary_impact_target=AAPL`.

Canonical event priority should generally be:

1. Official regulatory/exchange/company filings and releases, e.g. SEC filings.
2. Direct company press releases or investor relations material.
3. High-quality news articles that add genuinely new information.
4. Syndicated/reposted/derivative news coverage.

When a news article covers an already-known SEC event, the news-derived `trading_event` should either not be emitted as an independent event, or should be emitted with:

- `canonical_event_id` pointing to the SEC canonical event.
- `dedup_status = covered_by_official_source`.
- `coverage_reason` explaining the match, e.g. same CIK/accession/form, same company/event type/time window, or high text similarity to an official disclosure.

Covered news may still be useful for propagation, attention, or human-readable explanation, but it must not create a second independent `event_factor` row unless the article adds new non-SEC information that is safely observable at its own `effective_time`.

## `trading_event`

Canonical source-neutral event row. It stores what happened, when it became observable, where the evidence lives, and where any analysis artifact lives.

Important timing rules:

- `event_time` is the source publication/detection timestamp.
- `effective_time` is the earliest trading timestamp when the event can safely be used by a strategy.
- For after-hours SEC filings or articles, `effective_time` should usually be the next regular session open unless a strategy explicitly trades extended hours.

Typical `event_type` values include:

- `equity_financial_report_event`
- `equity_news_event`
- `option_activity_event`
- `equity_ma_event`
- `equity_offering_event`
- `equity_insider_transaction_event`
- `equity_ownership_change_event`
- `equity_buyback_event`
- `equity_management_change_event`
- `equity_legal_regulatory_event`
- `trading_economics_calendar_event`
- `market_anomaly_event`

SEC event classification should use `taxonomy_context` for source-specific details such as `sec_form`, `sec_items`, accession number context, and filing document references.

Macro model inputs now come from Trading Economics visible calendar rows. The former official-API `macro_data` bundle and `macro_release` evidence path are deprecated; use `trading_economics_calendar_event` for Actual, Previous, Consensus, and Forecast fields when visible.

## `event_analysis_report`

Index row for agent/model-generated analysis artifacts.

Recommended artifact pair:

```text
saved/reports/<event_id>.md
saved/reports/<event_id>.analysis.json
```

The Markdown report is for human review. The JSON sidecar is for structured summaries, extracted metrics, risks, and downstream scoring.

## `event_factor`

Numeric model-facing features for one event. First-version features are intentionally compact:

- `direction_score`
- `magnitude_score`
- `surprise_score`
- `novelty_score`
- `relevance_score`
- `credibility_score`
- `price_in_score`
- `reaction_score`

Do not mix future labels into this table. Future return, volatility, drawdown, and volume labels belong in a separate label/validation surface. `reaction_score` may only be populated when the intended decision time can actually observe the market reaction.
