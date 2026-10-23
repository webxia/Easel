from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import threading
import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from easel.production.publication import Publications
from easel.production.errors import ProductionError
from easel.production.deletion import DeletionService
from easel.publication_bilibili import BilibiliAdapter, BilibiliSession, biliup_command, publishing_lock
from web.publication_api import create_publication_router
from web.production_api import production_error_handler
from tests.production.test_revision_acceptance import prepared

ACCOUNT={'platform':'bilibili','uid':'123','name':'测试账号'}

class Fake:
    validate=staticmethod(BilibiliAdapter.validate)
    def __init__(self):
        self.identity=dict(ACCOUNT);self.calls=0;self.fail=False;self.entered=None;self.release=None;self.before=None
        self.receipt={'outcome':'verified','account':self.identity,'matched':{'status':'pending','platform_content_id':'BVtest'}}
    @contextmanager
    def session(self):yield self
    def account(self):return dict(self.identity)
    def snapshot(self):
        if self.before:self.before()
        return ['old']
    def stage_video(self,path,digest):return path
    def upload(self,path,content):
        self.calls+=1
        if self.entered:self.entered.set();self.release.wait(5)
        if self.fail:raise TimeoutError()
    def readback(self,*args,**kwargs):return self.receipt

@pytest.fixture
def publication(prepared):
    service,work=prepared
    service.command('accept',{'output_id':'passed'},command_id='accept',work_id=work,expected_revision=3)
    adapter=Fake();pub=Publications(service,adapter)
    draft=pub.prepare(work,'passed')
    content={**draft['content'],'account':dict(ACCOUNT),'tags':['测试']}
    draft=pub.save(draft['id'],draft['revision'],content)
    return pub,adapter,draft


def send(pub,d):return pub.submit(d['id'],d['revision'],d['confirmation_hash'])

def test_prepare_reuses_acceptance_and_exact_artifact(publication):
    p,a,d=publication
    assert p.prepare(d['work_id'],d['output_id'])['id']==d['id']
    assert d['media_digest'] and d['output_revision']==1
    assert a.calls==0
    with pytest.raises(ProductionError):p.prepare(d['work_id'],'unchecked')


def test_final_confirm_and_idempotency_survive_recreation(publication):
    p,a,d=publication
    result=send(p,d)
    assert result['attempts'][0]['state']=='verified'
    assert result['attempts'][0]['receipt']['matched']['status']=='pending'
    assert send(Publications(p.service,a),d)==result
    assert a.calls==1


@pytest.mark.parametrize('field,value',[('title','changed'),('body','changed'),('tags',['different']),('tid',21),('copyright',2),('source','https://source.example')])
def test_edits_invalidate_confirmation(publication,field,value):
    p,a,d=publication
    content={**d['content'],field:value,'source':'https://source.example'}
    p.save(d['id'],d['revision'],content)
    with pytest.raises(ProductionError):send(p,d)
    assert a.calls==0


def test_account_switch_requires_reconfirmation(publication):
    p,a,d=publication;a.identity={**ACCOUNT,'uid':'other'}
    with pytest.raises(ProductionError,match='账号'):send(p,d)
    assert a.calls==0


def test_media_changed_never_submitted(publication):
    p,a,d=publication
    with p.store.connection() as c:r=c.execute('select storage_ref from artifacts where id=?',(d['output_id'],)).fetchone()
    (p.service.outputs/r[0]).write_bytes(b'changed')
    with pytest.raises(ProductionError):send(p,d)
    assert a.calls==0


def test_acceptance_switch_invalidates_draft(publication):
    p,a,d=publication
    with p.store.transaction() as c:c.execute('update works set accepted_output_id=NULL where id=?',(d['work_id'],))
    with pytest.raises(ProductionError):send(p,d)
    assert a.calls==0


def test_concurrent_edit_between_preflight_and_reservation(publication):
    p,a,d=publication
    a.before=lambda:p.save(d['id'],d['revision'],{**d['content'],'body':'edit while checking'})
    with pytest.raises(ProductionError):send(p,d)
    assert a.calls==0


def test_duplicate_while_sending_returns_original_without_login_or_upload(publication):
    p,a,d=publication;a.entered=threading.Event();a.release=threading.Event()
    with ThreadPoolExecutor(2) as pool:
        future=pool.submit(send,p,d);assert a.entered.wait(3)
        duplicate=send(p,d)
        assert duplicate['attempts'][0]['state']=='sending'
        a.release.set();future.result()
    assert a.calls==1


@pytest.mark.parametrize('outcome',['unverified','login_required','readback_error'])
def test_readback_four_states_and_no_reupload(publication,outcome):
    p,a,d=publication;a.receipt={'outcome':outcome}
    result=send(p,d);assert result['attempts'][0]['state']=='unknown'
    p.reconcile(d['id']);send(p,d);assert a.calls==1


