# data_feed

Smallest-unit provider/source acquisition lives here.

A feed module talks to one provider/API/web/file family and returns normalized feed-level evidence. It may expose a CLI for local or manager-triggered runs, but it must not own model-input orchestration.

Boundary:

- provider requests, pagination, retries, rate limits, entitlement handling;
- credential lookup by alias only;
- timestamp normalization and feed-level cleaning;
- final cleaned feed artifacts or transient rows for a source;
- fixture-safe tests and explicit provider-call guardrails.

Manager-facing composition belongs in `data_source`. Deterministic model-layer feature construction belongs in `data_feature`.
