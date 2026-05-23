# Data Runtime

Shared runtime helpers for `trading-data` feeds and sources.

- `config.py` owns environment-overridable local path defaults.
- `exchange_calendar.py` owns narrow US equity session-open timing for point-in-time availability. It is not yet a full session/holiday exposure engine for Layer 6 calendar risk.
- `provider_policy.py` owns fail-closed live-provider execution checks.
- `io.py` owns atomic text/JSON writes and run-scoped receipt writes.

This package must stay provider-neutral. Feed/source modules import it before using credentials, network clients, or receipt files.