def test_timeout_after_upload_only_reconciles(publication):
    p,a,d=publication;a.fail=True
    assert send(p,d)['attempts'][0]['state']=='unknown'
    a.fail=False
    assert p.reconcile(d['id'])['attempts'][0]['state']=='verified'
    assert a.calls==1


def test_restart_with_sending_cannot_replay(publication):
    p,a,d=publication;send(p,d)
    with p.store.transaction() as c:c.execute("update publication_attempts set state='sending'")
    restored=Publications(p.service,a)
    assert send(restored,d)['attempts'][0]['state']=='sending'
    restored.reconcile(d['id']);assert a.calls==1


def test_known_success_retained_on_readback_error(publication):
    p,a,d=publication;send(p,d);a.receipt={'outcome':'readback_error'}
    assert p.reconcile(d['id'])['attempts'][0]['state']=='verified'


def test_foreign_account_readback_is_not_success(publication):
    p,a,d=publication;a.receipt={**a.receipt,'account':{**ACCOUNT,'uid':'other'}}
    assert send(p,d)['attempts'][0]['state']=='unknown'


def test_deletion_requires_cancel_and_submitted_cannot_cancel(publication):
    p,a,d=publication;deletion=DeletionService(p.store,outputs=p.service.outputs)
    with pytest.raises(ProductionError,match='发布'):deletion.preview(d['work_id'],d['output_id'])
    p.cancel(d['id'],d['revision'])
    assert deletion.preview(d['work_id'],d['output_id'])['output_id']==d['output_id']
    with pytest.raises(ProductionError):send(p,d)


def test_submitted_is_immutable(publication):
    p,a,d=publication;send(p,d)
    with pytest.raises(ProductionError):p.save(d['id'],d['revision'],d['content'])
    with pytest.raises(ProductionError):p.cancel(d['id'],d['revision'])


def test_preflight_failure_is_retryable_without_dispatch(publication):
    p,a,d=publication
    def fail():raise ProductionError('unavailable','未提交')
    a.before=fail
    with pytest.raises(ProductionError):send(p,d)
    assert p.get(d['id'])['state']=='draft' and not p.get(d['id'])['attempts']
    assert p.get(d['id'])['last_error']['submitted'] is False
    a.before=None;send(p,d);assert a.calls==1


def test_api_contract_and_recovery(publication):
    p,a,d=publication;app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler)
    app.include_router(create_publication_router(lambda:p.service,lambda:a))
    client=TestClient(app);base='/api/production/publications'
    assert client.get(base).json()[0]['id']==d['id']
    assert client.post(base+'/account').json()==ACCOUNT
    assert client.post(base+'/prepare',json={'work_id':d['work_id'],'output_id':'unchecked'}).status_code==409
    assert client.post(base+'/'+d['id']+'/submit',json={'revision':d['revision'],'confirmation_hash':'wrong'}).status_code==409
    assert a.calls==0
    assert client.post(base+'/'+d['id']+'/submit',json={'revision':d['revision'],'confirmation_hash':d['confirmation_hash']}).status_code==200
    assert client.post(base+'/'+d['id']+'/reconcile').status_code==200
    assert a.calls==1


def test_adapter_exact_unambiguous_readback(monkeypatch,tmp_path):
    from skills.shared.scripts import platform_readback as r
    session=BilibiliSession(tmp_path,tmp_path/'cookies');monkeypatch.setattr(session,'account',lambda:ACCOUNT)
    content={'title':'complete title'}
    stamp='2026-10-23T00:00:00Z';ts=1792713600000
    rows=[r.WorkItem('new','complete title','pending',ts)]
    monkeypatch.setattr(r,'read_bilibili_works',lambda *args,**kwargs:rows)
    assert session.readback(content,[],stamp)['outcome']=='verified'
    assert session.readback(content,['new'],stamp)['outcome']=='unverified'
    rows.append(r.WorkItem('another','complete title','published',ts))
    assert session.readback(content,[],stamp)['outcome']=='unverified'
    rows[:]=[r.WorkItem('prefix','complete tit','published',ts)]
    assert session.readback(content,[],stamp)['outcome']=='unverified'


def test_shared_legacy_lock_and_credential_snapshot(tmp_path,monkeypatch):
    cookie=tmp_path/'cookies.json';cookie.write_text('{"fixture":1}')
    adapter=BilibiliAdapter(tmp_path)
    with adapter.session() as session:
        cookie.write_text('{"fixture":2}')
        assert json.loads(session.cookie.read_text())=={'fixture':1}
        import os
        if os.name!='nt':assert session.cookie.stat().st_mode & 0o077==0
        private=session.cookie
        with pytest.raises(ProductionError):
            with publishing_lock(tmp_path):pass
    assert not private.exists()


