# Memory

## Durable Local Notes

- `trading-data` is the upstream data producer, not a model, strategy, execution, dashboard, or global storage repository.
- Direct route: provider/API/web/file -> `data_feed` -> `data_source` -> `data_feature` -> SQL/artifact handoff.
- Generated datasets, provider dumps, logs, notebooks, credentials, and secrets must stay out of Git.
- Shared fields, statuses, type values, data kinds, helper surfaces, and reusable templates discovered here must route through `trading-manager` for registry/docs review.
- Durable layout, manifests, artifact references, ready signals, retention, backup, and restore belong to `trading-storage`.
- Default tests should avoid live provider calls unless explicitly guarded.
- Market-state discovery, labels, training, evaluation, and promotion belong in `trading-model`; `trading-data` emits observed data and deterministic features only.
- Historical planning labels were market board data / 盘面数据, instrument data / 标的数据, and option data / 期权数据. Current docs should prefer feed/source/feature boundaries and model-layer mappings.
- `trading-manager` issues historical task/request instructions. `trading-data` executes the accepted source/feed route and writes reviewed outputs plus sanitized evidence.
- Accepted SQL outputs are the preferred numbered-source boundary. File artifacts and runtime evidence default to `trading-storage/storage/source_data/`; component-local `storage/` roots should not be created.
- Realtime data and broker-facing execution feeds belong to `trading-execution`.

## Provider Notes

- OKX uses `OKX_SECRET_ALIAS` -> source alias `okx`, backed by `/root/secrets/okx.json` with `api_key`, `secret_key`, `passphrase`, `allowed_ip_address`, and `api_key_remark_name`.
- Alpaca uses `ALPACA_SECRET_ALIAS` -> source alias `alpaca`, backed by `/root/secrets/alpaca.json` with `api_key`, `secret_key`, and `endpoint`.
- ThetaData uses `THETADATA_SECRET_ALIAS` -> source alias `thetadata`, backed by `/root/secrets/thetadata.json`. Theta Terminal v3 runs outside Git under `/root/tools/thetadata-terminal/` and serves `127.0.0.1:25503` when started.
- FRED, Census, BEA, and BLS aliases remain available for reviewed economic-data work. Use FRED only for FRED/St. Louis Fed/ALFRED-unique data or explicitly approved FRED-native research series/groups; use official agency sources for canonical agency measures.
- U.S. Treasury Fiscal Data is open/no-key per official docs.
- FOMC calendar, official macro release calendars, and ETF holdings should use official source pages/files and preserve source URL, as-of/publication time, retrieval time, and format.

## Current Route Decisions

- `macro_data` is not an active executable feed. Macro model inputs use `07_feed_trading_economics_calendar_web` visible-page rows unless a separately reviewed route replaces it.
- Alpaca raw trades/quotes are transient by default; `02_feed_alpaca_liquidity` persists ET-aligned aggregate `equity_liquidity_bar` rows.
- ThetaData option feeds are split by use case: selection snapshot, specified-contract primary tracking, and event timeline.
- `source_06_position_execution` is selected-contract option market-data tracking for `OptionExpressionModel` replay/evaluation; it is not a separate execution model.
- `source_02_target_candidate_holdings` preserves point-in-time visibility; absent explicit evidence, holdings become available at the next regular US session open after `as_of_date`.
- `equity_abnormal_activity_event` default standard is conservative and not production calibrated; production labels/gates require reviewed historical calibration.

## Runtime JSON Rules

- Keep task/request JSON and completion receipts minimal: include only fields consumed by manager, runner, feed/source code, or receipt readers.
- Per-run evidence belongs in run receipts/manifests, not stable task definitions.
- Runtime fields that become shared contracts need `trading-manager` registry review.
- API-specific source design starts from the manager templates: task key/request, source README, fetch spec, clean spec, save spec, completion receipt, and fixture policy.
