# ETF data-kind templates

This directory owns final saved CSV preview shapes for issuer-published ETF holdings outputs.

Boundary:

- ETF issuer websites/files are the source of truth for constituents and weights.
- Third-party aggregators do not replace issuer data without explicit review.
- Source-specific raw files/pages are run-local evidence; model-facing saved output is normalized CSV.

Current templates:

- `etf_holding_snapshot.preview.csv` — one constituent row for one ETF/as-of-date snapshot.
