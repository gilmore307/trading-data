from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from trading_data.data_sources.alpaca_quotes_trades.pipeline import aggregate_liquidity_bars, aggregate_quotes, aggregate_trades, run
from trading_data.source_availability.http import HttpResult


class FakeAlpacaClient:
    def get(self, url, *, params=None, headers=None):
        if url.endswith('/trades'):
            payload = {
                'trades': [
                    {'t': '2024-01-02T14:30:00.011509342Z', 'p': 187.18, 's': 2, 'x': 'P', 'i': 1, 'c': ['@'], 'z': 'C'},
                    {'t': '2024-01-02T14:30:30.000000000Z', 'p': 187.20, 's': 3, 'x': 'Q', 'i': 2, 'c': ['@'], 'z': 'C'},
                    {'t': '2024-01-02T14:31:00.000000000Z', 'p': 187.10, 's': 1, 'x': 'Q', 'i': 3, 'c': ['@'], 'z': 'C'},
                ]
            }
        else:
            payload = {
                'quotes': [
                    {'t': '2024-01-02T14:30:00.004605455Z', 'bp': 187.10, 'bs': 30, 'bx': 'P', 'ap': 187.19, 'as': 1, 'ax': 'P', 'c': ['R'], 'z': 'C'},
                    {'t': '2024-01-02T14:30:30.000000000Z', 'bp': 187.12, 'bs': 20, 'bx': 'P', 'ap': 187.22, 'as': 2, 'ax': 'P', 'c': ['R'], 'z': 'C'},
                    {'t': '2024-01-02T14:31:00.000000000Z', 'bp': 187.00, 'bs': 10, 'bx': 'P', 'ap': 187.15, 'as': 4, 'ax': 'P', 'c': ['R'], 'z': 'C'},
                ]
            }
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class AlpacaQuotesTradesPipelineTests(unittest.TestCase):
    def test_trade_aggregation_uses_et_buckets(self):
        rows = aggregate_trades('AAPL', [
            {'t': '2024-01-02T14:30:00Z', 'p': 10, 's': 2},
            {'t': '2024-01-02T14:30:30Z', 'p': 12, 's': 3},
        ], '1Min')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['interval_start_et'], '2024-01-02T09:30:00-05:00')
        self.assertEqual(rows[0]['trade_count'], 2)
        self.assertEqual(rows[0]['trade_volume'], 5)
        self.assertEqual(rows[0]['trade_vwap'], 11.2)

    def test_quote_aggregation_spread_features(self):
        rows = aggregate_quotes('AAPL', [
            {'t': '2024-01-02T14:30:00Z', 'bp': 10, 'bs': 2, 'ap': 11, 'as': 4},
            {'t': '2024-01-02T14:30:10Z', 'bp': 10.5, 'bs': 3, 'ap': 11.5, 'as': 5},
        ], '1Min')
        self.assertEqual(rows[0]['quote_count'], 2)
        self.assertEqual(rows[0]['avg_mid'], 10.75)
        self.assertEqual(rows[0]['avg_spread'], 1.0)
        self.assertEqual(rows[0]['avg_bid_size'], 2.5)

    def test_liquidity_bar_combines_interval_rows(self):
        rows = aggregate_liquidity_bars('AAPL', [{'t': '2024-01-02T14:30:00Z', 'p': 11, 's': 1}], [{'t': '2024-01-02T14:30:00Z', 'bp': 10, 'bs': 1, 'ap': 12, 'as': 1}], '1Min')
        self.assertEqual(rows[0]['vwap_minus_avg_mid'], 0.0)

    def test_pipeline_saves_only_derived_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                'task_id': 'alpaca_quotes_trades_task_test',
                'bundle': 'alpaca_quotes_trades',
                'params': {'symbol': 'AAPL', 'start': '2024-01-02T14:30:00Z', 'end': '2024-01-02T14:32:00Z', 'timeframe': '1Min'},
                'output_root': str(Path(tmp) / 'alpaca_quotes_trades_task_test'),
            }
            # Patch secrets by monkeypatching module loader.
            import trading_data.data_sources.alpaca_quotes_trades.pipeline as pipeline
            class Secret:
                alias='alpaca'; path=Path('/root/secrets/alpaca.json'); present=True; keys_present=('api_key','secret_key'); values={'api_key':'k','secret_key':'s','data_endpoint':'https://data.alpaca.markets'}
            old = pipeline.load_secret_alias
            pipeline.load_secret_alias = lambda alias: Secret()
            try:
                result = run(task_key, run_id='alpaca_quotes_trades_run_test', client=FakeAlpacaClient())
            finally:
                pipeline.load_secret_alias = old
            self.assertEqual(result.status, 'succeeded')
            saved = Path(task_key['output_root']) / 'runs' / 'alpaca_quotes_trades_run_test' / 'saved'
            self.assertTrue((saved / 'equity_liquidity_bar.csv').exists())
            self.assertFalse((saved / 'equity_liquidity_bar.jsonl').exists())
            self.assertFalse((saved / 'equity_trade_bar_derived.jsonl').exists())
            self.assertFalse((saved / 'equity_quote_bar_derived.jsonl').exists())
            self.assertFalse((saved / 'raw_trades.jsonl').exists())
            receipt = json.loads((Path(task_key['output_root']) / 'completion_receipt.json').read_text())
            self.assertEqual(receipt['runs'][0]['row_counts']['equity_liquidity_bar'], 2)


if __name__ == '__main__':
    unittest.main()
