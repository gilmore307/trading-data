# Data Sparse-Checkout Policy

## Goal

Define how `data/` should be maintained when some tracked content must remain in Git/GitHub but should not stay expanded in the local working tree long-term.

This policy is for the `crypto-trading` repo.

## Core rule

If a file or directory must:

- remain tracked in the repo and on GitHub
- but not remain present in the local working tree by default

then manage it with **Git sparse-checkout**, not `.gitignore`, and not watcher-side deletion exceptions.

## Responsibility split

### Sparse-checkout is responsible for

- deciding which tracked paths are materialized locally
- keeping tracked-but-not-locally-present paths from looking like normal deletions
- letting operators temporarily bring paths back for editing

### Auto-push watcher is responsible for

- detecting Git-visible working tree changes
- auto-committing additions / modifications / deletions after cooldown
- respecting the current sparse working tree layout

The watcher should **not** invent separate protection logic for tracked files intentionally omitted by sparse-checkout.

## Data directory categories

Treat `data/` paths as belonging to one of two categories.

### A. Local-default paths

These stay present locally by default and may be edited normally.

Typical examples:

- active small metadata
- compact summaries
- index files
- config-like data
- current operator-facing artifacts

### B. Sparse-managed paths

These remain tracked remotely but are omitted locally by default.

Typical examples:

- large historical datasets
- archived snapshots
- heavy derived artifacts that are still worth versioning
- infrequently touched tracked resources

## Editing workflow for sparse-managed files

This is the required workflow for a tracked path that exists remotely but is not currently present locally.

### Normal state

- path is tracked in Git
- path is excluded by sparse-checkout
- path does not appear in local working tree
- watcher must not treat its local absence as a deletion

### To modify the path

1. temporarily add the path back into sparse-checkout
2. restore/materialize it into the working tree
3. edit the file(s)
4. allow watcher (or manual Git) to sync the modification
5. remove the path from sparse-checkout again if it should not remain local

## Important nuance: modifying a file that only exists in the cloud

For tracked sparse-managed files, "modify after local deletion" does **not** mean recreating from memory.
It means:

1. re-include the tracked path in sparse-checkout
2. let Git materialize the tracked file back into the working tree from the current branch state
3. edit that restored file
4. commit/push the resulting diff
5. optionally sparse-hide it again

That is the safe workflow.

## Do not use this anti-pattern

Do **not** do this for tracked sparse-managed files:

- delete locally
- leave path outside sparse-checkout rules
- later create a new file at the same path manually
- rely on watcher to infer intent

That makes the state ambiguous and can turn a "modify existing tracked file" workflow into accidental delete/recreate behavior.

## Proposed operator commands

We should maintain helper scripts for this repo:

- `scripts/data_sparse_include.sh <path>`
- `scripts/data_sparse_exclude.sh <path>`

Optional later helper:

- `scripts/data_sparse_edit.sh <path>`

Where:

- `include` = add path to sparse-checkout set and materialize it
- `exclude` = remove path from sparse-checkout set after sync
- `edit` = ergonomic wrapper for the include/edit/exclude lifecycle

## Default future rule for `data/`

Before tracking new `data/` content, decide explicitly:

- local-default
- or sparse-managed

Do not let tracked `data/` content drift into a mixed implicit state.

## Operational cautions

- do not use sparse-checkout for files that are edited constantly every day unless there is a strong reason
- prefer sparse-checkout for heavy or infrequently touched tracked paths
- if a sparse-managed path is needed often on this machine, reclassify it as local-default instead of repeatedly toggling it

## Next implementation step

Add helper scripts for include/exclude workflows and document the exact Git commands they run.
