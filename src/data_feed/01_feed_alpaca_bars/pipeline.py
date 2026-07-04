"""Alpaca bars acquisition feed."""
from __future__ import annotations
import json
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from feed_availability.http import HttpClient, HttpResult
from feed_availability.sanitize import sanitize_url, sanitize_value
from feed_availability.secrets import load_secret_alias, public_secret_summary
from data_runtime.provider_policy import require_provider_execution_allowed
from data_runtime.config import resolve_output_root
from data_runtime.io import write_receipt_bundle
from data_source.m01_market_regime_data_acquisition.pipeline import FIELDS as EQUITY_BAR_FIELDS
from data_source.m01_market_regime_data_acquisition.pipeline import OUTPUT_TABLE
from storage.sql import PostgresSqlTableWriter, SqlTableWriter
ET=ZoneInfo('America/New_York'); UTC=timezone.utc
@dataclass(frozen=True)
class FeedContext: task_key:dict[str,Any]; run_dir:Path; receipt_path:Path; metadata:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class StepResult: status:str; references:list[str]=field(default_factory=list); row_counts:dict[str,int]=field(default_factory=dict); warnings:list[str]=field(default_factory=list); details:dict[str,Any]=field(default_factory=dict)
@dataclass(frozen=True)
class FetchedPayload: symbol:str; bars:list[dict[str,Any]]; secret_alias:dict[str,Any]|None=None
@dataclass(frozen=True)
class CleanedPayload: rows:list[dict[str,Any]]
class AlpacaBarsError(ValueError): pass
def _now_utc(): return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _required(m,k):
    v=m.get(k)
    if v in (None,'',[]): raise AlpacaBarsError(f'01_feed_alpaca_bars.params.{k} is required')
    return v
def _et_iso(v): return datetime.fromisoformat(str(v).replace('Z','+00:00')).astimezone(ET).isoformat()
def _json_response(r:HttpResult):
    if r.status is None: raise AlpacaBarsError(f'request failed before HTTP response: {r.error_type}: {r.error_message}')
    if r.status<200 or r.status>=300: raise AlpacaBarsError(f'request returned HTTP {r.status}: {r.error_message or r.text()[:240]}')
    return r.json()
def build_context(task_key,run_id):
    if task_key.get('feed')!='01_feed_alpaca_bars': raise AlpacaBarsError('task_key.feed must be 01_feed_alpaca_bars')
    root=resolve_output_root(task_key, default_task_id="01_feed_alpaca_bars_task"); run=root/'runs'/run_id
    return FeedContext(task_key,run,root/'completion_receipt.json',{'run_id':run_id,'started_at':_now_utc()})
def _fetch_paginated(client,url,row_key,params,headers,max_pages):
    rows=[]; evidence=[]; token=None
    for _ in range(max_pages):
        page=dict(params)
        if token: page['page_token']=token
        result=client.get(url,params=page,headers=headers); payload=_json_response(result)
        raw_batch=payload.get(row_key,[]) if isinstance(payload,dict) else []
        no_data_response=raw_batch is None
        batch=[] if no_data_response else raw_batch
        if not isinstance(batch,list): raise AlpacaBarsError(f'Alpaca field {row_key!r} was not a list')
        rows.extend(batch); token=payload.get('next_page_token') if isinstance(payload,dict) else None
        evidence.append({'endpoint':sanitize_url(result.url),'http_status':result.status,'row_count':len(batch),'has_next_page':bool(token),'no_data_response':no_data_response})
        if not token: break
    else: evidence.append({'warning':f'max_pages={max_pages} reached before pagination completed'})
    return rows,evidence
def fetch(context,*,client=None,client_is_fixture=False):
    params=dict(context.task_key.get('params') or {}); symbol=str(_required(params,'symbol')).upper(); timeframe=str(params.get('timeframe','1Day'))
    req={'timeframe':timeframe,'start':str(_required(params,'start')),'end':str(_required(params,'end')),'limit':str(params.get('limit',1000)),'adjustment':str(params.get('adjustment','raw'))}
    if params.get('feed'): req['feed']=str(params['feed'])
    max_pages=int(params.get('max_pages',10))
    if not client_is_fixture:
        require_provider_execution_allowed(context.task_key, provider='alpaca', endpoint_family='bars', requested_symbols=1, requested_rows=int(params.get('limit',1000))*max_pages, requested_requests=max_pages, requested_start=req.get('start'), requested_end=req.get('end'))
    client=client or HttpClient(timeout_seconds=int(params.get('timeout_seconds',20)))
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
        rows.append({'symbol':fetched.symbol,'timeframe':timeframe,'timestamp':_et_iso(b['t']),'bar_open':b.get('o'),'bar_high':b.get('h'),'bar_low':b.get('l'),'bar_close':b.get('c'),'bar_volume':b.get('v'),'bar_vwap':b.get('vw'),'bar_trade_count':b.get('n')})
    context.run_dir.mkdir(parents=True,exist_ok=True); schema_path=context.run_dir/'schema.json'
    schema_path.write_text(json.dumps({'equity_bar':EQUITY_BAR_FIELDS,'retention':'sql_only_no_jsonl_or_csv_payload'},indent=2,sort_keys=True)+'\n')
    return StepResult('succeeded',[str(schema_path)],{'equity_bar':len(rows)},details={'timezone':'America/New_York','retention':'sql_only_no_jsonl_or_csv_payload'}), CleanedPayload(rows)
