# Acceptance

## Acceptance Summary

`trading-data` is accepted when it provides a clear, testable, and boundary-safe data upstream component for the trading system.

Acceptance focuses on:

- repository boundary clarity;
- workflow clarity;
- provider/source boundary clarity;
- data-domain boundary clarity;
- contract compatibility with `trading-main`;
- storage compatibility with `trading-storage`;
- absence of committed data, logs, notebooks, and secrets;
- evidence-backed parsing, normalization, validation, and artifact writing once code exists.

## Acceptance Rules

### For Documentation Changes

Documentation changes are acceptable when they:

- update the narrowest authoritative file;
- preserve separation between scope, context, workflow, acceptance, task, decision, and memory;
- route global helper, template, field, status, type, and shared vocabulary changes to `trading-main`;
- mark unresolved provider/contract/storage questions as open gaps;
- preserve the distinction between market board, instrument, and option data domains;
- avoid pretending that implementation or provider choices are settled before evidence exists.

### For Data Implementation Changes

Implementation changes are acceptable only when they:

- keep source code component-local to data ingestion, normalization, validation, and artifact production;
- avoid committing generated data, provider dumps, notebooks, logs, credentials, or secrets;
- include tests for parsing and validation behavior;
- avoid live provider calls in default tests unless explicitly documented and guarded;
- respect provider rate limits and retry/backoff expectations;
- produce or preserve manifest/ready-signal evidence once those contracts are accepted;
- use `trading-storage` contracts for durable output placement once storage contracts exist;
- route new shared names through `trading-main/registry/`;
- document every provider/source connector before domain pipelines depend on it.

### For Provider Integrations

Provider integrations are acceptable when they document:

- authentication method using secret aliases, not secret values;
- the local secret-store alias shape and any `trading-main` config registration needed before shared use;
- supported instruments, markets, date ranges, and granularities;
- rate limits, quota risks, and retry behavior;
- timestamp/timezone semantics;
- known data-quality caveats;
- fixture coverage for expected and error responses.

### For Artifact-Producing Changes

Artifact-producing changes are acceptable when they:

- write outputs outside Git-tracked source paths;
- produce deterministic or explainably variable outputs;
- document schema and partition assumptions;
- record validation evidence;
- produce manifests and ready signals once contracts are accepted;
- do not bypass `trading-storage` layout rules.

## Verification Commands

Current documentation-stage checks:

```bash
git status --short
find docs -maxdepth 1 -type f | sort
find . -maxdepth 2 -type f | sort
```

Once implementation exists, acceptance must add appropriate commands for:

- unit tests;
- fixture-based provider tests;
- lint/type checks if configured;
- schema or contract validation;
- artifact/manifest/ready-signal validation.

## Required Review Evidence

Every accepted change should provide:

- changed files;
- boundary impact;
- contract impact;
- registry impact;
- storage impact;
- test/verification output;
- confirmation that no data, logs, notebooks, credentials, or secrets were committed;
- unresolved gaps routed to `docs/04_task.md`.

## Rejection Reasons

A change must be rejected or returned if it:

- commits generated datasets, raw dumps, logs, notebooks, or credentials;
- adds strategy/model/execution/dashboard behavior;
- invents shared fields/statuses/types without `trading-main` registry review;
- stores secret values or provider keys;
- makes live provider calls in default tests without guardrails;
- ignores provider rate limits;
- writes artifacts to undocumented paths;
- claims acceptance without test or inspection evidence;
- duplicates global contract definitions locally instead of referencing `trading-main`.
