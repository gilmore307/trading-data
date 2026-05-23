# Event Source Registry

Status: accepted source-acquisition boundary for the global event observation pool. This document defines how `trading-data` should acquire historical and realtime/future event observations before Layer 10 attribution and any future Layer 4 supervision.

## Core Rule

Event acquisition has two separate jobs:

1. historical replay: reconstruct what was knowable at each historical `available_time`;
2. realtime maintenance: keep the forward-looking global event observation pool current without making causal claims.

Rows produced from this registry are observation evidence only. They do not imply production Layer 4 eligibility, strategy failure attribution, alpha, trade direction, position size, or execution permission. Layer 10 may separately place an event family in the focused/watched event pool, which lets `trading-data` systematically acquire and standardize candidate observations for offline Layer 4 training and Layer 5 validation.

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

- Trading Economics visible calendar artifacts for macro calendars and macro release values;
- official agency/archive pages, machine-readable historical APIs, release archives, filing timestamps, announcement PDFs, and stored local snapshots for non-macro or exception routes;
- provider calendars only when official history is unavailable or as corroborating evidence;
- rule-generated calendars only for deterministic structures, and still tagged as `inferred_rule` until official confirmation is available.

Historical replay must store enough evidence refs to prove what was knowable before each model decision. It must not use later revisions, final outcomes, constituent results, or later news as if they were known at the original decision time.

## Realtime / Future Maintenance

Realtime maintenance should run bounded refreshes:

- yearly or monthly for exchange holiday and index methodology calendars;
- weekly or daily for Trading Economics macro calendars and macro release rows;
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
| Macro scheduled releases | Trading Economics visible calendar artifacts | Trading Economics visible calendar artifacts | official agency source only for manual incident review or severe TE anomaly | TE is the accepted runtime authority because it provides scheduled time plus useful expectation/previous/actual-style fields in one route; shell/scheduled fields and value fields must still obey TE row visibility |
| Treasury auctions | TreasuryDirect auction schedules, announcements, results archive | TreasuryDirect upcoming auctions and announcements | Treasury fiscal-data APIs if separately accepted | announcement/schedule time separate from auction/result time |
| Earnings and issuer events | SEC EDGAR filings, company IR archives, accepted historical earnings calendars | company IR, SEC EDGAR submissions, Nasdaq/other calendars as tentative discovery | vendor calendars for tentative dates only | company/SEC official artifacts outrank calendars; result/guidance facts require visible official artifact |
| Index reconstitution / rebalance | index provider announcements, methodology calendars, archived PDF/list files | FTSE Russell/LSEG, Nasdaq indexes, MSCI, S&P DJI official announcements/calendars | provider/member files where licensed and approved | calendar window can be known before constituent/result files; membership changes require official announcement visibility |
| Persistent event regimes | high-frequency reviewed news-topic timelines plus official action archives where available | high-frequency reviewed news-topic monitoring plus official action feeds/pages where available | Reuters/AP/Bloomberg/WSJ/FT style sources and official refs as evidence | same-day news is not required after regime is active; topic-frequency promotion must be agent-reviewed and decay-rule backed |

## Macro TE Route

Trading Economics is the accepted runtime route for macro event observations because it provides a unified calendar shape with useful market-facing fields such as expected/consensus, previous, and actual-style values when visible. `trading-data` should not run a parallel routine official-source macro calendar path by default.

Official macro agency sources are reserved for:

- incident review when TE rows are missing, malformed, delayed, or contradictory;
- one-off audit of critical macro event handling;
- future replacement only after a separate reviewed route decision.

This means macro rows can be promoted into the global event observation pool from TE alone, provided their `available_time`, retrieval evidence, row fields, and source URL are preserved. TE rows still do not become production Layer 4 conditioning samples unless Layer 10/review later accepts the event family/mechanism. They may support focused-pool candidate training after Layer 10 identifies a plausible failure relationship.

## Persistent-Regime Source Rules

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
