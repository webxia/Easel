#!/usr/bin/env python3
"""A5: actual isolated Web/OpenClaw + WorkService/Worker/FFmpeg journeys.

Only scripted chat/creative answers and synthetic licensed local media. Never
imports real runtime configuration or installs/restarts the production service.
Use --serve for manual browser acceptance; --probe records HTTP/native evidence.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from PIL import Image,ImageDraw
from easel.production.artifacts import register_file
from easel.production.operations import OperationService
from easel.production.planning import PlanningTasks
from easel.production.creation import CreationTasks
from easel.production.revisions import RevisionTasks
from easel.production.worker import Worker,TaskResult
from easel.conversation import ConversationService
from validate_video_conversation import fixture
from validate_openclaw_work_bridge import wait_for

IDENTITY={'provider':'direct-api','model':'a5-local-scripted','mode':'structured'}

class LocalCreativeModel:
    capabilities=frozenset({'text','structured','image','audio','tools'})
    def __init__(self):self.calls=[]
    async def complete(self,messages,tools,schema):
        context=json.loads(messages[1]['content'][0]['text'])
        kind=schema['title'];self.calls.append({'kind':kind,'context':context})
        if kind in {'VoiceReadyCreativePlan','CreativePlan'}:
            settings=json.loads(context['brief'].split('本次明确设置：')[1].split('\n')[0])
            settings={k:v for k,v in settings.items() if k in {'duration_seconds','aspect_ratio','audio_mode','voice','subtitles'}}
            settings={'duration_seconds':15,'aspect_ratio':'16:9','audio_mode':'music',**settings}
            value={'title':'创业笔记·先理解用户','summary':'真实经历，先听用户，再谈产品。','script':'先理解用户需求，再动手做产品。',
                'scenes':[{'id':'s1','purpose':'经历','visual':'蓝色静帧，克制留白','narration':''},
                          {'id':'s2','purpose':'转折','visual':'12秒后暖色静帧','narration':''}],
                'settings':settings,'facts':[],'constraints':['不改写真实经历'],'adaptation_permissions':[]}
        elif kind=='DirectorAnalysis':
            value={k:'合成参考的离线合同证据；不代表模型真实审美判断' for k in ('visual_style','storytelling','rhythm','sound','typography')}
            value.update(invariants=['克制与留白'],freedom=['题材可变'],evidence_notes=['实际参考帧和音轨进入请求'])
        elif kind=='CreativeEdit':
            pictures=[a['asset_id'] for a in context['artifacts'] if a['kind']=='image']
            audio=next(a['asset_id'] for a in context['artifacts'] if a['kind']=='audio')
            value={'scenes':[{'scene_id':'s1','asset_id':pictures[0],'duration':12},
                              {'scene_id':'s2','asset_id':pictures[1],'duration':3}],
                   'audio':[{'clip_id':'bgm','asset_id':audio,'role':'music','at':0,'duration':15}], 'captions':[]}
        elif kind=='RevisionProposal':
            base=context['artifacts'][0]['base_edit'];edit={k:deepcopy(base[k]) for k in ('scenes','audio','captions','required_features')}
            edit['scenes'][1]['motion']='push_in'
            expanded='扩大影响' in context['brief']
            value={'summary':'仅12至15秒画面缓慢推近，声音保持不变','affected':['visual'],'expands_scope':expanded,
                   'requires_new_generation':False,'reason':'复用原图片与完整音轨','edit':edit}
        else:raise AssertionError('Unexpected offline model task: '+kind)
        return {'content':json.dumps(value,ensure_ascii=False)}


def scoped_context(body):
    text=next(m['content'] for m in reversed(body['messages']) if m['role']=='user')
    return json.loads(text.split('【服务端创作上下文与来源，只适用于本运行段】\n')[1])


def configure(app,service,model,web):
    root=service.outputs.parent
    # Explicit local-only settings for capabilities. Execution uses no HTTP transport.
    (root/'.env').write_text('EASEL_DIRECT_API_BASE_URL=http://127.0.0.1:1/v1\nEASEL_DIRECT_API_MODEL=a5-local-scripted\nEASEL_DIRECT_API_KEY=\n')
    media=root/'media';media.mkdir(exist_ok=True)
    for name,color in [('blue','#174d70'),('warm','#ca8158')]:
        image=Image.new('RGB',(640,360),color)
        draw=ImageDraw.Draw(image);draw.rectangle((110,80,260,260),fill='#e8d7b8');draw.ellipse((360,80,530,250),fill='#38564a')
        if not (media/name).with_suffix('.png').exists():image.save(media/(name+'.png'))
    if not (media/'tone.wav').exists():subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=15','-ar','48000','-ac','2',str(media/'tone.wav')],check=True,timeout=20)
    if not (media/'reference.mp4').exists():subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(media/'blue.png'),'-i',str(media/'tone.wav'),'-t','1','-vf','scale=320:180','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(media/'reference.mp4')],check=True,timeout=20)
    creative=LocalCreativeModel();planning=PlanningTasks(service,OperationService(service.store),creative,IDENTITY,'a5-offline-v1')
    creation=CreationTasks(service,planning,manual_review_only=True)
    async def supply(ctx):
        ids=[]
        for name,kind,mime in [('blue.png','image','image/png'),('warm.png','image','image/png'),('tone.wav','audio','audio/wav')]:
            ids.append(register_file(service,ctx,media/name,kind=kind,media_type=mime,
                metadata={'source':'synthetic-local-A5','license':'test-created','role':'music' if kind=='audio' else 'visual'})['id'])
        return TaskResult(next_kind='edit',next_payload={'asset_ids':ids})
    worker=Worker(service.store,{'plan':planning.plan,'analyze_director':planning.analyze_director,'supply':supply,
        'edit':creation.edit,'render':creation.render,'quality':creation.quality,'revise':RevisionTasks(service,planning,creation).revise},poll_interval=.05)
    async def loop():
        while True:
            await worker.run_once();await asyncio.sleep(.1)
    @asynccontextmanager
    async def lifespan(_):
        task=asyncio.create_task(loop())
        try:yield
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    app.router.lifespan_context=lifespan
    def proposal(kind,values):
        def answer(body):
            c=scoped_context(body)
            return 'easel_work_propose',{'kind':kind,'values':values(c) if callable(values) else values,'source_refs':[c['sources'][-1]['ref']]}
        return answer
    model.extra_cases.update({
        'brief':lambda body:('easel_work_update_brief',{'entries':[
            {'kind':'user_requirement','text':'先理解用户需求，再动手做产品','source_refs':[next(s['ref'] for s in scoped_context(body)['sources'] if '先理解用户需求，再动手做产品' in s['text'])]},
            {'kind':'suggestion','text':'用留白表现克制','source_refs':[scoped_context(body)['sources'][-1]['ref']]}]}),
        'reference':lambda body:('easel_work_register_inputs',{'attachment_id':scoped_context(body)['sources'][-1]['attachments'][0]['id'],'usage':'reference'}),
        'director':proposal('director_formation',lambda c:{'name':'留白导演','reference_input_ids':[i['id'] for i in c['inputs'] if i['kind']=='video']}),
        'learning':proposal('profile',lambda c:{'file':'preferences','before_hash':c['profile_save_target']['hashes']['preferences'],
            'after':c['profile_save_target']['files']['preferences']+'\n视频开头先呈现具体用户问题。\n','entries':['视频开头先呈现具体用户问题。']}),
        'defaults':proposal('channel_defaults',{'creative_basis':{'audience':'独立产品创作者'}}),
        'director_version':proposal('director_revision',lambda c:{'base_revision':c['entry']['director']['revision'],
            'style':{**c['entry']['director_style'],'rhythm':'保留留白，转折更清楚'}}),
        'revision':lambda body:('easel_work_request_revision',{'feedback':'只改12秒后的画面，保持声音','protected':['声音','0至12秒画面'],'interval':{'start':12,'end':15}}),
        'create':('easel_work_create_draft',{'title':'创业笔记·先理解用户','input_text':'先理解用户需求，再动手做产品'}),
    })
    model.delays={'slow':2}
    return {'creative':creative,'worker':worker,'media':media,'web':web}


class Journey:
    def __init__(self,f):self.f=f;self.client=httpx.Client(base_url=f['url'],timeout=120,trust_env=False);self.checks=[];self.session='a5';self.segment=None;self.work=None
    def check(self,name,condition,**evidence):
        self.checks.append({'name':name,'pass':bool(condition),**evidence})
        (self.f['root']/'checkpoint.json').write_text(json.dumps(self.checks,ensure_ascii=False,indent=2))
        if not condition:raise AssertionError(name+' '+json.dumps(evidence,ensure_ascii=False))
    def request(self,method,path,body=None,status=200):
        r=self.client.request(method,path,json=body);assert r.status_code==status,(path,r.status_code,r.text);return r.json()
    def enter(self,entry,session=None):
        self.session=session or self.session;v=self.request('POST',f'/api/chat/video/{self.session}/enter',{'command_id':uuid.uuid4().hex,'entry':entry});self.segment=v['segment_id'];self.work=v['work_id'];return v
    def view(self):return self.request('GET',f'/api/chat/video/{self.session}')
    def snap(self):return self.request('GET','/api/production/works/'+self.work)
    def chat(self,case,message='',attachments=None):
        turn=uuid.uuid4().hex;body={'sessionId':self.session,'turnId':turn,'videoSegmentId':self.segment,'message':message+' A1_CASE='+case,'interaction_mode':'video','attachments':attachments or []}
        response=self.client.post('/api/chat/stream',json=body)
        assert response.status_code==200 and 'event: done' in response.text,(response.status_code,response.text)
        wait_for(lambda:all(t['state']=='ended' for t in self.view()['turns']),15)
        return body,response.text
    def apply(self,kind):
        p=next(p for p in reversed(self.view()['proposals']) if p['kind']==kind and p['state']=='proposed')
        body={'command_id':uuid.uuid4().hex,'hash':p['body_hash']}
        r=self.request('POST',f"/api/chat/video/{self.session}/proposals/{p['id']}/apply",body)
        if kind=='draft':self.work=r['work_id']
        return p,body,r
    def command(self,path,payload,status=202,body=None):
        body=body or {'command_id':uuid.uuid4().hex,'expected_revision':self.snap()['revision'],'payload':payload}
        return self.request('POST',f'/api/production/works/{self.work}/'+path,body,status),body
    def settle(self):
        def terminal():
            s=self.snap();r=next((r for r in s['runs'] if r['id']==s['active_run_id']),None)
            return not r or r['state'] in {'succeeded','failed','needs_decision','paused'}
        wait_for(terminal,120);return self.snap()
    def authorize_and_resume(self):
        s=self.settle()
        if s['state']=='needs_decision':
            task=next(t for t in s['tasks'] if t['run_id']==s['active_run_id'] and t['state']=='needs_decision')
            self.command('authorization-grants',{'purpose':'planning','services':[IDENTITY]})
            self.command('resume',{'decision_id':task['id']});s=self.settle()
        assert s['state']=='awaiting_confirmation',s['tasks'];return s
    def upload(self,name='reference.mp4',session=None):
        path=self.f['media']/name
        r=self.client.post('/api/upload',data={'sessionId':session or self.session},files={'files':(name,path.read_bytes())});r.raise_for_status();return r.json()['files'][0]

    def detached_turn(self,case,marker):
        body={'sessionId':self.session,'turnId':uuid.uuid4().hex,'videoSegmentId':self.segment,'message':marker+' A1_CASE='+case,'interaction_mode':'video'}
        with self.client.stream('POST','/api/chat/stream',json=body) as response:
            assert response.status_code==200
            for line in response.iter_lines():
                if line.startswith('event: activity'):break
        return body


def probe(f):
    j=Journey(f);service=f['service'];c=ConversationService(service)
    # Ordinary entry -> explicit video context, with/without profile, consultation only.
    j.enter({});j.chat('discuss','先聊主题，不制作');a=j.upload();j.chat('discuss','这份参考先留着讨论',attachments=[a])
    j.check('UI01_UI02_consultation_attachment_without_profile_no_work',service.list_works()['items']==[])
    j.enter({'profile_ref':'one'});j.chat('channel','创建创业笔记频道，本期讲先理解用户需求，再动手做产品')
    saved=j.view();p,b,r=j.apply('channel_create');channel=r['id']
    replay=j.request('POST',f"/api/chat/video/{j.session}/proposals/{p['id']}/apply",b)
    j.check('UI26_channel_save_replay_without_work',replay==r and service.list_works()['items']==[] and j.view()['context']['channel_id']==channel,channel=channel)
    j.chat('create','本期先理解用户需求，再动手做产品');p,b,r=j.apply('draft');work=j.work
    j.chat('brief','请保留真实经历');j.chat('discuss','为什么这样表达');j.check('UI02_UI05_discussion_brief_no_runs',j.snap()['runs']==[])
    j.command('basis',{'settings':{'duration_seconds':15,'aspect_ratio':'16:9','audio_mode':'music','subtitles':{'enabled':False}}})
    a=j.upload();j.chat('reference','参考只用来拆解风格',attachments=[a]);inputs=j.snap()['inputs']
    j.check('UI09_reference_rights_unknown',len(inputs)==1 and inputs[0]['usage']=='reference' and json.loads(inputs[0]['metadata_json'])['source']['rights'].get('status','UNKNOWN')=='UNKNOWN')
    j.chat('director','请拆解这个参考形成留白导演');p,b,receipt=j.apply('director_formation');director=receipt['id']
    s=j.settle();j.check('UI22_UI27_analysis_requires_authorization',s['state']=='needs_decision' and not j.request('GET','/api/production/directors')[0]['versions'])
    task=next(t for t in s['tasks'] if t['state']=='needs_decision');j.command('authorization-grants',{'purpose':'planning','services':[IDENTITY]});j.command('resume',{'decision_id':task['id']});j.settle()
    d=j.request('GET','/api/production/directors')[0];v=d['versions'][0];version=v['id']
    j.check('UI22_UI27_analysis_draft_no_production',bool(v['evidence']) and not v['style_confirmed'] and not v['accepted_at'] and len(j.snap()['runs'])==1)
    j.request('PATCH','/api/production/directors/'+director,{'command_id':uuid.uuid4().hex,'expected_revision':d['revision'],'payload':{'revision_id':version,'style_confirmed':True}},202)
    j.command('basis',{'settings':{'director_revision':version,'director_trial':True}})
    j.chat('plan','现在整理完整方案');p,b,receipt=j.apply('plan');s=j.authorize_and_resume()
    plan=s['plans'][-1];old_plan=deepcopy(plan);j.check('UI05_UI21_frozen_sources_channel_profile_director',plan['plan']['director_revision_id']==version and bool(plan['plan']['conversation_basis']) and len(json.loads(plan['plan']['profile_snapshot']['content']))==6,plan_revision=plan['revision'],plan_hash=plan['plan_hash'])
    body={'command_id':'a5-confirm-once','expected_revision':s['revision'],'payload':{'plan_hash':plan['plan_hash'],'services':[IDENTITY]}}
    first=j.request('POST',f"/api/production/works/{work}/plans/{plan['revision']}/confirm",body,202)
    replay=j.request('POST',f"/api/production/works/{work}/plans/{plan['revision']}/confirm",body,202)
    changed={**body,'command_id':'a5-other-window'};conflict=j.client.post(f"/api/production/works/{work}/plans/{plan['revision']}/confirm",json=changed)
    j.check('UI06_confirm_replay_and_second_window',first==replay and conflict.status_code==409,run=first['run_id'])
    blocked=j.client.post(f'/api/production/works/{work}/inputs',json={'command_id':'active-input','expected_revision':j.snap()['revision'],'payload':{'text':'cannot change active run'}})
    j.check('UI09_active_run_input_mutation_rejected',blocked.status_code==409)
    detached=j.detached_turn('discuss','DETACHED_TURN')
    wait_for(lambda:all(t['state']=='ended' for t in j.view()['turns']),15)
    count=len(f['model'].requests);replay=j.client.post('/api/chat/stream',json=detached)
    j.check('UI06_UI08_disconnect_replay_without_redispatch',replay.status_code==200 and 'event: done' in replay.text and len(f['model'].requests)==count)
    slow=j.detached_turn('slow','STOPPED_REPLY')
    wait_for(lambda:any('STOPPED_REPLY' in json.dumps(b['messages'][-1]) for b in f['model'].requests),10)
    stopped=j.request('POST','/api/chat/stop',{'sessionId':j.session})
    wait_for(lambda:all(t['state']=='ended' for t in j.view()['turns']),15)
    j.check('UI08_stop_reply_does_not_cancel_run',stopped['stopped'] and stopped['production_cancelled'] is False and j.snap()['runs'][-1]['state']!='cancelled')
    with j.client.stream('GET',f'/api/production/works/{work}/events') as events:
        lines=[]
        for line in events.iter_lines():
            lines.append(line)
            if not line and any(x.startswith('data:') for x in lines):break
    streamed=json.loads(next(line[5:].strip() for line in lines if line.startswith('data:')))
    j.check('UI07_work_SSE_uses_authoritative_snapshot',streamed['id']==work and streamed['cursor']<=j.snap()['cursor'] and streamed['active_run_id']==first['run_id'])
    s=j.settle();outputs=[a for a in s['artifacts'] if a['kind']=='output'];j.check('UI07_UI11_real_render_technical_manual_review',s['state']=='reviewable' and len(outputs)==1 and outputs[0]['manual_review_required'],tasks=[{'kind':t['kind'],'state':t['state']} for t in s['tasks']])
    output=outputs[0];old_path,_=service.artifact_path(output['id']);old_hash=hashlib.sha256(old_path.read_bytes()).hexdigest()
    j.check('UI11_UI14_unaccepted_not_in_library',j.request('GET','/api/production/library')==[])
    rejected=j.client.post(f"/api/production/works/{work}/outputs/{output['id']}/accept",json={'command_id':'no-manual','expected_revision':s['revision'],'payload':{}})
    j.check('UI11_manual_ack_required',rejected.status_code==422 or rejected.status_code==400)
    accepted,_=j.command('outputs/'+output['id']+'/accept',{'manual_review_confirmed':True})
    d=j.request('GET','/api/production/directors')[0]
    j.check('UI23_work_accept_does_not_accept_director',not d['versions'][0]['accepted_at'])
    j.request('POST',f'/api/production/directors/{director}/accept',{'command_id':'accept-director','expected_revision':d['revision'],'payload':{'revision_id':version,'trial_artifact_id':output['id'],'manual_review_confirmed':True}},202)
    ch=j.request('GET','/api/production/channels')[0]
    j.check('UI23_director_accept_does_not_set_default',ch['default_director_revision'] is None)
    j.request('PATCH','/api/production/channels/'+channel,{'command_id':'default-director','expected_revision':ch['revision'],'payload':{'director_ids':[director],'default_director_revision':version}},202)
    # Enter a concrete accepted output; native revision creates a candidate, not a run.
    j.enter({'work_id':work,'output_id':output['id'],'kind':'revise'});before=len(j.snap()['runs']);j.chat('revision','只改12秒后的画面，保持声音');j.check('UI10_revision_card_no_implicit_run',len(j.snap()['runs'])==before);j.apply('revision');s=j.settle()
    outputs=[a for a in s['artifacts'] if a['kind']=='output'];j.check('UI10_UI14_local_revision_preserves_A',s['state']=='reviewable' and len(outputs)==2 and s['accepted_output_id']==output['id'] and hashlib.sha256(old_path.read_bytes()).hexdigest()==old_hash)
    second=next(a for a in outputs if a['id']!=output['id']);a_path,_=service.artifact_path(second['id'])
    def audio_hash(path):
        return hashlib.sha256(subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vn','-f','s16le','-'],capture_output=True,check=True).stdout).hexdigest()
    j.check('UI10_decoded_audio_unchanged',audio_hash(old_path)==audio_hash(a_path))
    j.check('UI10_visual_change_produces_distinct_version',output['digest']!=second['digest'])
    def frame_hash(path,at):
        return hashlib.sha256(subprocess.run(['ffmpeg','-v','error','-ss',str(at),'-i',str(path),'-frames:v','1','-f','image2pipe','-vcodec','png','-'],capture_output=True,check=True).stdout).hexdigest()
    j.check('UI10_protected_visual_interval_unchanged',frame_hash(old_path,2)==frame_hash(a_path,2) and frame_hash(old_path,13)!=frame_hash(a_path,13))
    last=j.snap()['cursor'];records=service.store.events(work,last-1)
    with j.client.stream('GET',f'/api/production/works/{work}/events?after={last-1}') as events:
        lines=[]
        for line in events.iter_lines():
            lines.append(line)
            if not line and any(x.startswith('data:') for x in lines):break
    event=json.loads(next(line[5:].strip() for line in lines if line.startswith('data:')))
    j.check('UI07_reconnect_cursor_replays_exact_event',event['seq']==records[0]['seq'] and event['kind']==records[0]['kind'])
    j.command('revisions',{'output_id':output['id'],'feedback':'扩大影响，请先说明完整范围'});s=j.settle();review=s['reviews'][0]
    j.check('UI10_expanded_scope_waits_for_explicit_confirmation',s['state']=='needs_decision' and review['changes']['expands_scope'] and len([a for a in s['artifacts'] if a['kind']=='output'])==2)
    j.command('revisions/confirm',{'review_id':review['id'],'change_hash':review['change_hash'],'services':[IDENTITY]});s=j.settle()
    j.check('UI10_confirmed_expansion_creates_unconfirmed_plan',s['state']=='awaiting_confirmation' and not s['plans'][0]['confirmed_at'] and s['accepted_output_id']==output['id'])
    # Opt-in long term writes and future-only defaults, old plan remains frozen.
    before_profile=(service.profiles/'one/preferences.md').read_bytes();j.chat('learning','以后开头先呈现具体用户问题')
    j.check('UI15_proposal_does_not_write_profile',(service.profiles/'one/preferences.md').read_bytes()==before_profile)
    p,b,r=j.apply('profile');j.request('POST',f"/api/chat/video/{j.session}/proposals/{p['id']}/apply",b)
    j.check('UI16_explicit_profile_save_once',(service.profiles/'one/preferences.md').read_text().count('视频开头先呈现具体用户问题。')==1)
    j.chat('defaults','频道受众调整为独立产品创作者');j.apply('channel_defaults')
    j.chat('director_version','导演另存更清楚的节奏');j.apply('director_revision');d=j.request('GET','/api/production/directors')[0]
    j.check('UI17_new_style_draft_future_only',len(d['versions'])==2 and not d['versions'][0]['style_confirmed'] and not d['versions'][0]['accepted_at'] and next(p for p in j.snap()['plans'] if p['revision']==1)['plan']==old_plan['plan'])
    # Accepted library points at A even with a new preview B; fork selects inheritance and no grants.
    lib=j.request('GET','/api/production/library');j.check('UI18_library_exact_A',len(lib)==1 and lib[0]['artifact_id']==output['id'])
    fork,_=j.command('fork',{'output_id':output['id'],'title':'新主题','input_text':'新的产品故事','session_id':'fork-ui','inherit_settings':['director_revision','voice','subtitles']});forkwork=service.snapshot(fork['work_id'])
    with service.store.connection() as conn:grants=conn.execute('SELECT count(*) FROM authorization_grants WHERE work_id=?',(fork['work_id'],)).fetchone()[0]
    j.check('UI25_fork_exact_director_no_grants',forkwork['settings']['director_revision']==version and grants==0 and json.loads(forkwork['inputs'][0]['metadata_json'])['source']['rights']['status']=='UNKNOWN')
    # Channel entry future defaults vs history snapshots, no empty Work on browsing.
    before=len(service.list_works()['items']);j.enter({'profile_ref':'one','channel_id':channel});j.chat('context','本频道现在有哪些依据');j.check('UI19_UI20_UI21_channel_entry_no_empty_work',len(service.list_works()['items'])==before and j.view()['context']['settings']['director_revision']==version)
    j.enter({'director_revision':version,'profile_ref':'one'});j.chat('context','使用这位导演讨论');j.check('UI19_director_entry_no_empty_work',len(service.list_works()['items'])==before)
    j.enter({'work_id':work,'output_id':output['id'],'kind':'revise'});j.chat('context','恢复原作');j.check('UI24_historical_plan_unchanged',next(p for p in j.snap()['plans'] if p['revision']==1)['plan']==old_plan['plan'])
    start=len(f['model'].requests);old_segment=j.segment;j.enter({'profile_ref':'two'});j.chat('context','SECOND_PROFILE_SENTINEL')
    payload=json.dumps(f['model'].requests[start:]);j.check('UI03_UI28_cross_profile_native_isolation','PROFILE_two_identity_SENTINEL' in payload and 'PROFILE_one_identity_SENTINEL' not in payload and '先理解用户需求' not in payload)
    late=j.client.post('/api/chat/stream',json={'sessionId':j.session,'turnId':'late-a5','videoSegmentId':old_segment,'message':'late','interaction_mode':'video'})
    j.check('UI28_old_segment_rejected',late.status_code==409)
    j.enter({'work_id':work});stopped=j.request('POST','/api/chat/stop',{'sessionId':j.session});j.request('DELETE','/api/chat/video/'+j.session)
    j.check('UI08_delete_stop_preserve_outputs',not stopped.get('production_cancelled',False) and service.snapshot(work)['accepted_output_id']==output['id'] and old_path.is_file() and a_path.is_file())
    j.enter({'work_id':work},session='reopened');j.check('UI08_reopen_same_Work',j.view()['work_id']==work)
    pending=j.detached_turn('slow','DELETE_INFLIGHT')
    wait_for(lambda:any('DELETE_INFLIGHT' in json.dumps(b['messages'][-1]) for b in f['model'].requests),10)
    j.request('DELETE','/api/chat/video/'+j.session)
    def ended():
        with service.store.connection() as conn:return conn.execute('SELECT state FROM conversation_turns WHERE id=?',(pending['turnId'],)).fetchone()[0]=='ended'
    wait_for(ended,15)
    with service.store.connection() as conn:
        payload=json.loads(conn.execute('SELECT payload_json FROM conversation_turns WHERE id=?',(pending['turnId'],)).fetchone()[0])
        revoked=conn.execute('SELECT revoked_at FROM conversation_segments WHERE id=?',(j.segment,)).fetchone()[0]
    j.check('UI28_delete_inflight_native_end_reconciles_minimal_identity',bool(revoked) and bool(payload['run_id']) and 'message' not in payload and 'answer' not in payload and service.snapshot(work)['accepted_output_id']==output['id'])
    requests=json.dumps(f['model'].requests,ensure_ascii=False)
    from easel.conversation_bridge import TOOLS
    j.check('UI03_UI04_exact_native_tools_no_development_or_credentials',all({t['function']['name'] for t in b.get('tools',[])}==set(TOOLS) for b in f['model'].requests) and all(x not in requests for x in ('DEV_ONLY_FORBIDDEN_SENTINEL','MAIN_ONLY_FORBIDDEN_SENTINEL',f['bridge_token'])))
    j.check('UI03_all_six_dimensions_and_curated_Easel_knowledge',all('PROFILE_one_'+d+'_SENTINEL' in requests for d in ('identity','style','audience','platforms','preferences','memory')) and 'Easel 视频产线的交互知识' in requests)
    with service.store.connection() as conn:
        counts={t:conn.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ('works','runs','operations','acceptances','conversation_turns')}
        qc=[dict(r) for r in conn.execute('SELECT check_kind,status FROM quality_checks')]
        operations=[dict(r) for r in conn.execute('SELECT kind,provider,model,state FROM operations')]
    j.check('all_operations_are_scripted_local_model_receipts',all(o=={'kind':'MODEL',**{k:v for k,v in IDENTITY.items() if k!='mode'},'state':'succeeded'} for o in operations))
    j.check('local_only_model_receipts_no_generation_or_voice',all(c['kind'] in {'VoiceReadyCreativePlan','CreativePlan','DirectorAnalysis','CreativeEdit','RevisionProposal'} for c in f['creative'].calls) and not (f['root']/'denials.log').exists())
    return {'status':'PASS','scope':'isolated native Web + scripted creative model + real local Worker/FFmpeg; no production acceptance','checks':j.checks,'counts':counts,'quality_checks':qc,'operations':operations,'chat_model_requests':len(f['model'].requests),'creative_model_calls':len(f['creative'].calls),'paid_requests':0,'production_environment_changed':False,'isolated_worker_started':True,'production_worker_started':False,
        'work_id':work,'channel_id':channel,'director_id':director,'director_revision_id':version,'outputs':[{'id':a['id'],'sha256':a['digest'],'bytes':a['size_bytes']} for a in outputs]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--serve',action='store_true');parser.add_argument('--resume-isolated',action='store_true');args=parser.parse_args();result={}
    repo=Path(__file__).resolve().parents[1]
    files=[*repo.glob('easel/production/**/*.py'),*repo.glob('easel/conversation*.py'),repo/'easel/video_workspace.py',repo/'web/app.py',*repo.glob('web/*production*.py'),repo/'web/conversation_api.py',*repo.glob('web/frontend/src/**/*.ts*'),*repo.glob('agents/plugins/easel-work/*'),*repo.glob('scripts/validate_*conversation*.py'),repo/'scripts/validate_openclaw_work_bridge.py']
    hashes={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
    try:
        with fixture(args.root,configure=configure,resume=args.resume_isolated) as f:
            if args.serve:
                print(json.dumps({'url':f['url'],'root':str(args.root)}),flush=True)
                while True:time.sleep(1)
            result=probe(f)
    finally:
        if result:
            result['child_gateway_stopped']=True;result['source_sha256']=hashes
            (args.root/'a5-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='source_sha256'},ensure_ascii=False))

if __name__=='__main__':main()