def save(context,clean_result,payload,*,sql_writer:SqlTableWriter|None=None):
    writer=sql_writer or PostgresSqlTableWriter.from_config({})
    if payload.rows:
        metadata=writer.write_rows(table=OUTPUT_TABLE,columns=EQUITY_BAR_FIELDS,rows=payload.rows,key_columns=['symbol','timeframe','timestamp'])
    else:
        metadata={'table':OUTPUT_TABLE,'qualified_table':OUTPUT_TABLE,'rows_written':0,'driver':'postgresql','storage_target_id':'trading_data_postgres'}
    reference=str(metadata.get('qualified_table') or metadata.get('table') or OUTPUT_TABLE)
    return StepResult('succeeded',[reference],dict(clean_result.row_counts),details={'format':'sql_table','table':OUTPUT_TABLE,'columns':EQUITY_BAR_FIELDS,'storage':metadata,'file_payload_deleted':True})
def _compact_receipt_run(entry:dict[str,Any])->dict[str,Any]:
    steps=entry.get('steps') if isinstance(entry.get('steps'),dict) else {}
    save_step=steps.get('save') if isinstance(steps.get('save'),dict) else {}
    clean_step=steps.get('clean') if isinstance(steps.get('clean'),dict) else {}
    fetch_step=steps.get('fetch') if isinstance(steps.get('fetch'),dict) else {}
    return {
        'run_id':entry.get('run_id'),
        'status':entry.get('status'),
        'started_at':entry.get('started_at'),
        'completed_at':entry.get('completed_at'),
        'output_dir':entry.get('output_dir'),
        'outputs':[item for item in entry.get('outputs') or [] if isinstance(item,str)],
        'row_counts':entry.get('row_counts') or {},
        'source_table':OUTPUT_TABLE,
        'retention':'sql_only_no_jsonl_or_csv_payload',
        'request_manifest_refs':[item for item in fetch_step.get('references') or [] if isinstance(item,str)],
        'schema_refs':[item for item in clean_step.get('references') or [] if isinstance(item,str)],
        'save_refs':[item for item in save_step.get('references') or [] if isinstance(item,str)],
        'error':entry.get('error'),
    }
def write_receipt(context,*,status,fetch_result=None,clean_result=None,save_result=None,error=None):
    context.receipt_path.parent.mkdir(parents=True,exist_ok=True); existing={'task_id':context.task_key.get('task_id'),'feed':'01_feed_alpaca_bars','runs':[]}
    if context.receipt_path.exists():
        try: existing=json.loads(context.receipt_path.read_text())
        except json.JSONDecodeError: pass
    entry={'run_id':context.metadata['run_id'],'status':status,'started_at':context.metadata.get('started_at'),'completed_at':_now_utc(),'output_dir':str(context.run_dir),'outputs':save_result.references if save_result else [],'row_counts':save_result.row_counts if save_result else clean_result.row_counts if clean_result else {},'steps':{'fetch':asdict(fetch_result) if fetch_result else None,'clean':asdict(clean_result) if clean_result else None,'save':asdict(save_result) if save_result else None},'error':None if error is None else {'type':type(error).__name__,'message':str(error)}}
    compact_entry=_compact_receipt_run(entry)
    compact_runs=[_compact_receipt_run(r) for r in existing.get('runs',[]) if isinstance(r,dict) and r.get('run_id')!=context.metadata['run_id']]
    existing['runs']=compact_runs+[compact_entry]; existing.update({'task_id':context.task_key.get('task_id'),'feed':'01_feed_alpaca_bars','contract_type':'alpaca_bars_monthly_source_receipt','retention':'sql_only_no_jsonl_or_csv_payload'})
    run_payload={'task_id':context.task_key.get('task_id'),'feed':'01_feed_alpaca_bars','contract_type':'alpaca_bars_run_receipt','run':entry,'runs':[entry]}
    write_receipt_bundle(context.receipt_path, context.run_dir, existing, run_payload=run_payload); return StepResult(status,[str(context.receipt_path),*entry['outputs']],entry['row_counts'],details={'run_id':context.metadata['run_id'],'error':entry['error']})
def run(task_key,*,run_id,client=None,sql_writer:SqlTableWriter|None=None,client_is_fixture=False):
    c=build_context(task_key,run_id); fr=cr=sr=None
    try:
        fr,f=fetch(c,client=client,client_is_fixture=client_is_fixture); cr,payload=clean(c,f); sr=save(c,cr,payload,sql_writer=sql_writer); return write_receipt(c,status='succeeded',fetch_result=fr,clean_result=cr,save_result=sr)
    except Exception as exc: return write_receipt(c,status='failed',fetch_result=fr,clean_result=cr,save_result=sr,error=exc)
