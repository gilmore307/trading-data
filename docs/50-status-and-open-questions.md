# 50 Status and Open Questions

This document captures current implementation status and remaining open decisions.

## Implemented now
- Alpaca market-tape path
- previous-month batch entrypoint
- current-month maintenance entrypoints
- minute-level retained market-tape outputs
- first-wave FRED / BLS / BEA / Census / Treasury fetchers
- first maintained and merged official calendar artifacts
- storage-path migration into `trading-storage`
- compaction/normalize tooling repathed to storage-aware roots

## Still incomplete / not fully hardened
- broader operational validation across all context families
- cleaner dataset-refresh evidence contract for permanent macro/context refresh
- end-to-end validation against a clean storage skeleton
- some remaining open design choices around news/options compactness and evidence contracts

## Open questions
- should options snapshots remain one canonical row per `(option_symbol, ts)` or evolve into a more explicit event/version model?
- if news grows materially, should repeated source metadata move into compact month metadata?
- how far should official release calendars be normalized into local maintained artifacts versus source-backed on-demand fetches?

## Durable recent decisions
- durable outputs belong in `trading-storage`
- signals are artifact-readiness evidence, not orchestration state
- ETFs remain regime/context proxies rather than constituent-look-through-first objects
- low-frequency context should keep source/native frequency rather than being forced into month-partitioned tape
- regime ETF/proxy monthly refresh is intended to run as recurring periodic task flow rather than planner-discovered month gaps
- calendar refresh should only occur when future event coverage is nearly exhausted; planner then expands refreshed calendar events into scheduled release tasks
