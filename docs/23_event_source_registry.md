# Event Source Registry

Status: accepted source-acquisition boundary for the global event observation pool. This document defines how `trading-data` should acquire historical and realtime/future event observations before Layer 10 attribution and any future Layer 4 supervision.

## Core Rule

Event acquisition has two separate jobs:

1. historical replay: reconstruct what was knowable at each historical `available_time`;
2. realtime maintenance: keep the forward-looking global event observation pool current without making causal claims.

Rows produced from this registry are observation evidence only. They do not imply production Layer 4 eligibility, strategy failure attribution, alpha, trade direction, position size, or execution permission. Layer 10 may separately place an event family in the focused/watched event pool, which lets `trading-data` systematically acquire and standardize candidate observations for offline Layer 4 training and Layer 5 validation.

Raw source rows are not model-ready semantics. The required route is source acquisition -> point-in-time evidence row/artifact ref -> `event_interpretation` artifact -> standardized event observation row. `trading-data` owns acquisition, clocks, source priority, dedup/canonical metadata, source-specific parsed fields, and artifact refs. `trading-model` owns semantic interpretation, event-context vector scoring, failure attribution, and Layer 4/Layer 5 validation.

## Required Clocks

Every event observation should preserve the clocks that are available for its source class:

```text
source_published_time
source_updated_time
retrieved_time
available_time
event_time
scheduled_time
effective_time
regime_start_time
regime_end_time
last_material_update_time
```

`available_time` is the model visibility clock. When exact publication timing is unavailable for historical rows, use the most conservative supported time and record `available_time_rule`.

## Historical Replay

Historical acquisition should prefer immutable or archived artifacts with point-in-time clocks:

- Trading Economics storage-snapshot artifacts for macro calendars and macro release values;
- official agency/archive pages, machine-readable historical APIs, release archives, filing timestamps, announcement PDFs, and stored local snapshots for non-macro or exception routes;
- provider calendars only when official history is unavailable or as corroborating evidence;
- rule-generated calendars only for deterministic structures, and still tagged as `inferred_rule` until official confirmation is available.

Historical replay must store enough evidence refs to prove what was knowable before each model decision. It must not use later revisions, final outcomes, constituent results, or later news as if they were known at the original decision time.

## Realtime / Future Maintenance

Realtime maintenance should run bounded refreshes:

- yearly or monthly for exchange holiday and index methodology calendars;
- bounded Trading Economics recent/future calendar refresh into canonical storage source rows only, with no website URL persistence and no Layer 10 SQL event admission;
- daily or intraday for SEC/company filings, company IR/news, sanctions/trade actions, and persistent-regime status updates when active;
- event-window refreshes around known expiry, rebalance, macro, or earnings windows.

Realtime rows need certainty flags:

```text
confirmed
scheduled
tentative
estimated
inferred_rule
```

Future events may enter the global event observation pool when `available_time <= decision_time`. They remain observation-only until Layer 10 identifies a plausible failure relationship and places the family in the focused/watched event pool for candidate training and validation. Production Layer 4 use still requires later acceptance.

## Source Families

