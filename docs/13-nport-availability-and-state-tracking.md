# 13 N-PORT Availability and State Tracking

This document records the intended control logic for tracking SEC/N-PORT monthly availability.

## Goal

The system needs a low-frequency, persistent way to determine whether the current month's relevant N-PORT data has become available.

## Intended operating rule

- check once per day while the current month has not yet been captured
- stop checking for that month once the month is confirmed captured
- avoid repeated/high-frequency probing

## Availability question

The core operational question is not only:
- where is the N-PORT data published?

It is also:
- how do we know whether the current month is already available?

## Needed detection behavior

The future task should determine, for the current month:
- whether a matching dataset/file/release is available
- whether it has already been downloaded/normalized locally
- whether polling should continue or stop

## Suggested state tracking

A lightweight state file is likely enough, for example:
- `context/etf_holdings/_nport_state.json`

It could track fields such as:
- `target_month`
- `last_checked_at`
- `current_month_available`
- `current_month_captured`
- `source_reference`
- `notes`

## Practical stop rule

For a given target month:
- if availability is not yet confirmed -> keep daily checking
- if availability is confirmed and the month has been captured -> stop polling for that month
- when the calendar rolls to a new target month -> resume daily checking for the new month

## Why this matters

This avoids two bad patterns:
- forgetting to ever check again
- repeatedly hitting the source after the month's data has already been captured

## Current next-step question

The remaining design work is to determine the exact signal used for availability, such as:
- a predictable file name pattern
- a listing page / dataset reference update
- another official machine-readable indicator
