# Data Runtime

Shared runtime helpers for `trading-data` feeds and sources.

- `provider_policy.py` owns fail-closed live-provider execution checks.
- `io.py` owns atomic text/JSON writes and run-scoped receipt writes.

This package must stay provider-neutral. Feed/source modules import it before using credentials, network clients, or receipt files.
