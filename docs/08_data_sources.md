# Data Sources

`trading-data` must connect to external and approved local data sources before it can produce cleaned data outputs.

This file defines the source-connection boundary: where provider adapters belong, how credentials are referenced, and what must be documented before a provider can become part of a data domain pipeline.

## Source Layer Purpose

The first implementation layer should be data-source connection and provider adaptation.

It should own:

- provider client setup;
- authentication by secret alias;
- request construction;
- rate-limit and quota handling;
- response capture for normalization;
- provider-specific error handling;
- provider capability documentation;
- fixture or mock coverage for default tests.

It should not own:

- strategy signals;
- model labels or inference;
- execution decisions;
- dashboard presentation;
- durable storage policy;
- provider credentials or secret values.

## Future Source Layout

No source package exists yet. When implementation starts, the first source area should be a provider/source connector layer, with exact package layout accepted before code lands.

A likely Python package shape is:

```text
src/trading_data/
  sources/          Provider adapters and source capability descriptors.
  domains/          Domain assembly for market_board_data, instrument_data, option_data.
  normalize/        Provider-to-output normalization logic.
  validate/         Data quality checks.
  outputs/          Artifact/manifests/ready-signal writers after contracts are accepted.
tests/              Component tests, with README inventory for each test script.
```

Shared helpers belong in `trading-main`, not in a local `helpers/` folder.

This is a planning shape, not an accepted implementation contract. Any final source layout must update docs and tests in the same change.

## Secret And Credential Rule

Provider tokens, API keys, account identifiers, private keys, and credentials must never be committed to this repository.

Credential material belongs outside Git under the local secrets store:

```text
/root/secrets/<provider>/<credential-name>
```

Shared or reviewed references should be stored as secret aliases, not values. When a provider credential becomes a cross-repository or durable config dependency, register a `config` row in `trading-main` whose payload is the secret alias.

Example alias shape:

```text
provider-name/api-token
provider-name/api-key
provider-name/account-id
```

OKX is the first accepted provider config surface for crypto data acquisition and later trading access. Source credentials use one JSON secret file per provider/source. Additional provider aliases remain open until providers are selected.


## Registered Provider Configs

Current registered provider config surface:

| Provider | Purpose | Registered config keys | Secret aliases / values | Notes |
|---|---|---|---|---|
| OKX | Crypto data acquisition and later trading access. | `OKX_SECRET_ALIAS`, `OKX_ALLOWED_IP_ADDRESS`, `OKX_API_KEY_REMARK_NAME` | source alias `okx`; JSON path `/root/secrets/okx.json`; JSON keys `api_key`, `secret_key`, `passphrase`; allowed IPv4 `66.206.20.138`; remark `OpenClaw` | Secret values live in `/root/secrets/okx.json` and must not be copied into this repository. |

`trading-main` owns the registry rows for this source-level alias, registered JSON key names, and non-secret metadata. `trading-data` may use the alias once implementation has a connector boundary and default tests do not require live credentials.

## Provider Inventory Template

Each provider added later should document:

| Field | Meaning |
|---|---|
| Provider name | Human-readable provider name. |
| Provider role | Which data domain(s) it supports. |
| Secret alias | Alias path only; never the secret value. |
| Authentication method | Token, API key, OAuth, signed request, local file, etc. |
| Supported instruments | Equities, ETFs, options, indexes, macro series, calendars, etc. |
| Supported ranges/granularity | Time range, bar size, snapshot support, chain history, etc. |
| Rate limits and quotas | Calls/minute, calls/day, paid-plan limits, reset behavior. |
| Timestamp semantics | UTC, exchange local, provider local, timezone fields, market session behavior. |
| Data-quality caveats | Gaps, delays, survivorship risks, stale fields, adjusted/unadjusted behavior. |
| Fixture policy | Whether sample responses may be stored and how they are sanitized. |

## Connection Acceptance Checklist

A provider/source connector is acceptable only when:

- no secret values are committed;
- credentials are referenced by alias;
- provider capabilities and limitations are documented;
- default tests do not require live credentials or network calls;
- rate-limit behavior is documented before automation loops are introduced;
- timestamp and timezone behavior is documented;
- provider response examples are sanitized if fixtures are committed;
- any shared config keys or provider-independent vocabulary are routed through `trading-main`.

## Open Provider Decisions

- Which non-OKX provider(s), if any, support market board data?
- Which provider(s) support non-crypto instrument data?
- Whether OKX option data coverage is sufficient for the intended option data domain, or another options provider is needed.
- Which additional source-level secret aliases should be registered in `trading-main`?
- What live-call guardrail is acceptable for manual provider smoke tests?
- Which provider fixtures are safe and useful to commit?
