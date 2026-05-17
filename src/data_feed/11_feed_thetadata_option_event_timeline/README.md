# 11_feed_thetadata_option_event_timeline

ThetaData specified-contract option activity event feed.

## Purpose

Produce `option_activity_event.csv` rows and one compact `<event_id>.csv` detail artifact for each triggered option activity event. The feed emits events only; it does not save rolling process state, raw trade/quote rows, or periodic chain snapshots by default.

## Required params

- `underlying` — equity underlying symbol, e.g. `AAPL`.
- `expiration` — option expiration date, e.g. `2026-05-15`.
- `right` — `CALL` or `PUT`.
- `strike` — option strike price.
- `start_date` — ThetaData request start date, `YYYY-MM-DD`.
- `end_date` — ThetaData request end date, `YYYY-MM-DD`.
- `timeframe` — event evidence-window grain: `1Min`, `5Min`, `15Min`, `30Min`, `1Hour`, or `1Day`.
- `current_standard` — task/model/run event standard. This is input, not a global threshold owned by `trading-data`.

Example `current_standard`:

```json
{
  "standard_context": {
    "standard_source": "task_key_current_standard",
    "standard_id": "opt_evt_std_Q5M8T2K1",
    "generated_at": "2026-04-24T09:30:00-04:00"
  },
  "trade_at_ask": {
    "max_price_vs_ask": 0.01,
    "min_ask_touch_ratio": 0.95
  },
  "trade_at_bid": {
    "max_price_vs_bid": 0.01,
    "min_bid_touch_ratio": 0.95
  },
  "sweep_or_block_activity": {
    "min_block_trade_size": 100,
    "min_block_notional": 100000,
    "sweep_condition_codes": []
  },
  "opening_activity": {
    "min_window_volume": 100,
    "min_volume_percentile_20d_same_time": null
  },
  "iv_high_cross_section": {
    "min_iv_percentile_by_expiration": 0.95,
    "min_iv_zscore_by_expiration": 2.0
  }
}
```

## Optional runtime params

- `output_root` — development output root at task-key top level; defaults to `storage/<task_id>`.
- `thetadata_base_url` — local ThetaData Terminal base URL; defaults to `http://127.0.0.1:25503`.
- `timeout_seconds` — request timeout; defaults to `30`.
- `registry_csv` — optional registry snapshot for retained registered-field validation; when missing, fixture/local runs use code-local field names without reading an external repository path.
- `max_events` — cap emitted events for bounded development runs; defaults to `100`.
- `auto_enrich_option_context` — when true, fetches point-in-time context from ThetaData option context endpoints instead of requiring caller-supplied OI/IV/skew/term/underlying context.
- `option_context_interval` — ThetaData historical Greeks interval for auto enrichment; defaults to `1m` to avoid oversized/truncated one-second Greek responses.
- `prior_context_date` — optional previous trading date for OI-change comparison; defaults to previous weekday.
- `term_structure_expiration` — optional comparison expiration for term-structure context; defaults to the next weekly expiration.
- `iv_context` — optional event-local IV context values used by `iv_high_cross_section`; include `prior_implied_vol` or `iv_change` for direction-study coverage. Caller-supplied context overrides auto enrichment.
- `open_interest_context` — optional point-in-time OI evidence such as `open_interest_before`, `open_interest_after`, `open_interest_change`, and `source_ref`. Caller-supplied context overrides auto enrichment.
- `skew_context` — optional point-in-time skew evidence; include `skew_direction` plus source metadata. Caller-supplied context overrides auto enrichment.
- `term_structure_context` — optional point-in-time term-structure evidence; include `term_structure_direction` plus source metadata. Caller-supplied context overrides auto enrichment.
- `underlying_context` — optional point-in-time underlying confirmation/divergence evidence such as `underlying_return_during_window` and `source_ref`. Caller-supplied context overrides auto enrichment.

## Source endpoint

ThetaData Terminal v3:

- `/v3/option/history/trade_quote`

When `auto_enrich_option_context=true`, the feed also uses these point-in-time context endpoints:

- `/v3/option/history/open_interest` for current/prior OI and OI-change.
- `/v3/option/history/greeks/implied_volatility` for target IV/change, same-strike opposite-right skew, same-strike comparison-expiration term structure, and underlying price confirmation/divergence.

Rows are transient. The feed groups them into ET evidence windows and emits a final event only when at least one supplied indicator standard is satisfied.

## Outputs

```text
<output_root>/runs/<run_id>/
  request_manifest.json
  cleaned/
    option_activity_event.jsonl
    schema.json
  saved/
    option_activity_event.csv
    <event_id>.csv
<output_root>/completion_receipt.json
```

Only `saved/option_activity_event.csv` and `saved/<event_id>.csv` are final saved outputs. Cleaned JSONL is run-local development evidence. Raw provider responses are not persisted by default.

## Directional evidence boundary

This feed preserves option activity evidence; it does not decide final directional alpha.

Current event detail records include option right, quote context, triggering trade, explicit `trade_side_type`, ask-side and bid-side trigger support, ask-touch and bid-touch statistics, trade notional, sweep/block context, OI/open-interest context, opening-vs-closing context, IV level/change, skew direction, term-structure direction, underlying confirmation/divergence, direction confidence, and an `abnormality_evidence_coverage` object.

Coverage is explicit. If upstream task keys do not provide or auto enrichment cannot retrieve OI, skew, term-structure, IV-change, sweep/block standards, or underlying confirmation inputs, the feed records the corresponding field as missing or partial; it does not silently infer a bullish/bearish conclusion. Auto enrichment filters unusable IV rows such as zero IV or high `iv_error`; early market-open trades may therefore remain incomplete until a valid point-in-time Greek row exists.

Direction hypotheses must remain explicit and reviewable:

- ask-side CALL activity may be bullish;
- ask-side PUT activity may be bearish;
- IV-only expansion without side evidence is direction-unknown path/risk expansion;
- raw call/put volume alone is not directional proof because it may be hedging, closing, or inventory flow.

If side/aggressor, sweep/block, OI/opening-vs-closing, IV-change, skew, term-structure, or underlying confirmation context is missing, downstream interpretation should use `unknown_direction_activity`, `insufficient_evidence`, or `review_required` rather than force bullish/bearish labels.

## Failure and retry

Final CSV/JSON writes are atomic. A failed run has no valid partial final output; rerun the task after fixing the cause.
