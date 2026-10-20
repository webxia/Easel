#!/usr/bin/env python3
"""Fallback result continuation after direct API applies; zero paid calls.

Current native execution waiting is checked by validate_conversation_execution_wait.
"""
import argparse
import asyncio
import json
import hashlib
import subprocess
import time
from pathlib import Path
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_video_conversation import fixture
from validate_openclaw_work_bridge import wait_for
import httpx
from easel.conversation import ConversationService
from easel.production.catalog import CreativeCatalog
from easel.production.service import now, encode
from easel.production.worker import Worker, TaskResult
from easel.production.planning import PlanningTasks
from easel.production.operations import OperationService
from easel.production.model_tasks import ModelTaskError
from easel.production.errors import ProductionError


def configure(app,service,model,web):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def lifespan(_app):
        task=asyncio.create_task(web._video_chat.results_forever())
        try:yield
        finally:
            task.cancel()
            await asyncio.gather(task,return_exceptions=True)
    app.router.lifespan_context=lifespan
    from fastapi.responses import HTMLResponse
    @app.get('/')
    def proof():
        view=ConversationService(service).view('plan-success')
        sessions=[{'id':'plan-success','title':'任务结果原生接续验证','persona':'one','created':1,'messages':[],'videoSegmentId':view['segment_id']}]
        seed='<script>if(!localStorage.getItem("result_proof_seeded")){localStorage.setItem("easel_sessions",'+json.dumps(json.dumps(sessions,ensure_ascii=False))+');localStorage.setItem("easel_active_session","plan-success");localStorage.setItem("result_proof_seeded","yes");}</script>'
        html=(Path(__file__).resolve().parents[1]/'web/frontend/dist/index.html').read_text()
        return HTMLResponse(html.replace('<head>','<head>'+seed))
    @app.post('/__fixture/deliver-result')
    async def deliver():
        started=await web._video_chat.process_results_once()
        pending=list(web._video_chat.tasks.values())
        if pending:await asyncio.gather(*pending)
        return {'started':started}
    return {}


