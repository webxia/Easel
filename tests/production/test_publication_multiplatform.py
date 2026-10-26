"""Cross-platform accepted media stays on original scripts and persistent identities."""
from contextlib import contextmanager
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from easel.production.errors import ProductionError
from easel.production.publication import Publications
from easel.production.deletion import DeletionService
from easel.publication_bilibili import publishing_lock
from easel.publication_native import NativeAdapter
from web.publication_api import create_publication_router
from web.publication_files import create_file_cover_router, file_cover_path
from web.production_api import production_error_handler
from tests.production.test_revision_acceptance import prepared
from tests.production.test_publication import publication


class NativeFake:
    def __init__(self, platform):self.platform=platform;self.calls=0
    @contextmanager
    def session(self):yield self
    def account(self):return {'platform':self.platform,'uid':'same-id','name':'test'}
    def validate(self, content, final=False):return None
    def stage_video(self,path,digest):return path
    def stage_cover(self,path,digest):return path
    def upload(self,path,content):self.calls+=1;return {'returncode':0,'timed_out':False}


def accept(service,work):
    service.command('accept',{'output_id':'passed'},command_id='accept',work_id=work,expected_revision=3)


def ready(service,work,platform):
    adapter=NativeFake(platform);p=Publications(service,adapter)
    d=p.prepare(work,'passed',platform=platform)
    d=p.save(d['id'],d['revision'],{**d['content'],'account':adapter.account(),'tags':['test']})
    return p,adapter,d


def test_same_uid_different_platforms_unknown_does_not_cross_block_or_retry(prepared):
    service,work=prepared;accept(service,work)
    p,a,d=ready(service,work,'douyin');q,b,e=ready(service,work,'kuaishou')
    result=p.submit(d['id'],d['revision'],d['confirmation_hash'])
    assert result['attempts'][-1]['state']=='unknown' and result['attempts'][-1]['snapshot'] is None
    assert result['attempts'][-1]['can_reconcile'] is False
    assert result['attempts'][-1]['receipt']['execution']['returncode']==0
    assert q.submit(e['id'],e['revision'],e['confirmation_hash'])['attempts'][-1]['state']=='unknown'
    p.submit(d['id'],d['revision'],d['confirmation_hash'])
    assert a.calls==b.calls==1
    snapshot=service.snapshot(work)
    output=next(v for v in snapshot['artifacts'] if v['id']=='passed')
    assert {v['platform'] for v in output['publications']}=={'douyin','kuaishou'}
    assert p.prepare(work,'passed',platform='douyin')['id']==d['id']
    with pytest.raises(ProductionError):p.reconcile(d['id'])
    with pytest.raises(ProductionError):p.resolve_absent(d['id'],d['revision'],d['confirmation_hash'],'any',True)
    with pytest.raises(ProductionError):DeletionService(service.store,outputs=service.outputs).preview(work)


def test_router_platform_dispatch_and_reads_preserve_tables(prepared):
    service,work=prepared;accept(service,work)
    fake={p:NativeFake(p) for p in ['douyin','kuaishou']}
    app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler)
    app.include_router(create_publication_router(lambda:service,platform_adapter_provider=lambda p:fake[p]))
    c=TestClient(app)
    d=c.post('/api/production/publications/prepare',json={'work_id':work,'output_id':'passed','platform':'douyin'}).json()
    assert d['platform']=='douyin'
    assert c.post('/api/production/publications/account?platform=douyin').json()['platform']=='douyin'
    before=service.store.path.read_bytes()
    assert c.get('/api/production/publications/'+d['id']).json()['id']==d['id']
    assert c.get('/api/production/publications').json()[0]['platform']=='douyin'
    assert service.store.path.read_bytes()==before
    assert fake['douyin'].calls==0


def image_data():
    f=io.BytesIO();Image.new('RGB',(320,180),'navy').save(f,'PNG');return f.getvalue()


def test_original_file_covers_have_no_work_dependency_and_validate_identity(tmp_path):
    root=tmp_path/'outputs';root.mkdir();(root/'image.png').write_bytes(image_data())
    def resolve(path):
        p=(root/path).resolve()
        if root not in p.parents or path.startswith(('works','_','/')) or p.is_symlink():raise ValueError('private')
        return p
    app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler)
    app.include_router(create_file_cover_router(lambda:root,resolve));c=TestClient(app)
    cover=c.post('/api/publish/covers',json={'library_path':'image.png'}).json()
    assert c.get('/api/publish/covers/'+cover['digest']).headers['content-type']=='image/jpeg'
    uploaded=c.post('/api/publish/covers/upload',files={'file':('cover.png',image_data(),'image/png')}).json()
    assert cover==uploaded
    assert not (root/'_production').exists()
    assert c.post('/api/publish/covers',json={'library_path':'image.png','at':1}).status_code==422
    assert c.post('/api/publish/covers/upload',files={'file':('bad',b'broken')}).status_code==422
    assert c.get('/api/publish/covers/not-a-hash').status_code==422
    file_cover_path(root,cover).write_bytes(b'changed')
    with pytest.raises(ProductionError):file_cover_path(root,cover)


