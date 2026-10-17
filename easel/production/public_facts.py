"""Explicit, authorized public-fact search with persisted dated evidence.

Brave's documented web search endpoint is used directly; no developer tooling,
implicit browser access, arbitrary URL fetch, or model-generated citation counts
as retrieved evidence. Search snippets remain untrusted, partial source material.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html import unescape
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import Field

from .contracts import Contract, canonical_json, fingerprint
from .model_tasks import ModelTaskError
from .store import utc_now
from .tools import ScopedTool
from easel.materials.store import MaterialFileStore, digest_file

IDENTITY={'provider':'brave','model':'web-search','mode':'search'}
ENDPOINT='https://api.search.brave.com/res/v1/web/search'


class PublicFactQuery(Contract):
    query: str = Field(min_length=1,max_length=400)
    count: int = Field(default=5,ge=1,le=10)


def public_fact_capabilities(settings):
    enabled=settings.get('EASEL_PUBLIC_FACTS_PROVIDER','').strip()=='brave'
    available=bool(enabled and settings.get('BRAVE_SEARCH_API_KEY','').strip())
    return [{**IDENTITY,'label':'公共事实检索 · Brave','available':available}]


def _text(value,limit):
    return unescape(re.sub(r'<[^>]*>','',str(value or '')))[:limit]


def _source_url(value):
    """A citation only; no network request follows a search result URL."""
    try:
        url=urlsplit(value)
        host=url.hostname or ''
        if url.scheme!='https' or not host or url.username or url.password or url.port not in (None,443):return None
        if host in {'localhost','localhost.localdomain'} or host.endswith(('.localhost','.local','.internal')):return None
        try:
            if not ipaddress.ip_address(host).is_global:return None
        except ValueError:pass
        if re.search(r'(?i)(?:^|&)(api[_-]?key|access[_-]?token|token|signature|secret)=',url.query):return None
        return urlunsplit((url.scheme,url.netloc,url.path,url.query,''))
    except (TypeError,ValueError):return None


class BravePublicFacts:
    def __init__(self,key,*,transport=None,timeout=20):
        self._key=key.strip();self._transport=transport;self.timeout=timeout

    def validate(self,args:PublicFactQuery):
        if not self._key:raise ModelTaskError('capability_unavailable','公共事实检索服务尚未配置')
        if not args.query.strip() or re.search(r'(?i)\b(api[_-]?key|access[_-]?token|secret|password)\s*[:=]',args.query):
            raise ModelTaskError('invalid_search','公共事实查询无效或包含凭证字段')

    def search(self,args:PublicFactQuery):
        self.validate(args)
        try:
            with httpx.Client(transport=self._transport,trust_env=False,follow_redirects=False,timeout=self.timeout) as client:
                with client.stream('GET',ENDPOINT,params={'q':args.query.strip(),'count':args.count,'extra_snippets':'false'},
                    headers={'X-Subscription-Token':self._key,'Accept':'application/json'}) as response:
                    if response.status_code!=200:raise ModelTaskError('public_facts_unavailable','公共事实检索未成功，不能据此声称已核实')
                    body=bytearray()
                    for part in response.iter_bytes():
                        body.extend(part)
                        if len(body)>1024*1024:raise ModelTaskError('public_facts_unavailable','事实检索结果超过安全长度')
            payload=json.loads(body)
            values=payload.get('web',{}).get('results',[])
            if not isinstance(values,list):raise ValueError
        except (httpx.HTTPError,ValueError,TypeError,AttributeError):
            raise ModelTaskError('public_facts_unavailable','事实检索响应不可用，现有成果已保留') from None
        observed=datetime.now(timezone.utc).isoformat()
        sources=[]
        for value in values[:args.count]:
            if not isinstance(value,dict):continue
            url=_source_url(value.get('url'))
            if not url:continue
            sources.append({'source_id':fingerprint(url)[:24],'source_url':url,'title':_text(value.get('title'),300),
                'snippet':_text(value.get('description'),1500),'observed_at':observed,
                'published_at':_text(value.get('page_age'),100) or None})
        return {'schema_version':1,'provider':'brave','query':args.query,'observed_at':observed,'sources':sources,
                'evidence_kind':'search_snippets','coverage':'partial','personal_experience_evidence':False,
                'limitations':['搜索摘要仅作公共事实来源线索；未抓取或核对原文，需按内容重要性继续核验。']}


def _authorize(ctx,conn):
    """Check task-specific search permission in the transaction claiming send."""
    run=conn.execute('SELECT kind,target_ref FROM runs WHERE id=?',(ctx.run_id,)).fetchone()
    purpose='planning' if run['kind']=='planning' else 'production'
    grants=conn.execute('SELECT * FROM authorization_grants WHERE work_id=? AND purpose=? AND revoked_at IS NULL',(ctx.work_id,purpose)).fetchall()
    for grant in grants:
        if IDENTITY not in json.loads(grant['services_json']):continue
        if purpose=='production':
            if grant['plan_revision']!=ctx.plan_revision:continue
            plan=conn.execute('SELECT confirmed_at FROM plan_revisions WHERE work_id=? AND revision=?',(ctx.work_id,ctx.plan_revision)).fetchone()
            if not plan or not plan[0]:continue
        elif grant['target_ref'] and grant['target_ref'] not in {ctx.task_id,ctx.run_id,run['target_ref'],ctx.input_fingerprint}:
            continue
        return
    raise ModelTaskError('permission_missing','本次任务尚未授权公共事实检索服务 Brave / web-search / search')


def public_fact_tools(settings,ctx,*,outputs,transport=None):
    """Tools for one runtime task; service identity cannot be model-supplied."""
    if settings.get('EASEL_PUBLIC_FACTS_PROVIDER','').strip()!='brave':return ()
    provider=BravePublicFacts(settings.get('BRAVE_SEARCH_API_KEY',''),transport=transport)
    outputs=Path(outputs)

    async def execute(args,creative_context):
        if (creative_context.work_id,creative_context.run_id,creative_context.task_id)!=(ctx.work_id,ctx.run_id,ctx.task_id):
            raise ModelTaskError('permission_missing','事实检索不属于当前创作任务')
        ctx.assert_current()
        query_hash=fingerprint(args.model_dump())
        artifact_id='facts_'+fingerprint([ctx.task_id,query_hash])[:32]
        with ctx.store.connection() as conn:
            existing=conn.execute('SELECT * FROM artifacts WHERE id=? AND work_id=? AND deleted_at IS NULL',(artifact_id,ctx.work_id)).fetchone()
        if existing:
            path=MaterialFileStore(outputs).resolve_asset_locator(existing['storage_ref'])
            if digest_file(path)!=existing['digest']:raise ModelTaskError('fact_evidence_changed','已保存事实证据发生变化')
            result=json.loads(path.read_text(encoding='utf8'))
            return {'evidence_id':artifact_id,**result}
        import hashlib,tempfile
        receipt_root=outputs/'_production'/'fact_receipts'
        receipt_root.mkdir(parents=True,exist_ok=True)
        receipts=MaterialFileStore(receipt_root)
        receipt=receipt_root/(artifact_id+'.json')
        if receipt.exists():
            receipt=receipts.resolve_asset_locator(receipt.name)
            if receipt.stat().st_size>1024*1024:raise ModelTaskError('fact_evidence_changed','事实检索回执长度异常')
            result=json.loads(receipt.read_text(encoding='utf8'))
            if result.get('query')!=args.query or result.get('schema_version')!=1:
                raise ModelTaskError('fact_evidence_changed','事实检索回执与当前查询不匹配')
        else:
            provider.validate(args)
            # A charged search can also lose its response. Claim the intent
            # before HTTP; absent receipts never justify automatic resending.
            with ctx.transaction() as conn:
                _authorize(ctx,conn)
                payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
                searches=payload.setdefault('public_fact_requests',{})
                if query_hash in searches:
                    raise ModelTaskError('public_fact_result_unknown','事实检索已提交但没有可核实回执，不会自动重复请求')
                searches[query_hash]={'state':'sending','evidence_id':artifact_id}
                conn.execute('UPDATE tasks SET payload_json=?,updated_at=? WHERE id=?',(canonical_json(payload),utc_now(),ctx.task_id))
            result=await asyncio.to_thread(provider.search,args)
            encoded=canonical_json(result).encode()
            with tempfile.TemporaryDirectory(prefix='fact-receipt-') as directory:
                path=Path(directory)/'receipt.json';path.write_bytes(encoded)
                receipts.stage_object(path,receipt.name,hashlib.sha256(encoded).hexdigest(),len(encoded))
        encoded=canonical_json(result).encode()
        digest=hashlib.sha256(encoded).hexdigest()
        locator=f'works/{ctx.work_id}/evidence/public-facts/{digest}.json'
        MaterialFileStore(outputs).stage_object(receipt,locator,digest,len(encoded))
        with ctx.transaction() as conn:
            path=MaterialFileStore(outputs).resolve_asset_locator(locator)
            if digest_file(path)!=digest:raise ModelTaskError('fact_evidence_changed','事实证据文件发生变化')
            conn.execute('''INSERT OR IGNORE INTO artifacts(id,work_id,run_id,kind,storage_ref,digest,size_bytes,media_type,displayable,metadata_json,created_at)
                VALUES(?,?,?,'public_fact_evidence',?,?,?,'application/json',0,?,?)''',
                (artifact_id,ctx.work_id,ctx.run_id,locator,digest,len(encoded),canonical_json({'schema_version':1,'query_hash':query_hash,'provider':'brave','source_count':len(result['sources'])}),utc_now()))
            payload=json.loads(conn.execute('SELECT payload_json FROM tasks WHERE id=?',(ctx.task_id,)).fetchone()[0])
            payload.setdefault('public_fact_requests',{})[query_hash]={'state':'succeeded','evidence_id':artifact_id}
            conn.execute('UPDATE tasks SET payload_json=?,updated_at=? WHERE id=?',(canonical_json(payload),utc_now(),ctx.task_id))
            ctx.store.append_event(conn,ctx.work_id,'public_facts_retrieved',{'evidence_id':artifact_id,'source_count':len(result['sources']),'coverage':'partial'},run_id=ctx.run_id)
        return {'evidence_id':artifact_id,**result}

    return (ScopedTool('search_public_facts','检索可引用的公共事实来源摘要。仅返回有日期的公开网页线索，不能证明个人经历或替代原文核验。',PublicFactQuery,execute),)
