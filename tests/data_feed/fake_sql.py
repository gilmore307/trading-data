from __future__ import annotations


class FakeSqlWriter:
    def __init__(self):
        self.calls = []

    def write_rows(self, *, table, columns, rows, key_columns):
        self.calls.append(
            {
                "table": table,
                "columns": tuple(columns),
                "rows": [dict(row) for row in rows],
                "key_columns": tuple(key_columns),
            }
        )
        return {"qualified_table": f"trading_data.{table}", "table": table, "rows_written": len(rows), "driver": "fake"}

    def rows_for(self, table):
        for call in self.calls:
            if call["table"] == table:
                return call["rows"]
        raise AssertionError(f"table was not written: {table}")
