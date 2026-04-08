# src

This directory is the canonical home for `trading-data` code.

Use `src/` for:
- source adapters
- fetch/update/build entrypoints
- data-maintenance jobs
- future reusable data-layer modules

## Current direction

- Alpaca-related code should become the primary adapter family
- OKX and Bitget code remain useful as supplemental / backup adapter families
- downstream repos should not become the canonical home for acquisition logic