| Event family | Primary historical source | Primary realtime/future source | Fallback / corroboration | Key PIT rule |
|---|---|---|---|---|
| Exchange holidays, early closes, long weekends | NYSE/Nasdaq official calendars and saved snapshots | NYSE/Nasdaq official current/future calendars | rule-generated US exchange holidays tagged `inferred_rule` until official confirmation | source page retrieval time or official published/update time; early-close details must be source-backed |
| Option expiry / triple-witching | Cboe/OCC historical calendars or archived calendars plus deterministic monthly/quarterly rules | Cboe/OCC annual calendars plus deterministic rule projection | exchange calendars and local generated rule rows | rule-generated future windows are `inferred_rule`; official calendar rows upgrade to `confirmed` |
| Macro scheduled releases | Trading Economics storage-snapshot artifacts | Trading Economics storage-snapshot artifacts when reviewed/imported | official agency source only for manual incident review or severe TE anomaly | TE storage is the accepted macro evidence because it preserves scheduled time plus expectation/previous/actual-style fields captured before subscription expiry; no TE website URL is a source reference |
| Treasury auctions | TreasuryDirect auction schedules, announcements, results archive | TreasuryDirect upcoming auctions and announcements | Treasury fiscal-data APIs if separately accepted | announcement/schedule time separate from auction/result time |
| Earnings and issuer events | SEC EDGAR filings, company IR archives, accepted historical earnings calendars | company IR, SEC EDGAR submissions, Nasdaq/other calendars as tentative discovery | vendor calendars for tentative dates only | company/SEC official artifacts outrank calendars; result/guidance facts require visible official artifact |
| Target-local company news | Alpaca News when the target is covered, plus SEC/company IR for official issuer facts | Alpaca News for target-scoped headline discovery; SEC/company IR for official issuer facts | GDELT only as corroborating broad-context evidence, not the primary ticker/company-news route | ticker-scoped news is target-local evidence; broad macro/geopolitical context should be represented by separate event/regime rows instead of substituting for company-news coverage |
| Macro / political / war / geopolitical news regimes | GDELT raw point-in-time files plus official action archives where available | GDELT monitoring/API enrichment plus official government, sanctions, defense, diplomatic, and high-quality news sources where available | Reuters/AP/Bloomberg/WSJ/FT style sources and official refs as evidence; BigQuery diagnostics only | GDELT is a broad event-regime/news-topic source, not a single-stock headline source; promotion requires reviewed topic-frequency/regime evidence and decay rules |
| Index reconstitution / rebalance | index provider announcements, methodology calendars, archived PDF/list files | Nasdaq Global Indexes for Nasdaq-100; S&P DJI for S&P 500 and Dow Jones Industrial Average | provider/member files where licensed and approved; ETF issuer pages only as impact-chain corroboration, never source of truth | Nasdaq-100 methodology supports scheduled annual reconstitution and quarterly rebalance shells; S&P 500 supports quarterly maintenance/rebalance windows but constituent changes require S&P DJI announcement visibility; DJIA has no fixed constituent reconstitution calendar and relies on S&P DJI announcements |
| Persistent event regimes | high-frequency reviewed news-topic timelines plus official action archives where available | high-frequency reviewed news-topic monitoring plus official action feeds/pages where available | Reuters/AP/Bloomberg/WSJ/FT style sources and official refs as evidence | same-day news is not required after regime is active; topic-frequency promotion must be agent-reviewed and decay-rule backed |

## Attribution Source Routing

Layer 10 post-failure attribution uses source routing by impact layer rather than by ticker alone.

```text
market/global route
-> sector / industry / theme / peer / external-leader route
-> target-local route
```

The route selected first is the one supported by failure-scope triage, but lower layers remain in scope as residual, contributor, and confounder checks. A market-wide move still requires sector/theme and target-local checks. A sector/theme move still requires target-local checks. A target-local move still requires bounded market/sector confounder checks when timing overlaps or residual evidence is weak.

Source responsibilities:

- market/global route: GDELT raw PIT files and monitoring APIs for macro/geopolitical/news-regime evidence; official macro, policy, sanctions, defense, diplomatic, central-bank, regulator, and agency sources where available; Trading Economics storage rows for accepted macro calendar/value evidence;
- sector/theme/peer route: GDELT topic evidence, sector ETF/peer-basket context, official sector/regulatory sources, and source-entity evidence for external leader or peer events;
- external leader/peer route: Alpaca News, SEC EDGAR, company IR, and official issuer materials for the leader or peer entity, plus a scope-support ref showing the target transmission channel;
- target-local route: Alpaca News, SEC EDGAR, company IR, exchange/regulatory notices, official issuer artifacts, and accepted analyst/news refs for the target entity.

Index rebalance routing is limited to the accepted U.S. headline index set:

- Nasdaq-100: generate scheduled observation shells from Nasdaq Global Indexes methodology calendars; actual adds/deletes require Nasdaq official announcement evidence.
- S&P 500: generate quarterly maintenance/rebalance-window shells from S&P DJI methodology/index-page facts; actual additions/deletions require S&P DJI announcement evidence.
- Dow Jones Industrial Average: do not generate fixed constituent-reconstitution shells because the headline index changes as needed; monitor S&P DJI announcements and preserve announced effective dates when visible.
- ETF issuers such as QQQ, SPY, and DIA can support impact-chain analysis, but they are not canonical index membership or rebalance sources.

Examples:

- `META` post-earnings failure: target-local earnings/guidance/tax-charge source evidence is primary; GDELT and market sources check AI-capex theme and market confounders.
- `NVDA` semiconductor selloff: sector/theme evidence and market risk-off evidence may be primary when SMH/peers move with or more than NVDA; NVDA-specific export, legal, or valuation headlines remain target-local contributors.
- `ORCL` move after an `NVDA` event: the native event source is NVDA, but the target attribution route must preserve AI/cloud/data-center, semiconductor, supplier/customer, index, or risk-appetite transmission evidence before the event can explain ORCL.

## Standardized Event Observation Requirements

Every event family must preserve the source fields needed for downstream `event_interpretation` and standardized quantification. The shared minimum is:

```text
event_id
canonical_event_id
source_artifact_ref
source_name
source_type
source_priority
dedup_status
coverage_reason
covered_by_event_id
published_time
available_time
lifecycle_type
event_family
certainty_status
affected_scope_hint
affected_entities_hint
review_ref
```

