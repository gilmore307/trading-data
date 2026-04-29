# Feed Availability Probes

Run bounded feed/API smoke probes with:

```bash
python -m feed_availability --list
python -m feed_availability --dry-run
python -m feed_availability --feed bls --feed us_treasury_fiscal_data
```

Live reports are written under `storage/feed_availability/`, which is
ignored by Git. Reports include response shape keys and tiny sanitized sample
rows only. They do not write request headers, credential values, or full raw
provider payloads.

Optional local secret aliases are read from `/root/secrets/<alias>.json`, with
alias overrides from the registered environment variables such as
`FRED_SECRET_ALIAS` and `ALPACA_SECRET_ALIAS`. Reports only include alias
metadata and key names present, never secret values.
