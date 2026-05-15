# Decisions

This file records the active `trading-data` decisions. Superseded route history remains available in Git history; current readers should be able to follow the direct feed/source/feature route from this file alone.

## D001 — Repository boundary

`trading-data` owns historical data acquisition, source normalization, deterministic feature construction, and point-in-time data visibility.

It does not own model labels/training/evaluation/promotion, strategy/backtest logic, broker execution, dashboard interpretation, global storage policy, or secrets.

## D002 — Direct data route

The active route is:

```text
data_feed -> data_source -> data_feature -> SQL/artifact handoff
```

- `data_feed` owns provider/API/web/file access and feed-level normalization.
- `data_source` owns manager-facing source orchestration and reviewed model-input source outputs.
- `data_feature` owns deterministic point-in-time feature blocks from accepted source outputs.
- durable handoff uses reviewed SQL/artifact contracts, manifests, artifact references, and ready signals.

## D003 — Shared names route through trading-manager

Fields, statuses, data kinds, feed/source names, config keys, artifact/request/manifest/ready-signal types, templates, and shared helpers must be reviewed through `trading-manager` before becoming cross-repository contracts.

## D004 — Durable storage belongs to trading-storage

`trading-storage` owns durable layout, retention, archive, backup, restore, manifests, artifact references, and ready signals. Local ignored `storage/` files in this repo are development evidence, not production interfaces.

## D005 — Secrets stay outside Git

Provider credentials live under `/root/secrets/<alias>.json` and are referenced by alias only. Docs, manifests, receipts, logs, and tests must not print or commit secret values.

## D006 — Tests are fixture-safe by default

Default tests must not require network access or live credentials. Live calls require explicit guardrails: provider allowlist, endpoint family, bounded symbols/contracts, bounded time window, request/row caps, timeout, retry/rate-limit policy, and sanitized evidence.

## D007 — High-volume raw rows are transient by default

Raw provider trades, quotes, bulky SEC facts, and other high-volume payloads should be streamed/segmented and discarded after producing reviewed aggregates or final cleaned outputs. Persist raw payloads only for an explicitly approved debug or incident artifact.

## D008 — Accepted outputs prefer SQL or reviewed compact artifacts

Numbered model-input sources should write accepted SQL tables unless a reviewed compact artifact is the better boundary. Business tables should not carry `task_id`, `run_id`, or write-audit timestamps when those belong in receipts/manifests.

## D009 — Historical product labels are not runtime boundaries

Market board / 盘面数据, instrument / 标的数据, and option / 期权数据 remain useful product concepts. Runtime keys, package names, registry rows, and storage paths should follow feed/source/feature contracts instead.

## D010 — Macro model-input route

The executable `macro_data` feed is not active. Macro model-input rows use `07_feed_trading_economics_calendar_web` visible-page evidence unless a separately reviewed route replaces it. Official macro API aliases may remain for reviewed research but are not active manager routes by default.

## D011 — Provider surfaces

Current provider/source surfaces:

- Alpaca for stock/ETF bars, trades, quotes, snapshots, and news.
- ThetaData for option contracts, snapshots, OHLC, trade/quote, open interest, IV, and Greeks through local Terminal v3.
- OKX for accepted crypto market data.
- SEC EDGAR for official company submissions/facts/concepts/frames.
- ETF issuer pages/files for holdings.
- Trading Economics visible pages for current macro calendar/value rows.
- Official FOMC and macro release pages for calendar events.
- FRED/Census/BEA/BLS/Treasury only through reviewed optional economic-data routes.

## D012 — ThetaData runtime

ThetaData runtime lives outside Git under `/root/tools/thetadata-terminal/` and serves Terminal v3 on `127.0.0.1:25503` when started. Connector integration is accepted; a closed local port is a runtime-not-started condition, not a missing connector.

## D013 — ThetaData option feeds are use-case split

- `09_feed_thetadata_option_selection_snapshot` captures point-in-time option-chain visibility.
- `10_feed_thetadata_option_primary_tracking` tracks one caller-supplied contract and writes `option_bar.csv`.
- `11_feed_thetadata_option_event_timeline` emits event rows/details for one caller-supplied contract and supplied event standard.

`trading-data` does not choose contracts inside these feeds.

## D014 — Layer 1 and Layer 2 data boundaries

Layer 1 market-regime data is broad-market/ETF bar evidence and must not use sector leadership, selected securities, strategy labels, option outcomes, portfolio PnL, or future-return labels.

Layer 2 sector-context features derive deterministic sector/industry behavior evidence from accepted Layer 1 source outputs and reviewed relative-strength combinations. ETF holdings are not Layer 2 core behavior input.

## D015 — Target candidate and Layer 3 boundaries

`source_02_target_candidate_holdings` supports anonymous target candidate preparation after Layer 2 sector/basket prioritization. It preserves point-in-time visibility: explicit `available_time` wins; otherwise holdings become visible at the next regular US session open after `as_of_date`.

