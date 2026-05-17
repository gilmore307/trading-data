# Tests

Run the full fixture-safe suite with the same split used by CI:

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m unittest discover -s tests/data_feed
PYTHONPATH=src python3 -m unittest discover -s tests/data_source
PYTHONPATH=src python3 -m unittest discover -s tests/feed_availability
PYTHONPATH=src python3 -m unittest discover -s tests/feed_interfaces
```

The top-level discovery command intentionally remains paired with explicit subdirectory discovery so feed/source/interface tests cannot silently fall out of CI coverage.
