"""Alpaca bars acquisition bundle."""
from __future__ import annotations
import csv,json
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from trading_data.source_availability.http import HttpClient, HttpResult
from trading_data.source_availability.sanitize import sanitize_url, sanitize_value
from trading_data.source_availability.secrets import load_secret_alias, public_secret_summary
ET=ZoneInfo('America/New_York'); UTC=timezone.utc
EQUITY_BAR_FIELDS=['symbol','timeframe','timestamp_et','open','high','low','close','volume','vwap','trade_count']
@dataclass(frozen=True)
class BundleContext: task_key:dict[str,Any]; run_dir:Path; cleaned_dir:Path; saved_dir:Path; receipt_path:Path; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class StepResult: status:str; references:list[str]=field(default_factory=list); row_counts:dict[str,int]=field(default_factory=dict); warnings:list[str]=field(default_factory=list); details:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class FetchedPayload: symbol:str; bars:list[dict[str,Any]]; secret_alias:dict[str,Any]|None=None
class AlpacaBarsError(ValueError): pass
def _now_utc(): return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _required(m,k):
    v=m.get(k)
    if v in (None,'',[]): raise AlpacaBarsError(f'alpaca_bars.params.{k} is required')
    return v
def _et_iso(v): return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(ET).isoformat()
def _json_response(r:HttpResult):
    if r.status is None: raise AlpacaBarsError(f'request failed before HTTP response: {r.error_type}: {r.error_message}')
    if r.status<200 or r.status>=300: raise AlpacaBarsError(f'request returned HTTP {r.status}: {r.error_message or r.text()[:240]}')
    return r.json()
def build_context(task_key,run_id):
    if task_key.get('bundle')!='alpaca_bars': raise AlpacaBarsError('task_key.bundle must be alpaca_bars')
    root=Path(str(task_key.get('output_root') or f"storage/{task_key.get('task_id','alpaca_bars_task')}")); run=root/'runs'/run_id
    return BundleContext(task_key,run,run/'cleaned',run/'saved',root/'completion_receipt.json',{'run_id':run_id,'started_at':_now_utc()})
def _fetch_paginated(client,url,row_key,params,headers,max_pages):
    rows=[]; evidence=[]; token=None
    for _ in range(max_pages):
        page=dict(params)
        if token: page['page_token']=token
        result=client.get(url,params=page,headers=headers); payload=_json_response(result)
        batch=payload.get(row_key,[]) if isinstance(payload,dict) else []
        if not isinstance(batch,list): raise AlpacaBarsError(f'Alpaca field {row_key!r} was not a list')
        rows.extend(batch); token=payload.get('next_page_token') if isinstance(payload,dict) else None
        evidence.append({'endpoint':sanitize_url(result.url),'http_status':result.status,'row_count':len(batch),'has_next_page':bool(token)})
        if not token: break
    else: evidence.append({'warning':f'max_pages={max_pages} reached before pagination completed'})
    return rows,evidence
def fetch(context,*,client=None):
    params=dict(context.task_key.get('params') or {}); symbol=str(_required(params,'symbol')).upper(); timeframe=str(params.get('timeframe','1Day'))
    req={'timeframe':timeframe,'start':str(_required(params,'start')),'end':str(_required(params,'end')),'limit':str(params.get('limit',1000)),'adjustment':str(params.get('adjustment','raw'))}
    if params.get('feed'): req['feed']=str(params['feed'])
    max_pages=int(params.get('max_pages',10)); client=client or HttpClient(timeout_seconds=int(params.get('timeout_seconds',20)))
    secret=load_secret_alias('alpaca'); key=secret.values.get('api_key'); sec=secret.values.get('secret_key')
    if not key or not sec: raise AlpacaBarsError('Alpaca requires api_key and secret_key')
    base=str(secret.values.get('data_endpoint') or 'https://data.alpaca.markets').rstrip('/'); headers={'APCA-API-KEY-ID':str(key),'APCA-API-SECRET-KEY':str(sec)}
    bars,evidence=_fetch_paginated(client,f'{base}/v2/stocks/{symbol}/bars','bars',req,headers,max_pages)
    context.run_dir.mkdir(parents=True,exist_ok=True); manifest=context.run_dir/'request_manifest.json'
    manifest.write_text(json.dumps({'symbol':symbol,'bar_pages':evidence,'params':sanitize_value({**req,'max_pages':max_pages}),'secret_alias':public_secret_summary(secret),'raw_count':len(bars),'raw_persistence':'not_persisted_by_default','fetched_at_utc':_now_utc()},indent=2,sort_keys=True)+'\n')
    return StepResult('succeeded',[str(manifest)],{'raw_bars_transient':len(bars)},details={'symbol':symbol}), FetchedPayload(symbol,bars,public_secret_summary(secret))
