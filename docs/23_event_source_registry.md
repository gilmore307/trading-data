# Event Source Registry

Status: accepted source-acquisition boundary for the global event observation pool. This document defines how `trading-data` should acquire historical and realtime/future event observations before Layer 10 attribution and any future Layer 4 supervision.

## Core Rule

Event acquisition has two separate jobs:

1. historical replay: reconstruct what was knowable at each historical `available_time`;
2. realtime maintenance: keep the forward-looking global event observation pool current without making causal claims.

Rows produced from this registry are observation evidence only. They do not imply Layer 4 training eligibility, strategy failure attribution, alpha, trade direction, position size, or execution permission.

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

Historical acquisition should prefer immutable or archived official artifacts:

- official agency/archive pages, machine-readable historical APIs, release archives, filing timestamps, announcement PDFs, and stored local snapshots;
- provider calendars only when official history is unavailable or as corroborating evidence;
- rule-generated calendars only for deterministic structures, and still tagged as `inferred_rule` until official confirmation is available.

Historical replay must store enough evidence refs to prove what was knowable before each model decision. It must not use later revisions, final outcomes, constituent results, or later news as if they were known at the original decision time.

## Realtime / Future Maintenance

Realtime maintenance should run bounded refreshes:

- yearly or monthly for exchange holiday and index methodology calendars;
- weekly or daily for official macro calendars and Treasury/EIA schedules;
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

Future events may enter the global event observation pool when `available_time <= decision_time`. They remain observation-only until Layer 10/review accepts a relationship for the watched event pool.

## Source Families

| Event family | Primary historical source | Primary realtime/future source | Fallback / corroboration | Key PIT rule |
|---|---|---|---|---|
| Exchange holidays, early closes, long weekends | NYSE/Nasdaq official calendars and saved snapshots | NYSE/Nasdaq official current/future calendars | rule-generated US exchange holidays tagged `inferred_rule` until official confirmation | source page retrieval time or official published/update time; early-close details must be source-backed |
| Option expiry / triple-witching | Cboe/OCC historical calendars or archived calendars plus deterministic monthly/quarterly rules | Cboe/OCC annual calendars plus deterministic rule projection | exchange calendars and local generated rule rows | rule-generated future windows are `inferred_rule`; official calendar rows upgrade to `confirmed` |
| Macro scheduled releases | Federal Reserve, BLS, BEA, Census, Treasury, EIA official calendars/APIs/archives | same official calendars/APIs plus RSS/ICS/JSON where provided | Trading Economics visible pages as auxiliary discovery only | shell/scheduled time may be known before release; actual/revision fields only after official release visibility |
| Treasury auctions | TreasuryDirect auction schedules, announcements, results archive | TreasuryDirect upcoming auctions and announcements | Treasury fiscal-data APIs if separately accepted | announcement/schedule time separate from auction/result time |
| Earnings and issuer events | SEC EDGAR filings, company IR archives, accepted historical earnings calendars | company IR, SEC EDGAR submissions, Nasdaq/other calendars as tentative discovery | vendor calendars for tentative dates only | company/SEC official artifacts outrank calendars; result/guidance facts require visible official artifact |
| Index reconstitution / rebalance | index provider announcements, methodology calendars, archived PDF/list files | FTSE Russell/LSEG, Nasdaq indexes, MSCI, S&P DJI official announcements/calendars | provider/member files where licensed and approved | calendar window can be known before constituent/result files; membership changes require official announcement visibility |
| Persistent event regimes | official action archives plus reviewed high-quality news timelines | official action feeds/pages plus high-quality news monitoring for status updates | Reuters/AP/Bloomberg/WSJ/FT style sources as evidence refs when official sources lag | same-day news is not required after regime is active; active/shadow/decay/stale status must be PIT and decay-rule backed |

## Persistent-Regime Source Rules

Persistent regimes require interval evidence, not daily headlines. Accepted source classes include:

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
- Do not turn a global event-pool row into a Layer 4 training row without Layer 10/review promotion.
- Do not keep a persistent regime active forever without decay/staleness evidence.
- Do not bypass WAF, captcha, login, or provider terms to obtain source data.