`source_03_target_state` provides target-local observed bars/liquidity. `feature_03_target_state_vector` builds deterministic feature blocks for `TargetStateVectorModel`. Labels, evaluation, and promotion belong to `trading-model`.

## D016 — Event overlay boundary

`source_04_event_overlay` is a point-in-time event index with canonical-event and dedup fields. It stores overview rows and references to details; full articles, filings, detector payloads, browser/agent analysis, labels, impact scores, and alpha confidence stay outside the business table.

`equity_abnormal_activity_event` uses conservative fixture/default standards until reviewed historical calibration exists.

## D017 — Option-expression data boundary

`source_05_option_expression` writes option-chain snapshot rows for `OptionExpressionModel`.

`source_06_position_execution` tracks selected-contract option market data for replay/evaluation. It is not a separate execution model and must not emit order instructions, position sizing, PnL labels, or broker/account mutations.

## D018 — Downstream model layers without new acquisition

`AlphaConfidenceModel` and `PositionProjectionModel` do not need symmetry-only `trading-data` sources when no new external/source acquisition is required. They consume upstream SQL outputs, model outputs, labels, current/pending position state, risk/cost context, and reviewed evaluation artifacts in their owning boundaries.

## D019 — Production hardening does not equal production approval

Live-call policy, retry/rate-limit rules, checkpoint/resume evidence, manifests, artifact refs, ready signals, and ThetaData runbook rules can be defined before accumulated production labels exist. They do not approve unattended production orchestration, production labels, or model promotion.

## D020 — Package CLIs are the executable surface

Reusable logic belongs in `src/`. `trading-data` does not keep a top-level `scripts/` wrapper directory; stable callable entrypoints should be exposed through package CLIs declared in `pyproject.toml` and registered through `trading-manager` when shared.

## D021 — Price-action events belong inside Layer 4 event overlay

Date: 2026-05-09

`price_action` is an accepted `source_04_event_overlay` event category for detector-visible board/tape behavior such as `false_breakout`, `false_breakdown`, `liquidity_sweep_high`, `liquidity_sweep_low`, `bull_trap`, and `bear_trap`.

These rows are source-detector event evidence. They do not create a ninth model layer, action signal, label, order instruction, or execution permission. Detector details remain behind references or compact nested detector artifacts; the overview table keeps only the event envelope, clocks, category, scope, and reference.

## D022 — Browser-scraped data uses session-cookie acquisition

Date: 2026-05-15
Status: Accepted

For browser-scraped sources such as Trading Economics, the browser should maintain authenticated session state and refresh cookies, but normal historical feed acquisition should not repeatedly open/login browser pages or rely on a mutable long-lived tab. Feed tasks consume an exported local cookie jar plus task-specific date/filter parameters through bounded HTTP page fetches. If the provider requires captcha, MFA, WAF intervention, or permission handling, acquisition pauses for operator action rather than bypassing the control.

All browser-scraped feed parsers must filter outputs to the requested time/window and report skipped out-of-window rows in receipt warnings/details.

## D023 — Event evidence moves to Layer 8 event-risk governor use

Accepted: 2026-05-15

The active conceptual stack moves event intelligence from pre-alpha Layer 4 to post-guidance Layer 8. `trading-data` still owns point-in-time event evidence indexes and deterministic event-overview features, but those artifacts now feed event interpretation and the Layer 8 EventRiskGovernor / EventIntelligenceOverlay rather than acting as a hard prerequisite for Layer 4 AlphaConfidenceModel.

Layer 7 trading guidance / option-expression data uses the existing option-expression inputs (`source_05_option_expression`, `feature_08_option_expression`, and `source_06_position_execution`) until a dedicated implementation migration renames physical source/feature surfaces. Layer 8 event-risk data uses the existing event surfaces (`source_04_event_overlay`, `feature_04_event_overlay`, and event-feed artifacts) until a dedicated implementation migration renames physical surfaces.

Event evidence must preserve point-in-time availability, row coverage, canonical/dedup metadata, and evidence refs so an `event_interpretation_v1` artifact and event-risk intervention can be audited. `trading-data` must not emit broker orders, account mutations, or final trading decisions.

## D024 — Event evidence preserves lifecycle clocks

Accepted: 2026-05-15

Event evidence must preserve enough timing information for downstream event interpretation to distinguish scheduled-known catalysts from unscheduled surprise events. `source_04_event_overlay` remains a light overview/index surface, but referenced source artifacts must retain awareness/scheduled/published/available/interpretation/resolution clocks when the source provides or implies them.

Accepted lifecycle classes for downstream interpretation are `scheduled_known_outcome_later`, `unscheduled_surprise`, `scheduled_recurring_data_release`, `multi_stage_developing_event`, and `unknown`.

`trading-data` does not score final event risk or make trading decisions, but it must not destroy lifecycle evidence. Earnings and macro-calendar shells can be visible before results; result values become valid only after release artifacts are available. Surprise news must not be represented as if the specific headline was known before its first credible source.
