import asyncio
from dataclasses import replace
import json
import httpx
import pytest
from easel.production.context import TaskContext as CreativeContext
from easel.production.contracts import canonical_json
from easel.production.model_tasks import ModelTaskError
from easel.production.public_facts import public_fact_tools,public_fact_capabilities,IDENTITY
from .test_supply_tasks import env

SETTINGS={'EASEL_PUBLIC_FACTS_PROVIDER':'brave','BRAVE_SEARCH_API_KEY':'test-secret'}


def configured(env,responder):
    service,ops,ctx,spec,_=env
    tools=public_fact_tools(SETTINGS,ctx,outputs=service.outputs,transport=httpx.MockTransport(responder))
    creative=CreativeContext(ctx.work_id,ctx.run_id,ctx.task_id)
    return tools[0],creative


def grant(env):
    with env[2].store.transaction() as conn:conn.execute('UPDATE authorization_grants SET services_json=? WHERE id=?',(canonical_json([IDENTITY]),env[3]['grant_id']))


def test_unconfigured_or_unauthorized_search_never_sends(env):
    assert public_fact_tools({},env[2],outputs=env[0].outputs)==()
    assert not public_fact_capabilities({})[0]['available']
    tool,ctx=configured(env,lambda request:pytest.fail('unauthorized HTTP'))
    with pytest.raises(ModelTaskError,match='尚未授权'):asyncio.run(tool.invoke({'query':'public fact'},ctx))


def test_dated_source_evidence_is_saved_scoped_and_reused(env):
    grant(env);calls=[]
    def respond(request):
        calls.append(request)
        assert request.url.host=='api.search.brave.com' and request.headers['X-Subscription-Token']=='test-secret'
        return httpx.Response(200,json={'web':{'results':[{'title':'<b>Public fact</b>','url':'https://example.org/article','description':'A factual source snippet','page_age':'2026-10-01'}]}})
    tool,ctx=configured(env,respond)
    first=asyncio.run(tool.invoke({'query':'public fact'},ctx))
    second=asyncio.run(tool.invoke({'query':'public fact'},ctx))
    assert first==second and len(calls)==1
    assert first['sources'][0]['observed_at'] and first['sources'][0]['published_at']=='2026-10-01'
    assert first['coverage']=='partial' and first['personal_experience_evidence'] is False
    assert 'test-secret' not in canonical_json(first)
    with env[2].store.connection() as conn:
        artifact=conn.execute('SELECT * FROM artifacts WHERE id=?',(first['evidence_id'],)).fetchone()
        assert artifact['displayable']==0 and artifact['kind']=='public_fact_evidence'
    with pytest.raises(ModelTaskError,match='不属于'):asyncio.run(tool.invoke({'query':'other fact'},replace(ctx,work_id='other')))


def test_provider_redirect_error_and_bad_urls_do_not_fetch_arbitrary_pages(env):
    grant(env);calls=[]
    def respond(request):
        calls.append(request)
        return httpx.Response(200,json={'web':{'results':[{'url':'http://example.org/a'},{'url':'https://127.0.0.1/x'},
          {'url':'https://example.org/a?token=private'},{'url':'https://user:pw@example.org/a'},{'url':'https://safe.example/a'}]}})
    tool,ctx=configured(env,respond)
    value=asyncio.run(tool.invoke({'query':'facts'},ctx))
    assert len(calls)==1 and [s['source_url'] for s in value['sources']]==['https://safe.example/a']
    other,_=configured(env,lambda request:httpx.Response(302,headers={'location':'http://127.0.0.1/secret'}))
    with pytest.raises(ModelTaskError):asyncio.run(other.invoke({'query':'different query'},ctx))


def test_revoked_grant_and_secret_query_block_before_send(env):
    grant(env)
    tool,ctx=configured(env,lambda request:pytest.fail('should not send'))
    with pytest.raises(ModelTaskError,match='凭证'):asyncio.run(tool.invoke({'query':'api_key=supersecret'},ctx))
    with env[2].store.transaction() as conn:conn.execute("UPDATE authorization_grants SET revoked_at='revoked' WHERE id=?",(env[3]['grant_id'],))
    with pytest.raises(ModelTaskError,match='尚未授权'):asyncio.run(tool.invoke({'query':'public facts'},ctx))


def test_lost_search_receipt_does_not_repeat_a_potentially_charged_query(env):
    grant(env);calls=[]
    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout('remote response lost')
    tool,ctx=configured(env,timeout)
    with pytest.raises(ModelTaskError,match='不可用'):asyncio.run(tool.invoke({'query':'public fact'},ctx))
    with pytest.raises(ModelTaskError,match='不会自动重复'):asyncio.run(tool.invoke({'query':'public fact'},ctx))
    assert len(calls)==1