def probe(f):
    s=f['service'];c=ConversationService(s);checks=[];client=httpx.Client(base_url=f['url'],timeout=90,trust_env=False)
    def check(name,value):
        checks.append({'name':name,'pass':bool(value)})
        assert value,name
    channel=CreativeCatalog(s).command('channels','create',{'name':'隔离频道','profile_ref':'one','settings':{'schema_version':1}},command_id='channel')
    with s.store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('director','隔离导演',?,?)",(now(),now()))
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,created_at) VALUES ('v1','director',1,?,?,1,?)",(encode({'schema_version':1,'visual_style':'清晰','storytelling':'朋友'}),encode([{'source':'fixture'}]),now()))
    current={};native_event_requests=[]
    def result_tool(body):
        native_event_requests.append(body)
        snap=s.snapshot(current['work'])
        p=next((p for p in snap['plans'] if p['revision']==snap['current_plan_revision']),None)
        if p and not p['confirmed_at'] and snap['runs'][-1]['state']=='succeeded':
            return 'easel_pipeline',{'mode':'offer','action':'confirm','values':{'plan_revision':p['revision'],'plan_hash':p['plan_hash'],'services':[],'allow_ai':False,'image_limit':0,'video_limit':0},'summary':'完整方案已呈现，是否确认制作？'}
        return 'easel_pipeline',{'mode':'pending'}
    def result_text(body):
        snap=s.snapshot(current['work'])
        if current.get('failure'):
            return '这次模型请求超时，未取得完整方案。当前同步模型接口没有结果查询能力，我不会自动重发。你希望先核对服务还是停止本次尝试？'
        if snap['state']=='reviewable':
            output=next(a for a in snap['artifacts'] if a['kind']=='output')
            return f'视频已完成并可审阅。<video controls src="/api/production/artifacts/{output["id"]}/content"></video>\n请观看后告诉我需要修改的具体位置。'
        if current.get('edit_failure'):return '剪辑阶段失败，已有方案保留。请先确认素材问题，再决定是否恢复原任务。'
        return '方案摘要：技术服务人。\n\n### 完整逐字脚本\n技术服务人。\n\n### 分镜\n科技画面。\n\n此方案尚未制作，是否确认按展示的服务与额度制作？'
    f['model'].extra_cases={'task_result':result_tool}
    f['model'].final_texts={'task_result':result_text}
    def chat(session,seg,case):
        t=uuid.uuid4().hex
        r=client.post('/api/chat/stream',json={'sessionId':session,'turnId':t,'videoSegmentId':seg,'message':'A1_CASE='+case,'interaction_mode':'video'});r.raise_for_status()
        assert 'event: done' in r.text,r.text
        wait_for(lambda:c.view(session)['turns'][-1]['state']=='ended',10)
    def apply_last(session):
        p=c.view(session)['proposals'][-1]
        r=client.post(f"/api/chat/video/{session}/proposals/{p['id']}/apply",json={'command_id':uuid.uuid4().hex,'hash':p['body_hash']});r.raise_for_status();return r.json()
    def start(session):
        seg=c.enter(session,{'profile_ref':'one','channel_id':channel['id'],'director_revision':'v1','director_trial':True},'enter-'+session)['segment_id']
        chat(session,seg,'create');current.clear();current['work']=apply_last(session)['work_id']
        chat(session,seg,'plan');apply_last(session)
        return seg
    def plan_worker(failure=False):
        class Transport:
            capabilities=frozenset({'text','structured','image','tools'})
            async def complete(self,*args):
                if failure:raise ModelTaskError('provider_timeout','模型请求超时；提交结果尚未确定，禁止自动重发')
                return {'content':encode({'title':'隔离方案','summary':'技术服务人','script':'技术服务人。','scenes':[{'id':'s1','purpose':'解释','visual':'科技画面','narration':'技术服务人。','duration_seconds':3,'required_input_ids':[]}],'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}})}
        planning=PlanningTasks(s,OperationService(s.store),Transport(),{'provider':'direct-api','model':'a1-fake','mode':'structured'},'fixture')
        asyncio.run(Worker(s.store,{'plan':planning.plan}).run_once())
    delivered_counts={}
    def deliver(session):
        expected=delivered_counts.get(session,0)+1
        # No test endpoint starts the reply: the real background loop sees the
        # worker's persisted event and invokes the original native assistant.
        wait_for(lambda:len(c.view(session)['result_messages'])>=expected and c.view(session)['result_messages'][-1]['resultState']=='ended',30)
        delivered_counts[session]=expected
        view=c.view(session);result=view['result_messages'][-1]
        check('native_result_has_real_assistant_text_'+session, bool(result['content']) and not result.get('deliveryError'))
        check('same_native_segment_'+session,view['turns'][-1]['id']==result['serverTurnId'])
        check('no_duplicate_dispatch_'+session,client.post('/__fixture/deliver-result').json()['started'] is False)
        check('background_loop_delivered_without_polling_chat_'+session,bool(native_event_requests))
        return result
    seg=start('plan-success');plan_worker();r=deliver('plan-success')
    check('full_script_and_confirmation_in_actual_reply','完整逐字脚本' in r['content'] and '是否确认' in r['content'])
    check('event_creates_proposal_without_production',len(s.snapshot(current['work'])['runs'])==1 and c.view('plan-success')['proposals'][-1]['body']['values']['action']=='confirm')
    p=c.view('plan-success')['proposals'][-1]
    f['model'].extra_cases['start_production']=('easel_pipeline',{'mode':'answer','proposal_id':p['id'],'hash':p['body_hash'],'user_quote':'A1_CASE=start_production'})
    apply_last('plan-success')  # direct API compatibility: no live native turn owns this run.
    check('real_user_reply_continues_original_flow',len(s.snapshot(current['work'])['runs'])==2)
    async def supply(ctx):return TaskResult(next_kind='edit')
    async def edit(ctx):return TaskResult(next_kind='render')
    async def render(ctx):return TaskResult(next_kind='quality')
    async def quality(ctx):
        path=s.outputs/'works'/current['work']/'fixture.mp4';path.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=navy:s=320x180:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
        from tests.production.test_store import insert_artifact
        with ctx.transaction() as conn:
            insert_artifact(conn,current['work'],'output-'+ctx.run_id,storage_ref=path.relative_to(s.outputs).as_posix(),digest=hashlib.sha256(path.read_bytes()).hexdigest(),size_bytes=path.stat().st_size,run_id=ctx.run_id,kind='output',media_type='video/mp4',output_revision=1,quality_state='passed',displayable=1)
        return TaskResult(work_state='reviewable')
    asyncio.run(Worker(s.store,{'supply':supply,'edit':edit,'render':render,'quality':quality}).run_once())
    r=deliver('plan-success');check('edit_chain_delivered_by_assistant','视频已完成' in r['content'])
    start('plan-failure');current['failure']=True;plan_worker(True);r=deliver('plan-failure')
    check('native_failure_explains_unknown_without_fake_promise','没有结果查询能力' in r['content'] and '不会自动重发' in r['content'])
    before=len(s.snapshot(current['work'])['runs']);chat('plan-failure',c.view('plan-failure')['segment_id'],'discuss')
    check('failure_allows_next_user_reply_without_new_run',len(s.snapshot(current['work'])['runs'])==before)
    start('edit-failure');plan_worker();deliver('edit-failure');apply_last('edit-failure');current['edit_failure']=True
    async def failed_edit(ctx):raise ProductionError('edit_fixture_failed','剪辑素材不可用',requires_decision=True)
    asyncio.run(Worker(s.store,{'supply':supply,'edit':failed_edit}).run_once())
    r=deliver('edit-failure');check('native_edit_failure_explained','剪辑阶段失败' in r['content'])
    check('native_host_event_reaches_model',bool(native_event_requests) and all('宿主任务结果事件' in json.dumps(b,ensure_ascii=False) for b in native_event_requests))
    check('loopback_only',not (f['root']/'denials.log').exists())
    return {'status':'PASS','checks':checks,'fake_model_requests':len(f['model'].requests),'paid_requests':0,'production_environment_changed':False,'real_media_production':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--serve',action='store_true');args=parser.parse_args()
    with fixture(args.root,configure=configure) as f:
        result=probe(f)
        print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
        if args.serve:
            print('PROOF_URL='+f['url']+'/',flush=True)
            while True:time.sleep(1)
