"""Original conversation to accepted-version draft; real local services, no network."""
import json
import pytest
from easel.conversation import ConversationService
from easel.work_bridge import Identity
from easel.production.publication import Publications
from easel.publication_bilibili import BilibiliAdapter
from tests.production.test_revision_acceptance import prepared
from tests.production.test_conversation import entry, turn, raises
from tests.production.test_conversation_pipeline import pipe


def setup(prepared):
    service,work=prepared
    conversations=ConversationService(service)
    segment=entry(conversations,kind='continue',work_id=work)
    return service,work,conversations,segment


def test_original_chat_accept_prepare_save_restart_and_replay(prepared):
    s,w,c,seg=setup(prepared)
    before=s.snapshot(w)
    b,i,_=turn(s,c,seg,'我接受第一版，请整理B站标题简介')
    accepted=pipe(b,i,'offer',action='accept',values={'output_id':'passed','manual_review_confirmed':False},user_quote='我接受第一版，请整理B站标题简介')
    assert not accepted['requires_user_confirmation']
    assert s.snapshot(w)['accepted_output_id']=='passed'
    assert pipe(b,i,'offer',action='accept',values={'output_id':'passed','manual_review_confirmed':False},user_quote='我接受第一版，请整理B站标题简介')==accepted
    result=pipe(b,i,'offer',action='publication_prepare',values={'output_id':'passed'},user_quote='我接受第一版，请整理B站标题简介')
    draft=result['publication']
    result=pipe(b,i,'offer',action='publication_save',values={'draft_id':draft['id'],'revision':draft['revision'],'changes':{'title':'对外标题','body':'简介','tags':['思考']}},user_quote='我接受第一版，请整理B站标题简介')
    assert result['publication']['revision']==draft['revision']+1
    assert result['draft_url']=='/#publication='+draft['id'] and result['submitted'] is False
    b.end(Identity(**i))
    replies=c.view('ui')['result_messages']
    assert len(replies)==1 and result['draft_url'] in replies[0]['content']
    assert '尚未投稿' in replies[0]['content']
    persisted=Publications(s,BilibiliAdapter(s.outputs.parent)).get(draft['id'])
    assert persisted['content']['title']=='对外标题'
    assert persisted['content']['account'] is None and persisted['attempts']==[]
    assert persisted['output_id']=='passed'
    assert s.snapshot(w)['runs']==before['runs']
    with s.store.connection() as conn:
        assert conn.execute('SELECT count(*) FROM acceptances').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM publication_drafts').fetchone()[0]==1
        assert conn.execute('SELECT count(*) FROM operations').fetchone()[0]==0
        assert conn.execute("SELECT count(*) FROM conversation_proposals WHERE state='applied'").fetchone()[0]==3
    b,i,_=turn(s,ConversationService(s),seg,'再看一下草稿',id='restart')
    assert pipe(b,i,'pending')['publication']['drafts'][0]['content']['body']=='简介'


def test_source_review_stale_and_protected_fields(prepared):
    s,w,c,seg=setup(prepared)
    b,i,_=turn(s,c,seg,'接受第一版，准备发布')
    raises('invalid_source',lambda:pipe(b,i,'offer',action='accept',values={'output_id':'passed'},user_quote='伪造授权'))
    raises('acceptance_changed',lambda:pipe(b,i,'offer',action='publication_prepare',values={'output_id':'passed'},user_quote='接受第一版，准备发布'))
    pipe(b,i,'offer',action='accept',values={'output_id':'passed'},user_quote='接受第一版，准备发布')
    result=pipe(b,i,'offer',action='publication_prepare',values={'output_id':'passed'},user_quote='接受第一版，准备发布')
    d=result['publication']
    for changes in [{'account':{'uid':'someone'}},{'credits':''},{'action':'submit'}]:
        raises('invalid_publication',lambda:pipe(b,i,'offer',action='publication_save',values={'draft_id':d['id'],'revision':d['revision'],'changes':changes},user_quote='接受第一版，准备发布'))
    raises('stale_publication',lambda:pipe(b,i,'offer',action='publication_save',values={'draft_id':d['id'],'revision':99,'changes':{'title':'失效修改'}},user_quote='接受第一版，准备发布'))
    assert Publications(s,BilibiliAdapter(s.outputs.parent)).get(d['id'])['revision']==d['revision']


