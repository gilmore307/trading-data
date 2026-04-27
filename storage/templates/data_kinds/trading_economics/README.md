# Trading Economics data-kind templates

This directory owns final saved CSV preview shapes for Trading Economics visible web-calendar outputs.

Boundary:

- Webpage-visible calendar rows only.
- No Trading Economics API or Download/export endpoints.
- First version supports conservative interface/parser validation, not bulk historical backfill.

Current templates:

- `trading_economics_calendar_event.preview.csv` — macro-calendar row with actual, previous, consensus, forecast, revised, importance, and source URL fields for later macro-event enrichment.
