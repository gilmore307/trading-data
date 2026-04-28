# Deprecated macro data-kind templates

The executable `macro_data` official macro API bundle has been removed.

Macro model inputs now use `trading_economics_calendar_web` visible-page rows, which include Actual, Previous, Consensus, and Forecast when visible on Trading Economics pages.

The historical `macro_release` preview shape is retained only as a deprecated/transient reference for old registry rows and should not be used by new manager tasks. Do not add new code that writes `macro_release.csv` or routes tasks to `macro_data`.

Official macro API secret aliases may remain stored for optional future research, but they are not active `trading-data` task routes.
