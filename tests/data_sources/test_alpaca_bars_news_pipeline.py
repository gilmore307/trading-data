from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from trading_data.source_availability.http import HttpResult

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
        import trading_data.data_sources.alpaca_bars.pipeline as p
        old=p.load_secret_alias; p.load_secret_alias=lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tk={'task_id':'alpaca_bars_task_test','bundle':'alpaca_bars','params':{'symbol':'AAPL','timeframe':'1Day','start':'2024-01-02T00:00:00Z','end':'2024-01-03T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
                r=p.run(tk,run_id='alpaca_bars_run_test',client=FakeBarsClient())
                self.assertEqual(r.status,'succeeded')
                row=json.loads((Path(tk['output_root'])/'runs/alpaca_bars_run_test/saved/equity_bar.jsonl').read_text().splitlines()[0])
                self.assertEqual(row['timestamp_et'],'2024-01-02T00:00:00-05:00')
        finally: p.load_secret_alias=old
    def test_news_pipeline_et_timestamps(self):
        import trading_data.data_sources.alpaca_news.pipeline as p
        old=p.load_secret_alias; p.load_secret_alias=lambda alias: Secret()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tk={'task_id':'alpaca_news_task_test','bundle':'alpaca_news','params':{'symbols':'AAPL','start':'2024-01-09T00:00:00Z','end':'2024-01-10T00:00:00Z'},'output_root':str(Path(tmp)/'task')}
                r=p.run(tk,run_id='alpaca_news_run_test',client=FakeNewsClient())
                self.assertEqual(r.status,'succeeded')
                row=json.loads((Path(tk['output_root'])/'runs/alpaca_news_run_test/saved/equity_news.jsonl').read_text().splitlines()[0])
                self.assertEqual(row['created_at_et'],'2024-01-09T14:46:19-05:00')
        finally: p.load_secret_alias=old
if __name__=='__main__': unittest.main()