@pytest.mark.parametrize('platform',['douyin','xiaohongshu','kuaishou','weixin-channels'])
def test_native_adapter_reuses_command_and_stages_exact_bytes(platform,tmp_path,monkeypatch):
    calls=[]
    a=NativeAdapter(tmp_path,platform,lambda *args:calls.append(args) or ['original-script'],
        lambda _: {'loggedIn':True,'name':'测试账号'},lambda:{})
    from hashlib import sha256
    media=tmp_path/'v.mp4';media.write_bytes(b'exact-video')
    cover=tmp_path/'c.jpg';cover.write_bytes(b'exact-cover')
    def run(cmd,**kw):assert cmd==['original-script'];return SimpleNamespace(returncode=0)
    monkeypatch.setattr('easel.publication_native.subprocess.run',run)
    with a.session() as s:
        assert s.account()['platform']==platform
        assert s.account()['uid'].startswith('profile-name:')
        video=s.stage_video(media,sha256(media.read_bytes()).hexdigest())
        s.stage_cover(cover,sha256(cover.read_bytes()).hexdigest())
        assert s.upload(video,{'title':'t'})=={'returncode':0,'timed_out':False}
        assert calls[0][0]==platform and calls[0][-1].read_bytes()==b'exact-cover'
        with pytest.raises(ProductionError):
            with publishing_lock(tmp_path,platform):pass
        with publishing_lock(tmp_path,'bilibili'):pass
    assert not video.exists()


def test_native_adapter_cannot_substitute_account_or_invent_readback(tmp_path):
    a=NativeAdapter(tmp_path,'douyin',None,lambda _: {'loggedIn':True,'name':''},None)
    with pytest.raises(ProductionError):a.account()
    with pytest.raises(ProductionError):a.validate({'title':'t','body':'b','credits':'','tags':[],'action':'submit','account':{'platform':'kuaishou','uid':'x'}})
    with a.session() as session:assert not hasattr(session,'snapshot') and not hasattr(session,'readback')


def test_original_command_builders_keep_media_and_explicit_cover(tmp_path,monkeypatch):
    import web.app as web
    monkeypatch.setattr(web,'OUTPUTS_DIR',tmp_path)
    monkeypatch.setattr(web,'PUBLISH_DIR',tmp_path/'_publish')
    monkeypatch.setattr('web.publication_files.file_cover_path',lambda *args:tmp_path/'cover.jpg')
    for platform in ['douyin','xiaohongshu','kuaishou','weixin-channels','bilibili']:
        request=web.PublishRequest(title='t',body='b',tags='tag',cover={'test':'reference'})
        cmd=web._native_publish_command(platform,request,[],['video.mp4'],web.LOGIN_RUNNERS[platform])
        assert 'video.mp4' in cmd and cmd[cmd.index('--cover')+1]==str(tmp_path/'cover.jpg')
        if platform=='douyin':assert '--status-file' in cmd and '--sms-code-file' in cmd
        assert '--cover' not in web._native_publish_command(platform,web.PublishRequest(title='t'),[],['video.mp4'],web.LOGIN_RUNNERS[platform])


def test_schema6_upgrade_preserves_every_existing_publication_field(publication,tmp_path):
    from easel.production.store import Store
    from easel.production.migrations import MIGRATIONS
    from easel.production.store import _statements
    import sqlite3
    p,a,d=publication
    p.submit(d['id'],d['revision'],d['confirmation_hash'])
    old=Store(tmp_path/'old.sqlite3')
    # Build the exact previous schema and copy a real complete fixture including FKs.
    p.store._connect().backup(sqlite3.connect(old.path))
    c=sqlite3.connect(old.path)
    data={t:c.execute('select * from '+t).fetchall() for t in ['publication_drafts','publication_attempts']}
    c.executescript('DROP TABLE publication_attempts; DROP TABLE publication_drafts;'+MIGRATIONS[5])
    for t,rows in data.items():
        for record in rows:c.execute('INSERT INTO '+t+' VALUES('+','.join('?' for _ in record)+')',record)
    c.execute('PRAGMA user_version=6');c.commit()
    assert "platform='bilibili'" in c.execute("select sql from sqlite_master where name='publication_drafts'").fetchone()[0]
    before={t:c.execute('select * from '+t).fetchall() for t in ['publication_drafts','publication_attempts','works','artifacts','acceptances']};c.close()
    old.initialize()
    with old.connection() as c:
        for t,rows in before.items():assert [tuple(r) for r in c.execute('select * from '+t)]==rows
        assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
        from easel.production.store import SCHEMA_VERSION
        assert c.execute('PRAGMA user_version').fetchone()[0]==SCHEMA_VERSION


