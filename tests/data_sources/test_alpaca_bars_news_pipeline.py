from __future__ import annotations
import csv,json,tempfile,unittest
from importlib import import_module
from pathlib import Path
from source_availability.http import HttpResult

class FakeBarsClient:
    def get(self,url,*,params=None,headers=None):
        return HttpResult(url=url,status=200,headers={},body=json.dumps({'bars':[{'t':'2024-01-02T05:00:00Z','o':187.15,'h':188.44,'l':183.885,'c':185.64,'v':82496943,'vw':185.846233,'n':1009074}]}).encode())
class FakeNewsClient:
    def get(self,url,*,params=None,headers=None):
        return HttpResult(url=url,status=200,headers={},body=json.dumps({'news':[{'id':1,'headline':'h','source':'benzinga','author':'a','created_at':'2024-01-09T19:46:19Z','updated_at':'2024-01-09T19:46:19Z','symbols':['AAPL'],'summary':'s','content':'','url':'https://example.test','images':[{}]}]}).encode())
class Secret:
    alias='alpaca'; path=Path('/root/secrets/alpaca.json'); present=True; keys_present=('api_key','secret_key'); values={'api_key':'k','secret_key':'s','data_endpoint':'https://data.alpaca.markets'}

class AlpacaBarsNewsPipelineTests(unittest.TestCase):
    def test_bars_pipeline_et_timestamp(self):
        p = import_module("data_sources.01_source_alpaca_bars.pipeline")
        old=p.load_secret_alias; p.load_secret_alias=lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tk={'task_id':'01_source_alpaca_bars_task_test','bundle':'01_source_alpaca_bars','params':{'symbol':'AAPL','timeframe':'1Day','start':'2024-01-02T00:00:00Z','end':'2024-01-03T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
                r=p.run(tk,run_id='01_source_alpaca_bars_run_test',client=FakeBarsClient())
                self.assertEqual(r.status,'succeeded')
                with (Path(tk['output_root'])/'runs/01_source_alpaca_bars_run_test/saved/equity_bar.csv').open(newline='') as handle:
                    row=next(csv.DictReader(handle))
                self.assertEqual(row['timestamp'],'2024-01-02T00:00:00-05:00')
                self.assertFalse((Path(tk['output_root'])/'runs/01_source_alpaca_bars_run_test/saved/equity_bar.jsonl').exists())
        finally: p.load_secret_alias=old
    def test_news_pipeline_et_timestamps(self):
        p = import_module("data_sources.03_source_alpaca_news.pipeline")
        old=p.load_secret_alias; p.load_secret_alias=lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tk={'task_id':'03_source_alpaca_news_task_test','bundle':'03_source_alpaca_news','params':{'symbols':'AAPL','start':'2024-01-09T00:00:00Z','end':'2024-01-10T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
                r=p.run(tk,run_id='03_source_alpaca_news_run_test',client=FakeNewsClient())
                self.assertEqual(r.status,'succeeded')
                with (Path(tk['output_root'])/'runs/03_source_alpaca_news_run_test/saved/equity_news.csv').open(newline='') as handle:
                    reader=csv.DictReader(handle); row=next(reader)
                self.assertEqual(reader.fieldnames,['id','timeline_headline','created_at','updated_at','symbols','summary','event_link_url'])
                self.assertEqual(row['created_at'],'2024-01-09T14:46:19-05:00')
                self.assertFalse((Path(tk['output_root'])/'runs/03_source_alpaca_news_run_test/saved/equity_news.jsonl').exists())
        finally: p.load_secret_alias=old
if __name__=='__main__': unittest.main()