def test_delivery_follows_actual_acceptance_and_known_failure(publication):
    p,a,d=publication
    output=next(o for o in p.service.snapshot(d['work_id'])['artifacts'] if o['id']==d['output_id'])
    assert output['delivery']['can_publish']
    from easel.production.delivery import output_guidance
    assert not output_guidance(output,True,True)['can_publish']
    assert '完整声音' in output_guidance({'manual_review_required':True})['message']
    assert not output_guidance({'quality_state':'needs_fix'})['can_accept']


def test_attribution_is_carried_and_cannot_be_edited(prepared):
    service,work=prepared
    with service.store.transaction() as c:c.execute('update artifacts set metadata_json=? where id=?',(json.dumps({'schema_version':1,'attribution':{'credit_text':'Creator CC BY','source_page':'https://example.test'}}),'passed'))
    service.command('accept',{'output_id':'passed'},command_id='accept',work_id=work,expected_revision=3)
    p=Publications(service,Fake());d=p.prepare(work,'passed')
    assert d['content']['credits']=='Creator CC BY\nhttps://example.test'
    with pytest.raises(ProductionError):p.save(d['id'],d['revision'],{**d['content'],'credits':''})


def test_cli_uses_confirmed_fields_without_shell():
    content={'title':'literal $(echo no)','body':'body','credits':'credit','tid':36,'copyright':2,'source':'source','tags':['tag']}
    cmd=biliup_command('private/cookies.json','video.mp4',content)
    assert cmd[:3]==['biliup','-u','private/cookies.json']
    assert cmd[cmd.index('--desc')+1]=='body\n\ncredit'
    assert cmd[cmd.index('--title')+1]==content['title']


def test_calendar_projection_has_single_owner_and_never_republishes(publication):
    p,a,d=publication;send(p,d)
    assert p.calendar_items()==[]  # moderation is not public
    a.receipt['matched']['status']='published'
    p.reconcile(d['id'])
    assert len(p.calendar_items())==1
    assert p.calendar_items()==p.calendar_items()
    assert a.calls==1


def test_cancel_then_explicit_prepare_reopens_without_calling_platform(publication):
    p,a,d=publication;p.cancel(d['id'],d['revision'])
    reopened=p.prepare(d['work_id'],d['output_id'])
    assert reopened['state']=='draft' and reopened['revision']>d['revision']
    assert reopened['id']==d['id'] and a.calls==0


def test_published_history_survives_output_deletion(publication):
    p,a,d=publication;send(p,d)
    deletion=DeletionService(p.store,outputs=p.service.outputs)
    preview=deletion.preview(d['work_id'],d['output_id'])
    deletion.execute('delete-published',d['work_id'],preview['expected_revision'],preview['preview_hash'],d['output_id'])
    assert p.get(d['id'])['attempts'][0]['state']=='verified'
    assert send(p,d)['attempts'][0]['state']=='verified' and a.calls==1


def test_staged_media_is_exact_snapshot(tmp_path):
    import hashlib
    source=tmp_path/'source.mp4';source.write_bytes(b'accepted')
    private=tmp_path/'private';private.mkdir()
    session=BilibiliSession(tmp_path,private/'cookies.json')
    staged=session.stage_video(source,hashlib.sha256(b'accepted').hexdigest())
    source.write_bytes(b'replaced')
    assert staged.read_bytes()==b'accepted'


def test_forward_migration_preserves_existing_work(tmp_path,monkeypatch):
    from easel.production import store as module
    target=module.Store(tmp_path/'old.sqlite3')
    with monkeypatch.context() as old:
        old.setattr(module,'SCHEMA_VERSION',4)
        target.initialize()
    work=target.create_work({'title':'retained'})
    target.initialize()
    assert target.get_work(work['id'])['title']=='retained'
    with target.connection() as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==5
        assert c.execute('select count(*) from publication_drafts').fetchone()[0]==0


def test_calendar_does_not_initialize_database(tmp_path):
    from easel.production.publication import calendar_projection
    path=tmp_path/'absent'/'production.sqlite3'
    assert calendar_projection(path)==[] and not path.parent.exists()


def test_description_budget_counts_exact_exported_text(publication):
    _,adapter,d=publication
    content={**d['content'],'body':'a'*2000,'credits':''}
    adapter.validate(content,final=True)
    content['credits']='required credit'
    with pytest.raises(ProductionError):adapter.validate(content,final=True)


def test_reaccepting_does_not_bypass_unresolved_submission(publication):
    p,a,d=publication;a.fail=True;send(p,d)
    p.service.command('accept',{'output_id':d['output_id']},command_id='accept-again',work_id=d['work_id'],expected_revision=p.service.snapshot(d['work_id'])['revision'])
    again=p.prepare(d['work_id'],d['output_id'])
    again=p.save(again['id'],again['revision'],{**again['content'],'tags':['test'],'account':ACCOUNT})
    with pytest.raises(ProductionError,match='待核实'):send(p,again)
    assert a.calls==1
