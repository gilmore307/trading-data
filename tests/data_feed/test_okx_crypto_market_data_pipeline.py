import json
import tempfile
import unittest
from pathlib import Path

from importlib import import_module

from feed_availability.http import HttpResult

_okx_pipeline = import_module("data_feed.04_feed_okx_crypto_market_data.pipeline")
aggregate_liquidity_bars = _okx_pipeline.aggregate_liquidity_bars
normalize_bars = _okx_pipeline.normalize_bars
normalize_trades = _okx_pipeline.normalize_trades
run = _okx_pipeline.run


class FakeOkxClient:
    def get(self, url, *, params=None, headers=None):
        if url.endswith('/history-candles'):
            payload = {
                'code': '0',
                'data': [
                    ['1601568000000', '10716.3', '10716.3', '10375', '10511.4', '46936.6', '494694868.1', '494694868.1', '1'],
                    ['1601654400000', '10777.7', '10922', '10681.6', '10716.2', '39536.6', '427380464.5', '427380464.5', '1'],
                ],
            }
        elif url.endswith('/candles'):
            payload = {
                'code': '0',
                'data': [[
                    '1777241580000', '78527.3', '78535.1', '78527.2', '78535.1',
                    '0.0013739', '0.0013739', '107.89386989', '1'
                ]],
            }
        elif url.endswith('/trades'):
            payload = {
                'code': '0',
                'data': [
                    {'instId': 'BTC-USDT', 'side': 'buy', 'sz': '0.0013739', 'px': '78535.1', 'source': '0', 'tradeId': '997363272', 'ts': '1777241590242'},
                    {'instId': 'BTC-USDT', 'side': 'sell', 'sz': '0.002', 'px': '78530.0', 'source': '0', 'tradeId': '997363273', 'ts': '1777241591242'},
                ],
            }
        else:
            payload = {'code': '404', 'msg': 'unknown fake endpoint'}
        return HttpResult(url=url, status=200, headers={}, body=json.dumps(payload).encode())


class OkxCryptoMarketDataPipelineTests(unittest.TestCase):
    def test_normalizers_use_alpaca_like_output_shapes(self):
        bars = normalize_bars('BTC-USDT', [['1777241580000', '1', '2', '0.5', '1.5', '3', '3', '4.5', '1']], '1Min')
        self.assertNotIn('data_kind', bars[0])
        self.assertNotIn('source', bars[0])
        self.assertEqual(bars[0]['timestamp'], '2026-04-26T18:13:00-04:00')

        trades = normalize_trades('BTC-USDT', [{'side': 'buy', 'sz': '0.1', 'px': '10', 'tradeId': 'abc', 'ts': '1777241590242'}])
        self.assertEqual(trades[0]['data_kind'], 'crypto_trade')
        self.assertEqual(trades[0]['price'], 10.0)
        self.assertEqual(trades[0]['notional'], 1.0)

    def test_liquidity_bar_allows_missing_quote_features(self):
        trades = normalize_trades('BTC-USDT', [
            {'side': 'buy', 'sz': '0.1', 'px': '10', 'tradeId': 'a', 'ts': '1777241590242'},
            {'side': 'sell', 'sz': '0.2', 'px': '20', 'tradeId': 'b', 'ts': '1777241591242'},
        ])
        rows = aggregate_liquidity_bars('BTC-USDT', trades, '1Min')
        self.assertNotIn('data_kind', rows[0])
        self.assertNotIn('source', rows[0])
        self.assertIsNone(rows[0]['avg_bid'])
        self.assertEqual(rows[0]['bar_trade_count'], 2)

    def test_run_saves_csv_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                'task_id': '04_feed_okx_crypto_market_data_task_test',
                'feed': '04_feed_okx_crypto_market_data',
                'params': {'instId': 'BTC-USDT', 'timeframe': '1Min', 'limit': 2},
                'output_root': str(Path(tmp) / '04_feed_okx_crypto_market_data_task_test'),
            }
            result = run(task_key, run_id='04_feed_okx_crypto_market_data_run_test', client=FakeOkxClient(), client_is_fixture=True)
            saved = Path(task_key['output_root']) / 'runs' / '04_feed_okx_crypto_market_data_run_test' / 'saved'
            self.assertEqual(result.row_counts['crypto_bar'], 1)
            self.assertNotIn('crypto_trade', result.row_counts)
            self.assertEqual(result.row_counts['crypto_liquidity_bar'], 1)
            for name in ['crypto_bar', 'crypto_liquidity_bar']:
                self.assertTrue((saved / f'{name}.csv').exists())
                self.assertFalse((saved / f'{name}.jsonl').exists())
            self.assertFalse((saved / 'crypto_trade.csv').exists())
            self.assertTrue((Path(task_key['output_root']) / 'runs' / '04_feed_okx_crypto_market_data_run_test' / 'cleaned' / 'crypto_trade_transient.jsonl').exists())
            receipt = json.loads((Path(task_key['output_root']) / 'completion_receipt.json').read_text())
            self.assertEqual(receipt['feed'], '04_feed_okx_crypto_market_data')

    def test_run_can_fetch_historical_candles_without_historical_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                'task_id': '04_feed_okx_crypto_market_data_history_task_test',
                'feed': '04_feed_okx_crypto_market_data',
                'params': {
                    'instId': 'BTC-USDT',
                    'timeframe': '1Day',
                    'limit': 100,
                    'benchmark_window_start': '2020-10-01',
                    'benchmark_window_end_exclusive': '2020-10-03',
                },
                'output_root': str(Path(tmp) / '04_feed_okx_crypto_market_data_history_task_test'),
            }
            result = run(task_key, run_id='04_feed_okx_crypto_market_data_history_run_test', client=FakeOkxClient(), client_is_fixture=True)
            saved = Path(task_key['output_root']) / 'runs' / '04_feed_okx_crypto_market_data_history_run_test' / 'saved'
            self.assertEqual(result.row_counts['crypto_bar'], 2)
            self.assertEqual(result.row_counts['crypto_liquidity_bar'], 0)
            receipt = json.loads((Path(task_key['output_root']) / 'completion_receipt.json').read_text())
            manifest = json.loads((Path(receipt['runs'][0]['output_dir']) / 'request_manifest.json').read_text())
            self.assertTrue(manifest['historical_mode'])
            self.assertIsNone(manifest['trades_endpoint'])
            self.assertTrue((saved / 'crypto_bar.csv').exists())


if __name__ == '__main__':
    unittest.main()
