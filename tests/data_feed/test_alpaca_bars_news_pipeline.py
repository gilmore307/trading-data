from __future__ import annotations
import csv,json,tempfile,unittest
from importlib import import_module
from pathlib import Path
from feed_availability.http import HttpResult

class FakeBarsClient:
    def get(self,url,*,params=None,headers=None):
        return HttpResult(url=url,status=200,headers={},body=json.dumps({'bars':[{'t':'2024-01-02T05:00:00Z','o':187.15,'h':188.44,'l':183.885,'c':185.64,'v':82496943,'vw':185.846233,'n':1009074}]}).encode())
class FakeEmptyBarsClient:
    def get(self,url,*,params=None,headers=None):
        return HttpResult(url=url,status=200,headers={},body=json.dumps({'bars':None}).encode())
class FakeNewsClient:
    def get(self,url,*,params=None,headers=None):
        return HttpResult(url=url,status=200,headers={},body=json.dumps({'news':[{'id':1,'headline':'h','source':'benzinga','author':'a','created_at':'2024-01-09T19:46:19Z','updated_at':'2024-01-09T19:46:19Z','symbols':['AAPL'],'summary':'s','content':'','url':'https://example.test','images':[{}]}]}).encode())
class Secret:
    alias='alpaca'; path=Path('/root/secrets/alpaca.json'); present=True; keys_present=('api_key','secret_key'); values={'api_key':'k','secret_key':'s','data_endpoint':'https://data.alpaca.markets'}

class AlpacaBarsNewsPipelineTests(unittest.TestCase):
    def test_bars_pipeline_et_timestamp(self):
        p = import_module("data_feed.01_feed_alpaca_bars.pipeline")
        old=p.load_secret_alias; p.load_secret_alias=lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tk={'task_id':'01_feed_alpaca_bars_task_test','feed':'01_feed_alpaca_bars','params':{'symbol':'AAPL','timeframe':'1Day','start':'2024-01-02T00:00:00Z','end':'2024-01-03T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
                r=p.run(tk,run_id='01_feed_alpaca_bars_run_test',client=FakeBarsClient(), client_is_fixture=True)
                self.assertEqual(r.status,'succeeded')
                with (Path(tk['output_root'])/'runs/01_feed_alpaca_bars_run_test/saved/equity_bar.csv').open(newline='') as handle:
                    row=next(csv.DictReader(handle))
                self.assertEqual(row['timestamp'],'2024-01-02T00:00:00-05:00')
                self.assertFalse((Path(tk['output_root'])/'runs/01_feed_alpaca_bars_run_test/saved/equity_bar.jsonl').exists())
        finally: p.load_secret_alias=old

    def test_bars_live_client_requires_manager_controls(self):
        p = import_module("data_feed.01_feed_alpaca_bars.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            tk={'task_id':'01_feed_alpaca_bars_policy_test','feed':'01_feed_alpaca_bars','params':{'symbol':'AAPL','timeframe':'1Day','start':'2024-01-02T00:00:00Z','end':'2024-01-03T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
            r=p.run(tk,run_id='01_feed_alpaca_bars_policy_run')
            self.assertEqual(r.status,'failed')
            self.assertIn('live provider calls are not allowed', r.details['error']['message'])

    def test_injected_client_still_requires_policy_unless_marked_fixture(self):
        p = import_module("data_feed.01_feed_alpaca_bars.pipeline")
        with tempfile.TemporaryDirectory() as tmp:
            tk={'task_id':'01_feed_alpaca_bars_policy_test','feed':'01_feed_alpaca_bars','params':{'symbol':'AAPL','timeframe':'1Day','start':'2024-01-02T00:00:00Z','end':'2024-01-03T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
            r=p.run(tk,run_id='01_feed_alpaca_bars_injected_policy_run',client=FakeBarsClient())
            self.assertEqual(r.status,'failed')
            self.assertIn('live provider calls are not allowed', r.details['error']['message'])
    def test_bars_pipeline_treats_null_bars_as_empty_success(self):
        p = import_module("data_feed.01_feed_alpaca_bars.pipeline")
        old=p.load_secret_alias; p.load_secret_alias=lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tk={'task_id':'01_feed_alpaca_bars_empty_test','feed':'01_feed_alpaca_bars','params':{'symbol':'BITW','timeframe':'1Day','start':'2016-01-01T00:00:00Z','end':'2016-02-01T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
                r=p.run(tk,run_id='01_feed_alpaca_bars_empty_run_test',client=FakeEmptyBarsClient(), client_is_fixture=True)
                self.assertEqual(r.status,'succeeded')
                csv_path=Path(tk['output_root'])/'runs/01_feed_alpaca_bars_empty_run_test/saved/equity_bar.csv'
                with csv_path.open(newline='') as handle:
                    reader=csv.DictReader(handle)
                    self.assertEqual(reader.fieldnames,p.EQUITY_BAR_FIELDS)
                    self.assertEqual(list(reader),[])
                receipt=json.loads((Path(tk['output_root'])/'completion_receipt.json').read_text())
                run_receipt=json.loads((Path(tk['output_root'])/'runs/01_feed_alpaca_bars_empty_run_test/completion_receipt.json').read_text())
                self.assertEqual(run_receipt, receipt)
                run=receipt['runs'][0]
                self.assertEqual(run['row_counts'],{'equity_bar':0})
                self.assertTrue(run['steps']['fetch']['references'])
                manifest=json.loads(Path(run['steps']['fetch']['references'][0]).read_text())
                self.assertEqual(manifest['raw_count'],0)
                self.assertTrue(manifest['bar_pages'][0]['no_data_response'])
        finally: p.load_secret_alias=old
    def test_news_pipeline_et_timestamps(self):
        p = import_module("data_feed.03_feed_alpaca_news.pipeline")
        old=p.load_secret_alias; p.load_secret_alias=lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tk={'task_id':'03_feed_alpaca_news_task_test','feed':'03_feed_alpaca_news','params':{'symbols':'AAPL','start':'2024-01-09T00:00:00Z','end':'2024-01-10T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
                r=p.run(tk,run_id='03_feed_alpaca_news_run_test',client=FakeNewsClient(), client_is_fixture=True)
                self.assertEqual(r.status,'succeeded')
                with (Path(tk['output_root'])/'runs/03_feed_alpaca_news_run_test/saved/equity_news.csv').open(newline='') as handle:
                    reader=csv.DictReader(handle); row=next(reader)
                self.assertEqual(reader.fieldnames,['id','timeline_headline','created_at','updated_at','symbols','summary','event_link_url'])
                self.assertEqual(row['created_at'],'2024-01-09T14:46:19-05:00')
                self.assertFalse((Path(tk['output_root'])/'runs/03_feed_alpaca_news_run_test/saved/equity_news.jsonl').exists())
        finally: p.load_secret_alias=old
if __name__=='__main__': unittest.main()