def test_wrong_work_and_unreviewed_output_cannot_enter_publication(prepared):
    s,w,c,seg=setup(prepared)
    other=s.command('create',{'title':'other'},command_id='other')['work_id']
    seg=entry(c,kind='continue',work_id=other)
    b,i,_=turn(s,c,seg,'接受这版并准备发布')
    raises('binding_mismatch',lambda:pipe(b,i,'offer',action='accept',values={'output_id':'unchecked'},user_quote='接受这版并准备发布'))
    assert s.snapshot(w)['accepted_output_id'] is None
    with s.store.connection() as conn:assert conn.execute('SELECT count(*) FROM publication_drafts').fetchone()[0]==0


def test_direct_accept_retains_manual_review_requirement(prepared,monkeypatch):
    s,w,c,seg=setup(prepared)
    # Isolate the existing manual-review predicate; the bridge must neither
    # invent that human fact nor bypass the domain's requirement.
    with s.store.transaction() as conn:
        conn.execute("UPDATE artifacts SET quality_state='needs_fix' WHERE id='passed'")
        conn.execute("INSERT INTO quality_checks SELECT 'tech','passed',digest,'technical','fixture','pass','{}','now' FROM artifacts WHERE id='passed'")
    b,i,_=turn(s,c,seg,'接受此版')
    raises('manual_review_confirmation_required',lambda:pipe(b,i,'offer',action='accept',values={'output_id':'passed'},user_quote='接受此版'))
    with s.store.connection() as conn:assert conn.execute('SELECT count(*) FROM acceptances').fetchone()[0]==0




def test_acceptance_result_survives_interrupted_model(prepared):
    s,w,c,seg=setup(prepared)
    b,i,_=turn(s,c,seg,'接受第一版',id='accept-interrupted')
    pipe(b,i,'offer',action='accept',values={'output_id':'passed'},user_quote='接受第一版')
    b.end(Identity(**i))
    messages=c.view('ui')['result_messages']
    assert len(messages)==1 and '已接受' in messages[0]['content']
    assert messages[0]['publicationSource']=={'work_id':w,'output_id':'passed'}
    assert c.view('ui')['result_messages']==messages
    with s.store.connection() as conn:
        assert conn.execute('select count(*) from acceptances').fetchone()[0]==1
        assert conn.execute('select count(*) from publication_drafts').fetchone()[0]==0



def test_pending_uses_existing_projection_and_full_detail_remains_explicit(prepared):
    s,w,c,seg=setup(prepared)
    review=s.command('revise',{'output_id':'passed','feedback':'调整画面'},command_id='fixture-review',work_id=w,expected_revision=s.snapshot(w)['revision'])
    with s.store.transaction() as conn:
        conn.execute('UPDATE reviews SET changes_json=? WHERE id=?',(json.dumps({'schema_version':1,'history':'long-history-'*10000}),review['review_id']))
    b,i,_=turn(s,c,seg,'查看当前发布状态',id='summary')
    summary=pipe(b,i,'pending')
    detail=pipe(b,i,'pending',values={'detail':'full'})
    assert summary['work']['revision']==detail['work']['revision']
    assert summary['current_plan']==detail['current_plan']
    assert summary['work']['artifacts'][0]['id'] in {'passed','unchecked'}
    assert 'long-history-' not in json.dumps(summary)
    assert 'long-history-' in json.dumps(detail)
    assert summary['work']['artifacts'][0]['quality_state'] in {'passed','unchecked'}
