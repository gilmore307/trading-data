# alpaca adapter family

This directory is the primary source-adapter family for `trading-data`.

Alpaca is the primary long-term source and current main development focus.

Expected responsibilities here:
- stock data acquisition
- ETF/context data acquisition
- crypto overlap data acquisition
- options-context acquisition
- news acquisition
- normalization into canonical minute-level monthly partitions

This adapter family should define the mainline upstream contract surface wherever possible.
