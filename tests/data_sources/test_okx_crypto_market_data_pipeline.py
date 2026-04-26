import json
import tempfile
import unittest
from pathlib import Path

from trading_data.source_availability.http import HttpResult
from trading_data.data_sources.okx_crypto_market_data.pipeline import (
    aggregate_liquidity_bars,
    normalize_bars,
    normalize_trades,
    run,
)


class FakeOkxClient:
    def get(self, url, *, params=None, headers=None):
        if url.endswith('/candles'):
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
        self.assertEqual(bars[0]['data_kind'], 'crypto_bar')
        self.assertEqual(bars[0]['timestamp_et'], '2026-04-26T18:13:00-04:00')

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
        self.assertEqual(rows[0]['data_kind'], 'crypto_liquidity_bar')
        self.assertEqual(rows[0]['quote_features_available'], 'false')
        self.assertIsNone(rows[0]['avg_bid'])
        self.assertEqual(rows[0]['trade_count'], 2)

    def test_run_saves_csv_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            task_key = {
                'task_id': 'okx_crypto_market_data_task_test',
                'bundle': 'okx_crypto_market_data',
                'params': {'instId': 'BTC-USDT', 'timeframe': '1Min', 'limit': 2},
                'output_root': str(Path(tmp) / 'okx_crypto_market_data_task_test'),
            }
            result = run(task_key, run_id='okx_crypto_market_data_run_test', client=FakeOkxClient())
            saved = Path(task_key['output_root']) / 'runs' / 'okx_crypto_market_data_run_test' / 'saved'
            self.assertEqual(result.row_counts['crypto_bar'], 1)
            self.assertEqual(result.row_counts['crypto_trade'], 2)
            self.assertEqual(result.row_counts['crypto_liquidity_bar'], 1)
            for name in ['crypto_bar', 'crypto_trade', 'crypto_liquidity_bar']:
                self.assertTrue((saved / f'{name}.csv').exists())
                self.assertFalse((saved / f'{name}.jsonl').exists())
            receipt = json.loads((Path(task_key['output_root']) / 'completion_receipt.json').read_text())
            self.assertEqual(receipt['bundle'], 'okx_crypto_market_data')


if __name__ == '__main__':
    unittest.main()
