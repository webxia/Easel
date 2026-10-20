#!/usr/bin/env python3
"""Current native turn must await an authorized run. Loopback fake models only."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_video_conversation import fixture
from validate_openclaw_work_bridge import wait_for
from tests.production.test_conversation import entry, turn
from tests.production.test_conversation_pipeline import seed, pipe
from tests.production.test_planning_runtime import Transport
from easel.conversation import ConversationService
from easel.work_bridge import Identity
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.worker import Worker, TaskResult
import httpx


def probe(f):
    s=f['service'];c=ConversationService(s);channel=seed((s,c))
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'制作视频')
    work=pipe(b,i,'draft',user_quote='制作视频',values={'title':'隔离等待','input_text':'技术服务人'})['work_id']
    p=pipe(b,i,'offer',action='plan',values={'request':'整理完整方案'})
    # Leave native session assignment to the actual Gateway on the next turn.
    b.end(Identity(**i))
    with s.store.transaction() as conn:conn.execute('UPDATE conversation_segments SET native_session_id=NULL WHERE id=?',(seg,))
    f['model'].extra_cases['execute_wait']=('easel_pipeline',{'mode':'answer','proposal_id':p['proposal_id'],'hash':p['hash'],'user_quote':'A1_CASE=execute_wait'})
    received=[]
    def final(body):
        received.append(body)
        return '真实方案已完成：技术服务人。完整逐字稿与分镜已收到，请确认后再制作。'
    f['model'].final_texts={'execute_wait':final}
    answer={'title':'隔离方案','summary':'技术服务人','script':'技术服务人。','scenes':[{'id':'s1','purpose':'解释','visual':'科技画面','narration':'技术服务人。','duration_seconds':3,'required_input_ids':[]}],'settings':{'duration_seconds':3,'aspect_ratio':'16:9','audio_mode':'silent'}}
    handler=PlanningTasks(s,OperationService(s.store),Transport(answer),{'provider':'direct-api','model':'a1-fake','mode':'structured'},'fixture')
    events=[]
    def chat():
        with httpx.Client(base_url=f['url'],timeout=60,trust_env=False) as client:
            with client.stream('POST','/api/chat/stream',json={'sessionId':'ui','turnId':'native-wait','videoSegmentId':seg,'message':'A1_CASE=execute_wait','interaction_mode':'video'}) as response:
                response.raise_for_status()
                for line in response.iter_lines():events.append((time.monotonic(),line))
    # Closing the browser stream must not stop the separate native execution.
    with httpx.Client(base_url=f['url'],timeout=60,trust_env=False) as client:
        with client.stream('POST','/api/chat/stream',json={'sessionId':'ui','turnId':'native-wait','videoSegmentId':seg,'message':'A1_CASE=execute_wait','interaction_mode':'video'}) as response:
            for line in response.iter_lines():
                if line=='event: activity':break
    with ThreadPoolExecutor() as pool:
        future=pool.submit(chat)
        wait_for(lambda:len(s.snapshot(work)['runs'])==1,10)
        time.sleep(1.5)
        assert not any(line=='event: done' for _,line in events),'PREMATURE_DONE: native turn ended while planning was pending'
        assert not future.done() and not received,'native execution must remain waiting'
        with s.store.connection() as conn:
            assert conn.execute("SELECT state FROM conversation_turns WHERE id='native-wait'").fetchone()[0]=='active'
        completed=time.monotonic();asyncio.run(Worker(s.store,{'plan':handler.plan}).run_once())
        future.result(timeout=25)
    assert any(line=='event: done' and at>=completed for at,line in events)
    assert len(received)==1
    tools=[m for m in received[0]['messages'] if m['role']=='tool']
    assert any('技术服务人。' in json.dumps(m,ensure_ascii=False) for m in tools),'actual plan absent from current native tool result'
    with s.store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM conversation_turns WHERE json_extract(payload_json,'$.origin')='task_result'").fetchone()[0]==0
    assert len(s.snapshot(work)['runs'])==1,'planning must not automatically produce'
    assert not (f['root']/'denials.log').exists()
    checks=['planning_same_native_turn','refresh_reuses_original_execution']
    def propose(action,values,source):
        with s.store.transaction() as conn:
            return c.proposal(conn,c.segment(conn,'ui'),'pipeline',{'action':action,'payload':values,'summary':'隔离确认','catalog_target':{}},[source])
    def native(case,proposal,run_count,runner=None,stop=False):
        data={'sessionId':'ui','turnId':case,'videoSegmentId':seg,'message':'A1_CASE='+case,'interaction_mode':'video'}
        f['model'].extra_cases[case]=('easel_pipeline',{'mode':'answer','proposal_id':proposal['proposal_id'],'hash':proposal['hash'],'user_quote':data['message']})
        bodies=[]
        def final_result(body):
            bodies.append(body)
            return '本次真实结果已收到，请审阅；下一阶段需要你确认。'
        f['model'].final_texts[case]=final_result
        streamed=[]
        def request():
            with httpx.Client(base_url=f['url'],timeout=60,trust_env=False) as client:
                with client.stream('POST','/api/chat/stream',json=data) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():streamed.append(line)
        def pending():
            assert 'event: done' not in streamed and not bodies,case+' ended early'
        with ThreadPoolExecutor() as pool:
            future=pool.submit(request)
            wait_for(lambda:len(s.snapshot(work)['runs'])==run_count,10)
            time.sleep(.3);pending()
            if stop:
                with httpx.Client(base_url=f['url'],timeout=10,trust_env=False) as client:
                    reply=client.post('/api/chat/stop',json={'sessionId':'ui'}).json()
                assert reply=={'stopped':True,'production_cancelled':False}
            else:runner(pending)
            future.result(timeout=25)
        wait_for(lambda:c.view('ui')['turns'][-1]['state']=='ended',10)
        if stop:
            assert 'event: done' not in streamed
            assert s.snapshot(work)['runs'][-1]['state']=='pending'
            checks.append('native_stop_ends_wait_without_cancelling_production')
        else:
            assert 'event: done' in streamed and len(bodies)==1
            current=bodies[0]['messages']
            last_user=max(i for i,m in enumerate(current) if m['role']=='user')
            assert any('execution_result' in json.dumps(m) for m in current[last_user+1:] if m['role']=='tool')
            checks.append(case+'_same_turn_no_intermediate_done')
    plan=s.snapshot(work)['plans'][0]
    p=propose('confirm',{'plan_revision':1,'plan_hash':plan['plan_hash'],'services':[]},'native-wait')
    stages=[]
    def production(pending):
        async def step(ctx):
            kind=next(t['kind'] for t in s.snapshot(work)['tasks'] if t['id']==ctx.task_id)
            stages.append(kind);pending();await asyncio.sleep(.2)
            if kind=='quality' and stages.count('quality')==2:
                from tests.production.test_store import insert_artifact
                with ctx.transaction() as conn:insert_artifact(conn,work,'fixture-output',run_id=ctx.run_id,kind='output',output_revision=1,displayable=1)
                return TaskResult(work_state='reviewable')
            return TaskResult(next_kind={'supply':'edit','edit':'render','render':'quality','quality':'revise','revise':'render'}[kind])
        asyncio.run(Worker(s.store,{k:step for k in ['supply','edit','render','quality','revise']}).run_once())
    native('production',p,2,production)
    assert stages==['supply','edit','render','quality','revise','render','quality']
    p=propose('revise',{'output_id':'fixture-output','feedback':'仅修改画面'},'production')
    def revision(pending):
        async def step(ctx):
            pending();await asyncio.sleep(.2)
            kind=next(t['kind'] for t in s.snapshot(work)['tasks'] if t['id']==ctx.task_id)
            return TaskResult(work_state='reviewable') if kind=='quality' else TaskResult(next_kind={'revise':'render','render':'quality'}[kind])
        asyncio.run(Worker(s.store,{k:step for k in ['revise','render','quality']}).run_once())
    native('revision',p,3,revision)
    p=propose('plan',{'request':'新的隔离方案','services':[]},'revision')
    native('stop_wait',p,4,stop=True)
    assert not (f['root']/'denials.log').exists()
    return {'status':'PASS','checks':checks,'before_completion_done':False,'current_native_turn_received_plan':True,'after_delivery_done':True,'background_turns':0,'fake_model_requests':len(f['model'].requests),'paid_requests':0,'media_generated':False}



def timeout_config(app,service,model,web):
    path=service.outputs.parent/'openclaw.json'
    config=json.loads(path.read_text());config['agents']['defaults']['timeoutSeconds']=3
    path.write_text(json.dumps(config))
    return {}


def timeout_probe(f):
    s=f['service'];c=ConversationService(s);channel=seed((s,c))
    seg=entry(c,profile_ref='one',channel_id=channel,director_revision='v4',director_trial=True)
    b,i,_=turn(s,c,seg,'制作视频')
    work=pipe(b,i,'draft',user_quote='制作视频',values={'title':'超时隔离','input_text':'技术服务人'})['work_id']
    p=pipe(b,i,'offer',action='plan',values={'request':'完整方案'})
    b.end(Identity(**i))
    with s.store.transaction() as conn:conn.execute('UPDATE conversation_segments SET native_session_id=NULL WHERE id=?',(seg,))
    f['model'].extra_cases['timeout_wait']=('easel_pipeline',{'mode':'answer','proposal_id':p['proposal_id'],'hash':p['hash'],'user_quote':'A1_CASE=timeout_wait'})
    with httpx.Client(base_url=f['url'],timeout=20,trust_env=False) as client:
        response=client.post('/api/chat/stream',json={'sessionId':'ui','turnId':'timeout-wait','videoSegmentId':seg,'message':'A1_CASE=timeout_wait','interaction_mode':'video'})
    response.raise_for_status()
    assert 'event: error' in response.text and 'event: done' not in response.text
    wait_for(lambda:c.view('ui')['turns'][-1]['state']=='ended',10)
    snapshot=s.snapshot(work)
    assert len(snapshot['runs'])==1 and snapshot['runs'][0]['state']=='pending'
    with s.store.connection() as conn:assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
    assert not (f['root']/'denials.log').exists()
    return {'status':'PASS','native_timeout_seconds':3,'native_ended':True,'web_end':'error','production_state':'pending','production_cancelled':False,'resubmitted':False,'fake_model_requests':len(f['model'].requests),'paid_requests':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--native-timeout',action='store_true');args=parser.parse_args()
    with fixture(args.root,configure=timeout_config if args.native_timeout else None) as f:
        print(json.dumps(timeout_probe(f) if args.native_timeout else probe(f),ensure_ascii=False,indent=2))
