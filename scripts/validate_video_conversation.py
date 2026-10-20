#!/usr/bin/env python3
"""A2–A4 real Web/native-plugin integration on loopback fakes and a new temp DB.

Never imports production configuration, starts a production Worker, or installs
anything into the user's OpenClaw. --serve keeps ONLY this isolated fixture alive.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from easel.openclaw_cmd import openclaw_base_cmd
from easel.production.service import WorkService
from easel.production.store import Store
from easel.conversation import ConversationService
from easel.conversation_bridge import require_persistent_gateway
from easel.video_workspace import prepare_workspace
from web.conversation_api import VideoChat, create_router, create_internal_router
from web.production_api import create_router as production_router,production_error_handler
from web.production_settings_api import create_settings_router
from easel.production.errors import ProductionError
from validate_openclaw_work_bridge import FakeModel,free_port,wait_for,isolated_environment


@contextmanager
def fixture(root, *, configure=None, resume=False, memory_plugin=False):
    root=root.resolve()
    if not any(p in root.parents for p in [Path(tempfile.gettempdir()).resolve(),Path('/tmp').resolve()]):raise ValueError('Temporary root required')
    marker=root/'isolated-fixture.json'
    if resume and (not marker.is_file() or marker.read_text()!='easel-isolated-v1' or root.is_symlink()):raise ValueError('Only an existing isolated fixture can resume')
    previous=json.loads((root/'openclaw.json').read_text()) if resume else None
    root.mkdir(exist_ok=resume);marker.write_text('easel-isolated-v1')
    for folder in ('tmp','home','state','profiles','workspace-main'):(root/folder).mkdir(exist_ok=resume)
    repo=Path(__file__).resolve().parents[1];node,entry=openclaw_base_cmd();base=[node,entry]
    plugin=root/('plugin-'+uuid.uuid4().hex if resume else 'plugin');shutil.copytree(repo/'agents/plugins/easel-work',plugin)
    (root/'node_modules').mkdir(exist_ok=resume)
    if not resume:(root/'node_modules/openclaw').symlink_to(Path(entry).parent,target_is_directory=True)
    workspace=prepare_workspace(repo,root/('workspace-video-'+uuid.uuid4().hex if resume else 'workspace-video'))
    (root/'workspace-main/AGENTS.md').write_text('MAIN_ONLY_FORBIDDEN_SENTINEL')
    (root/'AGENTS.md').write_text('DEV_ONLY_FORBIDDEN_SENTINEL')
    for profile in ('one','two'):
        folder=root/'profiles'/profile;folder.mkdir(exist_ok=resume)
        for dimension in ('identity','style','audience','platforms','preferences','memory'):
            path=folder/(dimension+'.md')
            if not path.exists():path.write_text('PROFILE_'+profile+'_'+dimension+'_SENTINEL\n克制、忠于真实经历\n')
    web_port,gateway_port=free_port(),free_port();token,gateway_token=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    if previous:
        from urllib.parse import urlsplit
        gateway_port=previous['gateway']['port'];web_port=urlsplit(previous['plugins']['entries']['easel-work']['config']['baseUrl']).port
    guard=root/'guard.mjs'
    guard.write_text('''import net from 'node:net';import dns from 'node:dns';import fs from 'node:fs';
const allowed=new Set(PORTS); const original=net.Socket.prototype.connect;const lookup=dns.lookup;
dns.lookup=function(host,...args){if(['127.0.0.1','localhost','::1'].includes(host))return lookup.call(this,host,...args);fs.appendFileSync(LOG,'dns denied\\n');throw Error('offline DNS');};
net.Socket.prototype.connect=function(...args){const a=Array.isArray(args[0])?args[0]:args;const o=typeof a[0]==='object'?a[0]:{port:a[0],host:typeof a[1]==='string'?a[1]:'localhost'};
if(!allowed.has(Number(o.port))||!['127.0.0.1','localhost','::1'].includes(o.host??'localhost')){fs.appendFileSync(LOG,'network denied\\n');throw Error('offline network');}return original.apply(this,args);};
'''.replace('PORTS',json.dumps([web_port,gateway_port])).replace('LOG',json.dumps(str(root/'denials.log'))))
    config={'gateway':{'mode':'local','bind':'loopback','port':gateway_port,'auth':{'mode':'token','token':gateway_token},'http':{'endpoints':{'chatCompletions':{'enabled':True}}}},
        'logging':{'level':'info','file':str(root/'gateway.jsonl'),'consoleStyle':'json'},
        'agents':{'defaults':{'model':{'primary':'a1fake/a1-fake'},'models':{'a1fake/a1-fake':{}},'timeoutSeconds':40,'heartbeat':{'every':'0m'}},'entries':{'main':{'default':True,'workspace':str(root/'workspace-main'),'tools':{'allow':['session_status']}},'easel-video':{k:v for k,v in workspace.items() if k in {'workspace','skills','tools'}}}},
        'models':{'mode':'replace','providers':{'a1fake':{'baseUrl':f'http://127.0.0.1:{web_port}/v1','apiKey':'offline-no-payment','api':'openai-completions','models':[{'id':'a1-fake','name':'offline','reasoning':False,'input':['text'],'cost':{'input':0,'output':0,'cacheRead':0,'cacheWrite':0},'contextWindow':65536,'maxTokens':2048}]}}},
        'skills':{'allowBundled':[]},'cron':{'enabled':False},'update':{'checkOnStart':False,'auto':{'enabled':False}},'telemetry':{'enabled':False},
        'plugins':{'allow':['easel-work'],'load':{'paths':[str(plugin)]},'slots':{'memory':'none'},'entries':{'easel-work':{'enabled':True,'hooks':{'allowConversationAccess':True},'config':{'baseUrl':f'http://127.0.0.1:{web_port}','token':token,'protocolVersion':2}}}}}
    if memory_plugin:
        config['plugins']['allow'].append('memory-core')
        config['plugins']['slots']['memory']='memory-core'
    config_path=root/'openclaw.json';config_path.write_text(json.dumps(config));config_path.chmod(0o600)
    (root/'.env').write_text(f'EASEL_DIRECT_API_BASE_URL=http://127.0.0.1:{web_port}/v1\nEASEL_DIRECT_API_MODEL=a1-fake\n')
    store=Store(root/'outputs/_production/db.sqlite3');store.initialize();service=WorkService(store,outputs=root/'outputs',profiles=root/'profiles')
    # Reuse actual Web chat/replay functions, replacing only providers and test paths in THIS child process.
    import web.app as web
    web.OUTPUTS_DIR=service.outputs;web.PROFILES_DIR=service.profiles;web.SESSIONS_DIR=root/'sessions'
    web._production_service=lambda:service
    web.app.state.production_service=service
    os.environ['EASEL_WORK_BRIDGE_TOKEN']=token
    web._LOCAL_ORIGINS.append(f'http://127.0.0.1:{web_port}')
    chat=VideoChat(lambda:service,web._job_event_file,web._save_turn,gateway_url=f'http://127.0.0.1:{gateway_port}',gateway_token=gateway_token)
    web._video_chat=chat
    app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler)
    app.middleware('http')(web.local_write_guard)
    app.include_router(create_router(lambda:service));app.include_router(create_internal_router(lambda:service,lambda:token));app.include_router(production_router(lambda:service));app.include_router(create_settings_router(lambda:service,settings_provider=lambda:{}))
    app.add_api_route('/api/chat/stream',web.api_chat_stream,methods=['POST']);app.add_api_route('/api/chat/jobs/{turn_id}/stream',web.api_chat_job_stream,methods=['GET']);app.add_api_route('/api/chat/stop',web.api_chat_stop,methods=['POST']);app.add_api_route('/api/chat/last/{session_id}',web.api_chat_last,methods=['GET'])
    app.add_api_route('/api/upload',web.api_upload,methods=['POST'])
    app.add_api_route('/api/upload/local',web.api_upload_local,methods=['POST'])
    app.add_api_route('/api/outputs',web.api_outputs,methods=['GET'])
    app.add_api_route('/api/skills',web.api_skills,methods=['GET'])
    model=FakeModel()
    def channel_case(body):
        content=next(m['content'] for m in reversed(body['messages']) if m['role']=='user')
        refs=re.findall(r'"ref":"([^"]+)"',content)
        return 'easel_work_propose',{'kind':'channel_create','values':{'name':'创业笔记','creative_basis':{'position':'克制地分享真实创业经历','themes':'创业与产品','audience':'创业者'}},'source_refs':[refs[-1]]}
    model.extra_cases={'channel':channel_case}
    app.add_api_route('/v1/chat/completions',model.complete,methods=['POST'])
    @app.get('/api/status')
    def status():return {'personas':[{'name':'one'},{'name':'two'}],'gateway':True,'transport':'openclaw','runtime':'openclaw'}
    @app.get('/api/settings/bootstrap')
    def bootstrap():return {'modelConfigured':True}
    @app.get('/api/upload/limits')
    def limits():return {'max_mb':50}
    extension=configure(app,service,model,web) if configure else {}
    app.mount('/static',StaticFiles(directory=repo/'web/static'),name='static')
    app.mount('/',StaticFiles(directory=repo/'web/frontend/dist',html=True),name='frontend')
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=web_port,log_level='error'));thread=threading.Thread(target=server.run,daemon=True);thread.start();wait_for(lambda:server.started)
    env=isolated_environment(root,node,config_path,guard);log=(root/'gateway-console.log').open('w')
    gateway=subprocess.Popen(base+['gateway','run','--port',str(gateway_port)],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    try:
        def ready():
            try:require_persistent_gateway(f'http://127.0.0.1:{gateway_port}',gateway_token);return True
            except (ProductionError,httpx.HTTPError):return False
        wait_for(ready,60)
        yield {'root':root,'url':f'http://127.0.0.1:{web_port}','service':service,'model':model,'bridge_token':token,'gateway':gateway,'node':node,'entry':entry,'env':env,**extension}
    finally:
        gateway.terminate()
        try:gateway.wait(timeout=12)
        except subprocess.TimeoutExpired:gateway.kill();gateway.wait(timeout=5)
        log.close();server.should_exit=True;thread.join(timeout=5)


def probe(f):
    client=httpx.Client(base_url=f['url'],timeout=90,trust_env=False)
    service=f['service'];c=ConversationService(service);checks=[]
    def check(name,condition):
        checks.append({'name':name,'pass':bool(condition)})
        if not condition:raise AssertionError(name)
    def enter(session,entry):
        response=client.post(f'/api/chat/video/{session}/enter',json={'command_id':uuid.uuid4().hex,'entry':entry});response.raise_for_status();return response.json()['segment_id']
    def chat(session,segment,case):
        turn=uuid.uuid4().hex;body={'sessionId':session,'turnId':turn,'videoSegmentId':segment,'message':'A1_CASE='+case,'interaction_mode':'video'}
        response=client.post('/api/chat/stream',json=body);response.raise_for_status()
        assert 'event: done' in response.text,response.text
        with service.store.connection() as conn:
            value=conn.execute('SELECT state FROM conversation_turns WHERE id=?',(turn,)).fetchone()[0]
        wait_for(lambda:c.view(session)['turns'][-1]['state']=='ended',10)
        return turn,body,response.text
    from easel.production.catalog import CreativeCatalog
    from easel.production.service import now, encode
    channel=CreativeCatalog(service).command('channels','create',{'name':'Isolated selected channel','profile_ref':'one','settings':{'schema_version':1}},command_id='fixture-channel')['id']
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('fixture-director','Isolated director',?,?)",(now(),now()))
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,created_at) VALUES ('fixture-version','fixture-director',1,?,?,1,?)",(encode({'schema_version':1,'visual_style':'清晰','storytelling':'朋友'}),encode([{'source':'fixture'}]),now()))
    sid=enter('probe',{'profile_ref':'one','channel_id':channel,'director_revision':'fixture-version','director_trial':True})
    chat('probe',sid,'discuss');chat('probe',sid,'discuss')
    check('web_discussion_no_work_or_run',service.list_works()['items']==[])
    _,body,_=chat('probe',sid,'create');view=c.view('probe');p=view['proposals'][-1]
    check('native_draft_tool_returns_persistent_card_without_side_effect',p['kind']=='draft' and service.list_works()['items']==[])
    action={'command_id':'apply-draft','hash':p['body_hash']}
    result=client.post(f"/api/chat/video/probe/proposals/{p['id']}/apply",json=action);result.raise_for_status();work=result.json()['work_id']
    check('card_replay_one_work',client.post(f"/api/chat/video/probe/proposals/{p['id']}/apply",json=action).json()==result.json() and len(service.list_works()['items'])==1)
    before=len(f['model'].requests);duplicate=client.post('/api/chat/stream',json=body)
    check('duplicate_chat_post_replays_without_model',duplicate.status_code==200 and len(f['model'].requests)==before)
    chat('probe',sid,'plan');view=c.view('probe');plans=[p for p in view['proposals'] if p['kind']=='plan']
    check('different_tool_call_ids_one_plan_proposal',len(plans)==1 and service.snapshot(work)['runs']==[])
    p=plans[0];response=client.post(f"/api/chat/video/probe/proposals/{p['id']}/apply",json={'command_id':'plan','hash':p['body_hash']});response.raise_for_status()
    check('explicit_plan_card_uses_existing_work_service',len(service.snapshot(work)['runs'])==1)
    for case in ('attack_exec','attack_read','attack_sessions_spawn','attack_voice','attack_memory_search','attack_old_pipeline','attack_video','forge'):chat('probe',sid,case)
    check('forbidden_tools_no_new_production',len(service.snapshot(work)['runs'])==1)
    with service.store.connection() as conn:
        grants=conn.execute('SELECT purpose,services_json FROM authorization_grants').fetchall()
        check('planning_confirmation_binds_fake_service_without_paid_operations',conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0 and len(grants)==1 and grants[0]['purpose']=='planning' and json.loads(grants[0]['services_json'])==[{'provider':'direct-api','model':'a1-fake','mode':'structured'}])
    # Exercise the new adapter through the actual native tool lifecycle, with
    # only fake model responses and an isolated catalog (no paid service).
    pipe_sid=enter('pipeline-probe',{'profile_ref':'one','kind':'channel_create'})
    f['model'].extra_cases={
        'pipeline_pending':('easel_pipeline',{'mode':'pending'}),
        'pipeline_offer':lambda body:('easel_work_propose',{'kind':'channel_create','values':{'name':'Isolated conversational channel'},'source_refs':[next(r['id'] for r in reversed(c.view('pipeline-probe')['turns']) if r['state']=='active')]}),
    }
    chat('pipeline-probe',pipe_sid,'pipeline_pending')
    chat('pipeline-probe',pipe_sid,'pipeline_offer')
    proposed=c.view('pipeline-probe')['proposals'][-1]
    f['model'].extra_cases['pipeline_answer']=('easel_pipeline',{'mode':'answer','proposal_id':proposed['id'],'hash':proposed['body_hash'],'user_quote':'A1_CASE=pipeline_answer'})
    chat('pipeline-probe',pipe_sid,'pipeline_answer')
    check('native_text_answer_saves_channel_without_button',bool(c.view('pipeline-probe')['context'].get('channel_id')))
    check('channel_pipeline_does_not_create_video',len(service.list_works()['items'])==1)
    # Reproduce the real paused planning path with a minimal model-generated
    # grant request. Only this temporary database is changed; no Worker runs.
    with service.store.transaction() as conn:
        task=dict(conn.execute("SELECT * FROM tasks WHERE work_id=? AND kind='plan'",(work,)).fetchone())
        conn.execute("UPDATE authorization_grants SET revoked_at='fixture-revoked' WHERE work_id=?",(work,))
        conn.execute("UPDATE tasks SET state='needs_decision',error_json=? WHERE id=?",(json.dumps({'code':'permission_missing'}),task['id']))
        conn.execute("UPDATE runs SET state='needs_decision' WHERE id=?",(task['run_id'],))
        conn.execute("UPDATE works SET state='needs_decision' WHERE id=?",(work,))
    f['model'].extra_cases['grant_recovery_offer']=('easel_pipeline',{'mode':'offer','action':'grant','values':{'purpose':'planning'}})
    chat('probe',sid,'grant_recovery_offer')
    recovery=c.view('probe')['proposals'][-1]
    payload=recovery['body']['values']['payload']
    check('native_minimal_grant_binds_service_and_original_task',payload['services']==[{'provider':'direct-api','model':'a1-fake','mode':'structured'}] and payload['decision_id']==task['id'])
    f['model'].extra_cases['grant_recovery_answer']=('easel_pipeline',{'mode':'answer','proposal_id':recovery['id'],'hash':recovery['body_hash'],'user_quote':'A1_CASE=grant_recovery_answer'})
    chat('probe',sid,'grant_recovery_answer');chat('probe',sid,'grant_recovery_answer')
    with service.store.connection() as conn:
        check('native_grant_answer_resumes_once_without_new_run',conn.execute('SELECT count(*) FROM runs WHERE work_id=?',(work,)).fetchone()[0]==1 and conn.execute('SELECT state FROM tasks WHERE id=?',(task['id'],)).fetchone()[0]=='pending' and conn.execute('SELECT count(*) FROM authorization_grants WHERE work_id=? AND revoked_at IS NULL',(work,)).fetchone()[0]==1)
        check('native_authorization_recovery_does_not_call_production_model',conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0)
    pipeline_schema=next(t['function']['parameters'] for t in f['model'].requests[-1]['tools'] if t['function']['name']=='easel_pipeline')
    check('native_model_sees_exact_grant_array_schema',pipeline_schema['properties']['values']['properties']['services']['type']=='array' and pipeline_schema['properties']['values']['properties']['services']['items']['additionalProperties'] is False)
    # Exercise UNKNOWN recovery through the real plugin/Web dialogue, using a
    # local HTTP mock for the planning worker. No remote provider is reachable.
    from easel.production.configuration import model_configuration
    from easel.production.model_tasks import HTTPModelTransport
    from easel.production.operations import OperationService
    from easel.production.planning import PlanningTasks
    from easel.production.worker import Worker
    from easel.conversation_pipeline import call_status
    settings,model,version=model_configuration(service.outputs.parent)
    model_calls=[]
    def fake_timeout(request):
        model_calls.append(1)
        raise httpx.ReadTimeout('isolated timeout')
    transport=HTTPModelTransport(settings,transport=httpx.MockTransport(fake_timeout))
    planner=PlanningTasks(service,OperationService(service.store),transport,model,version)
    asyncio.run(Worker(service.store,{'plan':planner.plan}).run_once())
    recovery_sid=enter('recovery-probe',{'profile_ref':'one','work_id':work,'kind':'continue'})
    with service.store.connection() as conn:
        segment=c.segment(conn,'recovery-probe')
        recovery=call_status(c,conn,segment)
        old_operation=dict(conn.execute('SELECT * FROM operations WHERE work_id=?',(work,)).fetchone())
    check('native_recovery_reads_real_timeout_diagnostic',recovery['diagnostics'][0]['timeout_type']=='read' and recovery['recovery']['can_offer'])
    check('native_schema_includes_bounded_unknown_recovery','replan_after_unknown' in pipeline_schema['properties']['action']['enum'])
    f['model'].extra_cases['unknown_recovery_offer']=('easel_pipeline',recovery['recovery']['next_action'])
    chat('recovery-probe',recovery_sid,'unknown_recovery_offer')
    new_proposal=c.view('recovery-probe')['proposals'][-1]
    check('native_unknown_offer_exposes_duplicate_charge_scope','可能重复计费' in new_proposal['body']['values']['summary'] and len(service.snapshot(work)['runs'])==1)
    f['model'].extra_cases['unknown_recovery_answer']=('easel_pipeline',{'mode':'answer','proposal_id':new_proposal['id'],'hash':new_proposal['body_hash'],'user_quote':'A1_CASE=unknown_recovery_answer'})
    chat('recovery-probe',recovery_sid,'unknown_recovery_answer');chat('recovery-probe',recovery_sid,'unknown_recovery_answer')
    with service.store.connection() as conn:
        check('native_unknown_ledger_preserved',dict(conn.execute('SELECT * FROM operations WHERE id=?',(old_operation['id'],)).fetchone())==old_operation)
        check('native_explicit_replan_enqueues_once',conn.execute('SELECT count(*) FROM runs WHERE work_id=?',(work,)).fetchone()[0]==2 and conn.execute("SELECT count(*) FROM tasks WHERE work_id=? AND state='pending'",(work,)).fetchone()[0]==1)
    check('native_no_automatic_provider_resend',len(model_calls)==1)
    # Native length termination: no live provider, no automatic continuation.
    f['model'].final_texts={'length_probe':''}
    f['model'].finish_reasons={'length_probe':'length'}
    length_sid=enter('length-probe',{'profile_ref':'one'})
    length_turn=uuid.uuid4().hex;before=len(f['model'].requests)
    response=client.post('/api/chat/stream',json={'sessionId':'length-probe','turnId':length_turn,
        'videoSegmentId':length_sid,'message':'A1_CASE=length_probe','interaction_mode':'video'})
    response.raise_for_status()
    wait_for(lambda:c.view('length-probe')['turns'][-1]['state']=='ended',10)
    with service.store.connection() as conn:
        diagnostic=json.loads(conn.execute('SELECT payload_json FROM conversation_turns WHERE id=?',(length_turn,)).fetchone()[0]).get('model_diagnostic',{})
    check('native_length_diagnostic_retained',diagnostic.get('stop_reason')=='length' and diagnostic.get('usage_status')=='missing_or_zero')
    check('native_diagnostic_config_not_mislabeled_wire',diagnostic.get('parameter_source')=='configured_not_wire')
    check('native_length_visible_without_retry','长度上限' in response.text and len(f['model'].requests)==before+1)
    chat('length-probe',length_sid,'discuss')
    check('native_length_followup_keeps_same_session_no_production',c.view('length-probe')['work_id'] is None and len(service.snapshot(work)['runs'])==2)
    # A different Work/Profile gets another native transcript, despite sharing the UI session.
    start=len(f['model'].requests);other=enter('probe',{'profile_ref':'two'});chat('probe',other,'context')
    text=json.dumps(f['model'].requests[start:])
    check('cross_profile_native_session_has_no_previous_sentinel',other!=sid and 'PROFILE_two_identity_SENTINEL' in text and 'PROFILE_one_identity_SENTINEL' not in text)
    all_requests=json.dumps(f['model'].requests,ensure_ascii=False)
    check('no_development_main_or_service_credentials',all(x not in all_requests for x in ('MAIN_ONLY_FORBIDDEN_SENTINEL','DEV_ONLY_FORBIDDEN_SENTINEL',f['bridge_token'])))
    from easel.conversation_bridge import TOOLS
    check('effective_native_tool_surface_matches_contract',all({t['function']['name'] for t in b.get('tools',[])}==set(TOOLS) for b in f['model'].requests))
    check('selected_product_personality_loaded','创作者的社媒内容搭子' in all_requests)
    old=client.post('/api/chat/stream',json={**body,'turnId':'late-old-segment'});check('old_segment_dispatch_rejected',old.status_code==409)
    deleted=client.delete('/api/chat/video/probe');check('delete_chat_preserves_work_and_run',deleted.status_code==200 and len(service.snapshot(work)['runs'])==2)
    check('bridge_credential_cannot_call_authority_api',client.post('/api/production/works',json={'command_id':'forbidden','payload':{'title':'no'}},headers={'Authorization':'Bearer '+f['bridge_token']}).status_code==403)
    check('all_network_loopback_only',not (f['root']/'denials.log').exists())
    return {'status':'PASS','checks':checks,'fake_model_requests':len(f['model'].requests),'paid_requests':0,'production_environment_changed':False,'production_worker_started':False,'work_count':1,'planning_runs':2,'isolated_mock_model_requests':1,'openclaw_version':subprocess.run([f['node'],f['entry'],'--version'],capture_output=True,text=True,timeout=15,env=f['env'],cwd=f['root']).stdout.strip()}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--serve',action='store_true');parser.add_argument('--memory-plugin',action='store_true');args=parser.parse_args()
    result={}
    try:
        with fixture(args.root,memory_plugin=args.memory_plugin) as f:
            if args.serve:
                print(json.dumps({'url':f['url'],'root':str(args.root)}),flush=True)
                while True:time.sleep(1)
            result=probe(f)
    finally:
        if result:
            result['child_gateway_stopped']=True;(args.root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