@pytest.mark.parametrize('platform',['douyin','xiaohongshu','kuaishou','weixin-channels'])
def test_cover_upload_is_scoped_and_confirmed_before_publisher_can_submit(platform,tmp_path):
    from skills.shared.scripts.publish_cover import apply_custom_cover
    path=tmp_path/'cover.jpg';path.write_bytes(image_data());events=[]
    class Node:
        first=property(lambda self:self)
        last=property(lambda self:self)
        def count(self):return 1
        def is_visible(self):return True
        def get_by_text(self,*a,**kw):return self
        def get_by_role(self,*a,**kw):return self
        def locator(self,selector):events.append(('locator',selector));return self
        def click(self):events.append(('click',))
        def wait_for(self,**kwargs):events.append(('wait',kwargs['state']))
        def set_input_files(self,p,**kwargs):events.append(('upload',Path(p).read_bytes()))
    page=Node();apply_custom_cover(page,platform,path)
    upload=next(i for i,e in enumerate(events) if e[0]=='upload')
    assert events[upload][1]==image_data()
    assert any(e[0]=='locator' and 'role="dialog"' in e[1] for e in events[:upload])
    assert any(e[0]=='click' for e in events[upload+1:])
    assert events[-1]==('wait','hidden')
    class Missing(Node):
        def count(self):return 0
    with pytest.raises(RuntimeError):apply_custom_cover(Missing(),platform,path)


def test_async_legacy_dispatch_reserves_platform_before_touching_sms(tmp_path,monkeypatch):
    import web.app as web
    monkeypatch.setattr(web,'PROJECT_ROOT',tmp_path)
    status=tmp_path/'status.json';status.write_text('original')
    code=tmp_path/'sms.code';code.write_text('1234')
    with publishing_lock(tmp_path,'douyin'):
        with pytest.raises(ProductionError):web._start_async_publish('douyin',[],'t','b',{},status,code)
    assert status.read_text()=='original' and code.read_text()=='1234'

@pytest.mark.parametrize('platform,title,valid',[('douyin','题'*30,True),('douyin','题'*31,False),('xiaohongshu','A'*30,True),('xiaohongshu','题'*21,False)])
def test_native_metadata_uses_original_script_title_semantics(platform,title,valid,tmp_path):
    a=NativeAdapter(tmp_path,platform,None,None,None)
    content={'title':title,'body':'body','credits':'','tags':[],'action':'submit','account':None}
    if valid:a.validate(content)
    else:
        with pytest.raises(ProductionError):a.validate(content)


def test_weixin_channels_never_represses_submit_after_acknowledgement_timeout(monkeypatch):
    from skills.shared.scripts import web_publisher as script
    monkeypatch.setattr(script,'_settle_login',lambda *a:None)
    monkeypatch.setattr(script,'_is_logged_in',lambda *a:True)
    presses=[]
    class Frame:
        url='https://channels.weixin.qq.com/micro/content/post/create'
        def evaluate(self,code,*args):
            return True if '!!document.querySelector' in code else 'focused'
    class Page:
        url='https://channels.weixin.qq.com/platform/post/create'
        frames=[Frame()]
        keyboard=SimpleNamespace(press=lambda key:presses.append(key))
        def goto(self,*a,**kw):pass
        def wait_for_timeout(self,*a,**kw):pass
        def wait_for_selector(self,*a,**kw):pass
        def wait_for_url(self,*a,**kw):pass
        def set_input_files(self,*a,**kw):pass
        def locator(self,*a,**kw):return self
        def count(self):return 1
        def nth(self,i):return self
        def is_visible(self):return True
        def click(self):pass
    with pytest.raises(RuntimeError,match='勿重发'):
        script._publish_weixin_channels(Page(),{'media':'test.mp4','title':'t'})
    assert presses==['Enter']


@pytest.mark.parametrize('images',[[],['first.jpg','second.jpg']])
def test_wechat_explicit_cover_does_not_drop_or_add_body_images(images,tmp_path,monkeypatch):
    import web.app as web
    monkeypatch.setattr(web,'OUTPUTS_DIR',tmp_path)
    monkeypatch.setattr(web,'PUBLISH_DIR',tmp_path/'_publish')
    monkeypatch.setattr(web,'_mp_login_status',lambda:{'state':'success'})
    monkeypatch.setattr('web.publication_files.file_cover_path',lambda *a:tmp_path/'chosen-cover.jpg')
    def convert(cmd,**kwargs):
        Path(cmd[-1]).write_text('<html>body</html>');return SimpleNamespace(returncode=0)
    monkeypatch.setattr(web.subprocess,'run',convert)
    cmd=web._native_publish_command('wechat-oa',web.PublishRequest(title='t',body='text',cover={'ref':'test'}),images,[],web.LOGIN_RUNNERS['wechat-oa'])
    assert cmd[cmd.index('--cover')+1]==str(tmp_path/'chosen-cover.jpg')
    markdown=next((tmp_path/'_publish').glob('*.md')).read_text()
    assert 'chosen-cover.jpg' not in markdown
    for image in images:assert image in markdown
    if images:assert markdown.index(images[0])<markdown.index(images[1])