def clean(context,fetched):
    timeframe=str((context.task_key.get('params') or {}).get('timeframe','1Day')); rows=[]
    for b in fetched.bars:
        rows.append({'symbol':fetched.symbol,'timeframe':timeframe,'timestamp_et':_et_iso(b['t']),'open':b.get('o'),'high':b.get('h'),'low':b.get('l'),'close':b.get('c'),'volume':b.get('v'),'vwap':b.get('vw'),'trade_count':b.get('n')})
    context.cleaned_dir.mkdir(parents=True,exist_ok=True); path=context.cleaned_dir/'equity_bar.jsonl'
    with path.open('w') as h:
        for r in rows: h.write(json.dumps(r,sort_keys=True)+'\n')
    (context.cleaned_dir/'schema.json').write_text(json.dumps({'equity_bar':EQUITY_BAR_FIELDS},indent=2,sort_keys=True)+'\n')
    return StepResult('succeeded',[str(path),str(context.cleaned_dir/'schema.json')],{'equity_bar':len(rows)},details={'timezone':'America/New_York'})
def save(context,clean_result):
    context.saved_dir.mkdir(parents=True,exist_ok=True); refs=[]; src=context.cleaned_dir/'equity_bar.jsonl'
    rows=[json.loads(l) for l in src.read_text().splitlines() if l.strip()]; csvp=context.saved_dir/'equity_bar.csv'; cols=EQUITY_BAR_FIELDS
    with csvp.open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=cols); w.writeheader(); w.writerows(rows)
    refs.append(str(csvp)); return StepResult('succeeded',refs,dict(clean_result.row_counts),details={'format':'csv'})
def write_receipt(context,*,status,fetch_result=None,clean_result=None,save_result=None,error=None):
    context.receipt_path.parent.mkdir(parents=True,exist_ok=True); existing={'task_id':context.task_key.get('task_id'),'bundle':'alpaca_bars','runs':[]}
    if context.receipt_path.exists():
        try: existing=json.loads(context.receipt_path.read_text())
        except json.JSONDecodeError: pass
    entry={'run_id':context.metadata['run_id'],'status':status,'started_at':context.metadata.get('started_at'),'completed_at':_now_utc(),'output_dir':str(context.run_dir),'outputs':save_result.references if save_result else [],'row_counts':save_result.row_counts if save_result else clean_result.row_counts if clean_result else {},'steps':{'fetch':asdict(fetch_result) if fetch_result else None,'clean':asdict(clean_result) if clean_result else None,'save':asdict(save_result) if save_result else None},'error':None if error is None else {'type':type(error).__name__,'message':str(error)}}
    existing['runs']=[r for r in existing.get('runs',[]) if r.get('run_id')!=context.metadata['run_id']]+[entry]; existing.update({'task_id':context.task_key.get('task_id'),'bundle':'alpaca_bars'})
    context.receipt_path.write_text(json.dumps(existing,indent=2,sort_keys=True)+'\n'); return StepResult(status,[str(context.receipt_path),*entry['outputs']],entry['row_counts'],details={'run_id':context.metadata['run_id'],'error':entry['error']})
def run(task_key,*,run_id,client=None):
    c=build_context(task_key,run_id); c.cleaned_dir.mkdir(parents=True,exist_ok=True); c.saved_dir.mkdir(parents=True,exist_ok=True); fr=cr=sr=None
    try:
        fr,f=fetch(c,client=client); cr=clean(c,f); sr=save(c,cr); return write_receipt(c,status='succeeded',fetch_result=fr,clean_result=cr,save_result=sr)
    except BaseException as exc: return write_receipt(c,status='failed',fetch_result=fr,clean_result=cr,save_result=sr,error=exc)
