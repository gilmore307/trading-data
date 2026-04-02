# Data Layering and Git Policy

## Goal

Keep large market/research datasets local, while still allowing code, reports, and lightweight publishable artifacts to sync to GitHub.

## Data layers

### 1. `data/raw/`
Raw downloaded exchange data.

Examples:
- candles / kline history
- derivatives basis / funding / open interest series
- exchange-native raw feeds saved to disk

Policy:
- **local only**
- **do not upload to GitHub**

### 2. `data/intermediate/` *(target layer; introduce over time)*
Large research-process datasets and intermediate working sets.

Examples:
- parameter utility datasets
- large feature matrices
- state datasets
- clustering labels when they are too large to be practical repo assets

Policy:
- **local only**
- **do not upload to GitHub**

Note:
Some legacy files still live under `data/derived/` today even though they really belong to this layer. They should be treated by policy, not by old location name.

### 3. `data/derived/`
Smaller derived outputs that are useful for repeatable local workflows.

Examples:
- compact summaries
- review-ready JSON payloads
- lightweight dashboard inputs
- small evaluation outputs

Policy:
- may be tracked **only if reasonably small and reviewable**
- if a derived artifact becomes large, treat it as intermediate/local-only instead

### 4. `data/reports/` *(target layer; can be introduced gradually)*
Human-facing reports and publishable summaries.

Examples:
- markdown summaries
- compact JSON reports
- exported charts intended for review
- small presentation-ready bundles

Policy:
- **should be GitHub-friendly by default**

## Current practical rule

For now, the following categories should remain local and untracked unless/until they are converted into canonical GitHub-friendly partitions/summaries:

- all `data/raw/`
- large parameter utility datasets
- large market-state / clustering datasets
- large family-variant dashboard payloads

GitHub should contain primarily:

- code
- docs
- configuration
- compact summaries
- publishable reports
- lightweight dashboard payloads

## Migration direction

Over time, move legacy oversized files out of ambiguous locations and toward clearer separation:

Current practical migration approach:

- physically move oversized local-only datasets into `data/intermediate/`
- keep local compatibility symlinks at old legacy paths for existing scripts during transition
- gradually update scripts/configs to point at the clearer intermediate locations directly


- raw market downloads → `data/raw/`
- large research working sets → `data/intermediate/`
- reviewable reports → `data/reports/`
- lightweight app-facing payloads → `data/derived/` or a future explicit publish layer
