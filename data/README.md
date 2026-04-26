# data/

Local runtime data area for `trading-data`.

Only README files in this tree are tracked. Generated data, provider responses, task outputs, receipts, logs, and temporary files must stay out of Git.

During the development stage, task outputs should use [`storage/`](./storage/) instead of writing to SQL databases. Durable SQL output contracts remain future `trading-storage` work.