Trading-calendar and market-structure observations should also preserve:

```text
next_market_open_time
non_trading_interval_minutes
closure_type
closure_length_bucket
holiday_name
early_close_flag
pre_holiday_session_flag
expiry_window_flag
triple_witching_flag
index_rebalance_flag
index_event_family
```

Persistent-regime observations should also preserve:

```text
regime_family
candidate_regime_ref
regime_status
regime_start_time
regime_end_time
last_material_update_time
affected_scope
affected_entities
decay_rule_ref
staleness_review_time
regime_review_ref
```

These fields are standardization evidence. Layer 10 and review decide whether they become focused-pool candidates or accepted Layer 4 production conditioning.

## Macro TE Route

Trading Economics storage is the accepted macro source route because it preserves a unified calendar shape with market-facing fields such as expected/consensus, previous, and actual-style values captured before subscription expiry. `trading-data` should not run a parallel routine official-source macro calendar path by default and must not use the expired TE website as an active source.

Official macro agency sources are reserved for:

- incident review when TE rows are missing, malformed, delayed, or contradictory;
- one-off audit of critical macro event handling;
- future replacement only after a separate reviewed route decision.

This means macro rows can be promoted into the global event observation pool from TE storage alone, provided their `available_time`, retrieval evidence, row fields, and retained storage artifact path are preserved. TE source artifacts are keep-forever append-only evidence under the canonical monthly storage root; SQL stores the normalized event envelope and points back to those artifacts. TE rows still do not become production Layer 4 conditioning samples unless Layer 10/review later accepts the event family/mechanism. They may support focused-pool candidate training after Layer 10 identifies a plausible failure relationship.

## Persistent-Regime Source Rules

GDELT BigQuery is not a routine acquisition path for persistent-regime history or replay. Use it only as a bounded parity/audit tool when validating local raw-file coverage, provider schema changes, or suspicious missing data. Production-oriented regime acquisition should be designed around point-in-time raw-file manifests, local parsed evidence, dedup/canonical URL clustering, focused event-pool filters, and bounded enrichment APIs.

Persistent regimes are a news-topic promotion route. They require interval evidence, not daily headlines. The repeatable flow is:

```text
high_frequency_news_topic
-> candidate_regime
-> `regime-promotion-review`
-> persistent_event_regime
-> Layer 10 attribution
-> focused/watched event pool for systematic acquisition and candidate training
-> Layer 4 candidate training
-> Layer 5 validation
-> Layer 10 disposition
-> accepted_layer4_event_family only if later accepted for production supervision
```

A candidate regime should include:

```text
topic_key
topic_entities
topic_keywords
source_count
high_quality_source_count
first_seen_time
last_seen_time
topic_frequency_score
topic_persistence_score
topic_acceleration_score
affected_scope_hint
representative_evidence_refs
```

Agent review uses the `regime-promotion-review` skill to decide whether the topic is a real regime, a short-lived news cluster, duplicate coverage of another regime, or noise. The accepted review packet should define `regime_family`, inclusion/exclusion rules, start status, affected scopes, material update rules, decay/staleness rules, and evidence-quality thresholds. Approval can authorize focused-pool candidate acquisition and Layer 4 candidate training/evaluation; it does not authorize production Layer 4 conditioning.

Accepted source classes include:

- tariffs and trade conflict: USTR notices, Federal Register notices, official trade actions, and high-quality news for negotiation/escalation context;
- sanctions: OFAC recent actions and sanctions program pages, plus official government notices;
- public-health regimes: CDC and WHO outbreak/emergency pages, official health-agency updates, and reviewed news timelines;
- geopolitical war/escalation regimes: official government statements, sanctions/defense/diplomatic releases, and reviewed high-quality news timelines;
- banking-system stress: official regulator/central-bank actions, deposit/guarantee/liquidity facility notices, and reviewed high-quality news timelines.

Each interval row should carry:

```text
regime_family
regime_status
regime_start_time
regime_end_time
last_material_update_time
affected_scope
affected_entities
decay_rule_ref
staleness_review_time
evidence_refs
```

`regime_status` may be `active`, `shadow_active`, `decaying`, `stale`, or `resolved`. `trading-data` preserves the facts; `trading-model` and review decide whether the regime explains failures.

## Forbidden Shortcuts

- Do not backfill future-known results as historical pre-event facts.
- Do not treat vendor/news calendars as higher priority than official issuer/agency/exchange sources.
- Do not turn a global event-pool row into production Layer 4 conditioning without Layer 10/review acceptance.
- Do not skip the focused-pool candidate stage when Layer 10 has only identified a plausible failure relationship.
- Do not keep a persistent regime active forever without decay/staleness evidence.
- Do not bypass WAF, captcha, login, or provider terms to obtain source data.
